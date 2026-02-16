# Simple Hugging Face Chatbot

A simple chatbot that uses Hugging Face's API to generate responses.

## Setup Steps

### 1. Get Your Hugging Face API Token

- Go to https://huggingface.co/
- Sign up or log in
- Go to Settings → Access Tokens
- Create a new token (Read access is sufficient)
- Copy the token

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Token

Open `chatbot.py` and replace `YOUR_HUGGING_FACE_API_TOKEN_HERE` with your actual API token.

### 4. Run the Chatbot

```bash
python chatbot.py
```

## How It Works

The script:

1. Sends your message to the Hugging Face API
2. Uses the `microsoft/DialoGPT-medium` model (a conversational AI model)
3. Receives and displays the response
4. Continues in a loop until you type 'quit'

## Next Steps

Once this works, you can:

- Add conversation history/context
- Try different models
- Build a web interface
- Add more features
