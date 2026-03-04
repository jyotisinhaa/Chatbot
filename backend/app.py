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


def get_welcome_message(name: str = "User") -> str:
    """Returns a friendly welcome message."""
    return f"Hello, {name}! Welcome to your AI assistant demo."


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


def extract_location(message: str) -> str:
    """Extract city/location name from user message using regex."""
    # Look for patterns like "in Tokyo", "of london", "at sydney"
    match = re.search(r'\b(?:in|of|at)\s+([a-zA-Z\s]+?)(?:\?|$)', message, re.IGNORECASE)
    if match:
        location = match.group(1).strip()
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
- When a user asks for a welcome message, use the get_welcome_message tool with their name
- When a user asks for temperature or weather in a location, use the get_current_temperature tool with the city name
  - This tool provides REAL weather data from Open-Meteo API
  - If the API returns an error, gracefully inform the user about the issue
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
        "get_welcome_message": lambda: get_welcome_message("User"),
        "get_current_temperature": get_current_temperature
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
                "name": "get_welcome_message",
                "description": "Get a friendly welcome message",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The user's name"
                        }
                    },
                    "required": ["name"]
                }
            },
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

    # Intent-based tool choice: detect what user is asking for
    user_message_lower = request.message.lower()
    tool_choice = "auto"
    
    if "temperature" in user_message_lower or "weather" in user_message_lower:
        tool_choice = {"type": "function", "function": {"name": "get_current_temperature"}}
        debug_log(f"Intent detected: WEATHER - forcing temperature tool")
    elif "time" in user_message_lower or "date" in user_message_lower:
        tool_choice = {"type": "function", "function": {"name": "get_current_datetime"}}
        debug_log(f"Intent detected: TIME/DATE - forcing datetime tool")
    elif "welcome" in user_message_lower or "hello" in user_message_lower or "hi" in user_message_lower:
        tool_choice = {"type": "function", "function": {"name": "get_welcome_message"}}
        debug_log(f"Intent detected: WELCOME - forcing welcome message tool")

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
                elif function_name == "get_welcome_message":
                    function_response = get_welcome_message(function_args.get("name", "friend"))
                elif function_name == "get_current_temperature":
                    function_response = get_current_temperature(function_args.get("location", "New York"))
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
            # No tool calls, just use the content
            reply = message.content or ""
        
    except Exception as exc:
        debug_log(f"{'='*60}")
        debug_log(f"ERROR in LLM call:")
        debug_log(f"Exception type: {type(exc).__name__}")
        debug_log(f"Exception: {exc}")
        debug_log(f"{'='*60}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Add final assistant response to session history
    sessions[session_id].append({"role": "assistant", "content": reply})
    
    return ChatResponse(reply=reply, session_id=session_id)