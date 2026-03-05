import os
import re
from typing import List, Optional, Dict
import json
import uuid
from datetime import datetime
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from openai import OpenAI
from pydantic import BaseModel

# Helper function for debug output that writes to file
def debug_log(message: str):
    """Write debug message to debug.log file"""
    with open("debug.log", "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] 🔍 {message}\n")
        f.flush()

load_dotenv()

app = FastAPI(title="Chatbot UI API")

# Configuration constants
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_MAX_TOKENS = 250
DEFAULT_TEMPERATURE = 0.7
TEST_MAX_TOKENS = 10  # For API key validation only

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage for full conversation history
sessions: Dict[str, List[dict]] = {}


# ==================== TOOL FUNCTIONS ====================
def get_current_datetime():
    """Returns the current date and time as a JSON string."""
    return json.dumps({"current_datetime": datetime.now().isoformat()})


def get_current_temperature(location: str = "New York") -> str:
    """Returns the current temperature for a location using Open-Meteo API."""
    try:
        import requests
        
        # Clean up location: if it's in "City, State" format, try city first
        clean_location = location
        city_only = location.split(',')[0].strip() if ',' in location else location
        
        # Step 1: Geocode the location to get latitude/longitude
        geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
        
        # Try with the provided location first, then fallback to city only
        for search_location in [location, city_only]:
            geocode_params = {
                "name": search_location,
                "count": 1,
                "language": "en",
                "format": "json"
            }
            
            geocode_response = requests.get(geocode_url, params=geocode_params, timeout=5)
            debug_log(f"geocode_response for '{search_location}': {geocode_response.text}")
            geocode_response.raise_for_status()
            geocode_data = geocode_response.json()
            debug_log(f"geocode_data for '{search_location}': {geocode_data}")
            
            if geocode_data.get("results"):
                # Found results, use this
                break
        
        if not geocode_data.get("results"):
            return json.dumps({
                "location": location,
                "error": f"Location '{location}' not found. Please try a different city name."
            })
        

        # Get the first matching result
        result = geocode_data["results"][0]
        debug_log(f"geocode result: {result}")
        latitude = result["latitude"]
        debug_log(f"latitude: {latitude}")
        longitude = result["longitude"]
        debug_log(f"longitude: {longitude}")
        location_name = result.get("name", location)
        debug_log(f"location_name: {location_name}")
        country = result.get("country", "")
        debug_log(f"country: {country}")
        if country:
            location_name = f"{location_name}, {country}"
        
        # Step 2: Get current weather data
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,weather_code",
            "temperature_unit": "celsius"
        }
        
        weather_response = requests.get(weather_url, params=weather_params, timeout=5)
        weather_response.raise_for_status()
        weather_data = weather_response.json()
        debug_log(f"weather_data: {weather_data}")
        current = weather_data.get("current", {})
        temp_celsius = current.get("temperature_2m", 20)
        humidity = current.get("relative_humidity_2m", 0)
        temp_fahrenheit = round(temp_celsius * 9/5 + 32, 1)
        
        return json.dumps({
            "location": location_name,
            "temperature_celsius": temp_celsius,
            "temperature_fahrenheit": temp_fahrenheit,
            "humidity": humidity
        })
    
    except Exception as e:
        # Fallback: Return error message
        debug_log(f"Weather API error for '{location}': {str(e)}")
        return json.dumps({
            "location": location,
            "error": f"Unable to fetch weather data: {str(e)}"
        })


