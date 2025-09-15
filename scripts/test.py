import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "<YOUR_SITE_URL>",  # Optional. Site URL for rankings on openrouter.ai.
        "X-Title": "<YOUR_SITE_NAME>",  # Optional. Site title for rankings on openrouter.ai.
    },
    data=json.dumps(
        {
            "model": "openai/gpt-4.1-mini",  # Optional
            "messages": [{"role": "user", "content": "What is the meaning of life?"}],
        }
    ),
)
print(response.text)
