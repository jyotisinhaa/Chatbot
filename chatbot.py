import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client with Hugging Face router
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.getenv("HF_TOKEN"),
)

# Model to use
MODEL_NAME = "meta-llama/Llama-3.2-3B-Instruct"

def chat(user_message):
    """
    Send a message to the chatbot and get a response
    """
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_tokens=250,
            temperature=0.7,
        )
        
        return completion.choices[0].message.content
    
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    print("=== Hugging Face Chatbot (Llama 3.2) ===")
    print("Type 'quit' to exit\n")
    
    # Interactive chat loop
    while True:
        user_input = input("You: ")
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        response = chat(user_input)
        print(f"Bot: {response}\n")