def web_search(query: str, max_results: int = 5) -> str:
    """Perform a web search and return results as JSON."""
    try:
        import requests
        from urllib.parse import quote_plus
        import xml.etree.ElementTree as ET

        normalized_query = " ".join(query.strip().split())
        normalized_query = re.sub(r"[^a-zA-Z0-9\s,\-]", "", normalized_query)
        typo_map = {
            "currnetly": "currently",
            "temprature": "temperature",
            "temperatur": "temperature",
            "waht": "what",
            "irab": "iran",
        }
        words = [typo_map.get(w.lower(), w) for w in normalized_query.split()]
        normalized_query = " ".join(words) if words else query

        # 1) Try Google News RSS first (best for current events)
        rss_url = f"https://news.google.com/rss/search?q={quote_plus(normalized_query)}&hl=en-US&gl=US&ceid=US:en"
        rss_response = requests.get(rss_url, timeout=10)
        if rss_response.status_code == 200 and rss_response.text:
            root = ET.fromstring(rss_response.text)
            rss_results = []
            for item in root.findall(".//item")[:max_results]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                description = (item.findtext("description") or "").strip()
                description = re.sub(r"<[^>]+>", "", description)
                if title or link:
                    rss_results.append({
                        "title": title,
                        "snippet": description,
                        "url": link,
                    })

            if rss_results:
                return json.dumps({
                    "query": normalized_query,
                    "results": rss_results,
                    "source": "Google News RSS"
                })
        
        # 2) Fallback to DuckDuckGo HTML search
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(normalized_query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse the HTML to extract search results
        from html.parser import HTMLParser
        
        class DuckDuckGoParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.results = []
                self.current_result = {}
                self.in_result = False
                self.in_result_title = False
                self.in_result_snippet = False
                
            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                if tag == 'a' and attrs_dict.get('class') == 'result__a':
                    self.in_result_title = True
                    self.current_result = {'url': attrs_dict.get('href', '')}
                elif tag == 'a' and 'result__snippet' in attrs_dict.get('class', ''):
                    self.in_result_snippet = True
                    
            def handle_endtag(self, tag):
                if tag == 'a' and self.in_result_title:
                    self.in_result_title = False
                if tag == 'a' and self.in_result_snippet:
                    self.in_result_snippet = False
                    if self.current_result and len(self.results) < max_results:
                        self.results.append(self.current_result)
                        self.current_result = {}
                        
            def handle_data(self, data):
                if self.in_result_title:
                    self.current_result['title'] = data.strip()
                elif self.in_result_snippet:
                    self.current_result['snippet'] = data.strip()
        
        parser = DuckDuckGoParser()
        parser.feed(response.text)
        
        if not parser.results:
            # 3) Final fallback: DuckDuckGo Instant Answer API
            instant_url = f"https://api.duckduckgo.com/?q={quote_plus(normalized_query)}&format=json"
            instant_response = requests.get(instant_url, timeout=5)
            instant_data = instant_response.json()
            
            results = []
            if instant_data.get('Abstract'):
                results.append({
                    'title': instant_data.get('Heading', query),
                    'snippet': instant_data.get('Abstract'),
                    'url': instant_data.get('AbstractURL', '')
                })
            
            # Add related topics
            for topic in instant_data.get('RelatedTopics', [])[:max_results-1]:
                if isinstance(topic, dict) and topic.get('Text'):
                    results.append({
                        'title': topic.get('Text', '')[:100],
                        'snippet': topic.get('Text', ''),
                        'url': topic.get('FirstURL', '')
                    })
            
            if results:
                return json.dumps({
                    "query": normalized_query,
                    "results": results,
                    "source": "DuckDuckGo Instant Answer"
                })
        else:
            return json.dumps({
                "query": normalized_query,
                "results": parser.results[:max_results],
                "source": "DuckDuckGo Search"
            })
        
        # If still no results
        return json.dumps({
            "query": normalized_query,
            "results": [],
            "error": "No search results found"
        })
        
    except Exception as e:
        debug_log(f"Web search error for '{query}': {str(e)}")
        return json.dumps({
            "query": query,
            "error": f"Unable to perform web search: {str(e)}"
        })


def extract_location(message: str) -> str:
    """Extract city/location name from user message using regex."""
    # Look for patterns like "in Tokyo", "in Ames, Iowa, USA", "at New York"
    match = re.search(r'\b(?:in|of|at)\s+([a-zA-Z\s,\-]+?)(?:\?|$)', message, re.IGNORECASE)
    if match:
        location = match.group(1).strip().strip(",.")
        return location if location else "New York"
    return "New York"  # Default fallback



@app.get("/health")
def health():
    return {"status": "ok"}


class ChatRequest(BaseModel):
    model: str = DEFAULT_MODEL
    message: str  # Just the new user message
    session_id: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/static/{file_path:path}")
async def static_files(file_path: str):
    full_path = os.path.join("frontend", file_path)
    if os.path.exists(full_path):
        return FileResponse(full_path)
    raise HTTPException(status_code=404, detail="File not found")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if not request.api_key or not request.api_key.strip():
        raise HTTPException(status_code=400, detail="API key is required. Please provide a valid Groq API key.")

    api_key = request.api_key.strip()
    
    # Create or retrieve session
    session_id = request.session_id or str(uuid.uuid4())
    
    # Enhanced system prompt
    SYSTEM_PROMPT = """You are a helpful, knowledgeable, and friendly AI assistant with access to various tools.

Guidelines:
- Provide clear, concise, and accurate responses
- Ask clarifying questions if the user's request is ambiguous
- Break down complex topics into digestible parts
- Maintain a professional yet approachable tone
- Acknowledge limitations when you don't know something
- Use examples when helpful to illustrate concepts
- Keep responses focused and relevant to the user's question

IMPORTANT - Tool Usage:
- You have access to functions/tools that you should use when appropriate
- When a user asks for the current time or date, use the get_current_datetime tool
- When a user asks for temperature or weather in a location, use the get_current_temperature tool with the city name
  - This tool provides REAL weather data from Open-Meteo API
  - If the API returns an error, gracefully inform the user about the issue
- When a user asks about current events, news, recent developments, or any topic you don't have information about, use the web_search tool
  - This tool searches the web and returns real, up-to-date information
  - Use it for questions like "What's happening in...", "Latest news about...", "Current events...", etc.
- Always use available tools instead of saying you don't have access to real-time information
- Call the appropriate function whenever the user's request matches a tool's capability"""
    
    # Initialize session with enhanced system message if new
    if session_id not in sessions:
        sessions[session_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    
    # Add new user message to session history
    sessions[session_id].append({"role": "user", "content": request.message})
    
    # Use ALL messages from session as context (full conversation history)
    messages_to_send = sessions[session_id]

    debug_log(f"Session ID: {session_id}")
    debug_log(f"Using API key (last 10 chars): ...{api_key[-10:]}")
    debug_log(f"Model: {request.model}")
    debug_log(f"Full context size: {len(messages_to_send)} messages")

    # Tool registry with proper definitions
    tool_functions = {
        "get_current_datetime": get_current_datetime,
        "get_current_temperature": get_current_temperature,
        "web_search": web_search
    }
    debug_log(f"Available tool functions: {list(tool_functions.keys())}")
    
    # Define tools for the LLM in OpenAI format
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_datetime",
                "description": "Get the current date and time",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_temperature",
                "description": "Get the current temperature for a specific location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city name (e.g., 'New York', 'London', 'Tokyo')"
                        }
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information, news, events, or any topic. Use this when users ask about current events, news, recent developments, or any information you don't have.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query (e.g., 'current events in Iran', 'latest tech news', 'what happened today')"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of search results to return (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]
    
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
    )

    debug_log(f"{'='*60}")
    debug_log(f"About to call LLM with:")
    debug_log(f"  - Model: {request.model}")
    debug_log(f"  - Tools enabled: {bool(tools)}")
    debug_log(f"  - Messages: {len(messages_to_send)}")
    debug_log(f"{'='*60}")

    # Intent-based tool routing:
    # 1) weather -> temperature tool
    # 2) time/date -> datetime tool
    # 3) greeting -> greeting handler tool
    # 4) everything else -> web search tool
    user_message_lower = request.message.lower()
    is_weather_query = bool(
        re.search(r"\b(weather|temperature|temperatur|temperate|temprature|temp)\b", user_message_lower)
    )
    is_time_query = "time" in user_message_lower or "date" in user_message_lower
    
    # Detect greetings/smalltalk — let LLM respond naturally (no tool needed)
    greeting_words = (
        r"^\s*("
        r"hey|hi|hello|hola|howdy|sup|wassup|whatsup|wazzup|yo|hiya|heya|"
        r"what'?s\s*up|wats\s*up|wuts\s*up|whats\s*good|"
        r"good\s*(morning|afternoon|evening|night)|"
        r"greetings|salutations|aloha|namaste"
        r")\s*[!?.]*\s*$"
    )
    how_are_you_patterns = (
        r"\bhow\s*(are|r)\s*(you|u|ya)\b"
        r"|\bhow'?s\s*it\s*going\b"
        r"|\bhow\s*(are|r)\s*(you|u|ya)\s*doing\b"
        r"|\bhow\s*do\s*you\s*do\b"
        r"|\bwhat'?s\s*up\s+with\s+you\b"
    )
    is_greeting = bool(
        re.search(greeting_words, user_message_lower)
        or re.search(how_are_you_patterns, user_message_lower)
    )

    if is_greeting and not is_weather_query and not is_time_query:
        # No tool needed — let the LLM handle greetings naturally
        tool_choice = "none"
        debug_log("Routing: GREETING -> LLM natural response (no tool)")
    elif is_weather_query:
        tool_choice = {"type": "function", "function": {"name": "get_current_temperature"}}
        debug_log("Routing: WEATHER -> get_current_temperature")
    elif is_time_query:
        tool_choice = {"type": "function", "function": {"name": "get_current_datetime"}}
        debug_log("Routing: TIME/DATE -> get_current_datetime")
    else:
        tool_choice = {"type": "function", "function": {"name": "web_search"}}
        debug_log("Routing: DEFAULT -> web_search")

    try:
        # Call LLM with tools
        completion = client.chat.completions.create(
            model=request.model,
            messages=messages_to_send,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            tools=tools,
            tool_choice=tool_choice,
        )
        
        message = completion.choices[0].message
        debug_log(f"Messsage line 201: {message}")

        
        # Debug: Log the response structure
        debug_log(f"{'='*60}")
        debug_log(f"LLM Response Structure:")
        debug_log(f"Message Content: {message.content}")
        debug_log(f"Has tool_calls: {hasattr(message, 'tool_calls') and message.tool_calls is not None}")
        if hasattr(message, 'tool_calls') and message.tool_calls:
            debug_log(f"Tool calls: {[tc.function.name for tc in message.tool_calls]}")
        
        # Check if LLM wants to call a function
        if hasattr(message, 'tool_calls') and message.tool_calls:
            debug_log("LLM requested tool execution!")
            
            # Add the assistant's message with tool_calls to history
            sessions[session_id].append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]
            })
            
            # Execute each tool call
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                
                debug_log(f"Executing tool: {function_name} with args: {function_args}")
                
                # Call the appropriate function
                if function_name == "get_current_datetime":
                    function_response = get_current_datetime()
                elif function_name == "get_current_temperature":
                    function_response = get_current_temperature(function_args.get("location", "New York"))
                elif function_name == "web_search":
                    function_response = web_search(
                        function_args.get("query", ""),
                        function_args.get("max_results", 5)
                    )
                else:
                    function_response = json.dumps({"error": f"Unknown function: {function_name}"})
                
                debug_log(f"Tool result: {function_response}")
                
                # Add the function result to messages
                sessions[session_id].append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": function_response
                })
            
            # Now call LLM again with the function results
            debug_log("Calling LLM again with tool results...")
            second_completion = client.chat.completions.create(
                model=request.model,
                messages=sessions[session_id],
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                tools=tools,
            )
            debug_log(f"Last Messsage line 261: {message}")
            reply = second_completion.choices[0].message.content or ""
            debug_log(f"Final response after tool execution: {reply}")
        else:
            # No tool_calls — use LLM's direct response or fallback
            if message.content:
                # LLM gave a direct text response (e.g., greetings, general chat)
                reply = message.content
                debug_log(f"LLM direct response (no tool): {reply}")
            elif is_weather_query:
                fallback_location = extract_location(request.message)
                temp_data = json.loads(get_current_temperature(fallback_location))
                if temp_data.get("error"):
                    reply = f"I couldn't fetch weather right now: {temp_data['error']}"
                else:
                    reply = (
                        f"The current temperature in {temp_data['location']} is "
                        f"{temp_data['temperature_celsius']}°C ({temp_data['temperature_fahrenheit']}°F)."
                    )
            elif is_time_query:
                time_data = json.loads(get_current_datetime())
                reply = f"The current date and time is {time_data['current_datetime']}."
            else:
                search_data = json.loads(web_search(request.message, 5))
                if search_data.get("error"):
                    reply = f"I couldn't complete web search right now: {search_data['error']}"
                elif not search_data.get("results"):
                    reply = "I couldn't find relevant web results. Please try a more specific query."
                else:
                    top = search_data["results"][:3]
                    lines = [f"Here are current web results for: {search_data.get('query', request.message)}"]
                    for i, item in enumerate(top, 1):
                        lines.append(f"{i}. {item.get('title', 'Untitled')}")
                        if item.get("snippet"):
                            lines.append(f"   {item['snippet']}")
                        if item.get("url"):
                            lines.append(f"   Source: {item['url']}")
                    reply = "\n".join(lines)
        
    except Exception as exc:
        # Provider fallback for malformed forced-tool generation
        if "tool_use_failed" in str(exc):
            debug_log("Provider returned tool_use_failed. Executing backend fallback based on route.")
            if is_weather_query:
                fallback_location = extract_location(request.message)
                temp_data = json.loads(get_current_temperature(fallback_location))
                if temp_data.get("error"):
                    reply = f"I couldn't fetch weather right now: {temp_data['error']}"
                else:
                    reply = (
                        f"The current temperature in {temp_data['location']} is "
                        f"{temp_data['temperature_celsius']}°C ({temp_data['temperature_fahrenheit']}°F)."
                    )
            elif is_time_query:
                time_data = json.loads(get_current_datetime())
                reply = f"The current date and time is {time_data['current_datetime']}."
            else:
                search_data = json.loads(web_search(request.message, 5))
                if search_data.get("error"):
                    reply = f"I couldn't complete web search right now: {search_data['error']}"
                elif not search_data.get("results"):
                    reply = "I couldn't find relevant web results. Please try a more specific query."
                else:
                    top = search_data["results"][:3]
                    lines = [f"Here are current web results for: {search_data.get('query', request.message)}"]
                    for i, item in enumerate(top, 1):
                        lines.append(f"{i}. {item.get('title', 'Untitled')}")
                        if item.get("snippet"):
                            lines.append(f"   {item['snippet']}")
                        if item.get("url"):
                            lines.append(f"   Source: {item['url']}")
                    reply = "\n".join(lines)
        else:
            debug_log(f"{'='*60}")
            debug_log(f"ERROR in LLM call:")
            debug_log(f"Exception type: {type(exc).__name__}")
            debug_log(f"Exception: {exc}")
            debug_log(f"{'='*60}")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Add final assistant response to session history
    sessions[session_id].append({"role": "assistant", "content": reply})
    
    return ChatResponse(reply=reply, session_id=session_id)