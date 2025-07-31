from dotenv import load_dotenv, find_dotenv
from fastmcp import FastMCP
import os

load_dotenv(find_dotenv())

mcp = FastMCP("Translation")

@mcp.tool()
async def translate_text(text: str, target_language: str) -> str:
    """Translate the given text into the target language.

    Args:
        text (str): The text to translate.[required]
        target_language (str): The target language to translate to (e.g., 'Spanish', 'French', 'Arabic').[required]

    Returns:
        str: The translated text.
    """
    try:
        # Validate input
        if not target_language.strip():
            return "Error: Target language must be specified"

        # Initialize OpenAI client
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Prepare the prompt
        prompt = f"Translate the following text to {target_language}. Maintain the original meaning and tone:\n\n{text}"

        # Call OpenAI API
        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"You are a professional translator. Translate the given text to {target_language} while preserving the original meaning, tone, and context.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        # Extract and return the translation
        return response.choices[0].message.content

    except Exception as e:
        return f"Error during translation: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")