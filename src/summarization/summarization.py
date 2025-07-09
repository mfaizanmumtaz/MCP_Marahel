from dotenv import load_dotenv, find_dotenv
import os

load_dotenv(find_dotenv())


async def text_summarization(text: str) -> str:
    """Summarize the given text.

    Args:
        text (str): The text to summarize.

    Returns:
        str: The summarized text.
    """
    try:
        # Validate text length
        if len(text.strip()) < 10:
            return "Text must be at least 10 characters long"

        # Initialize OpenAI client
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Prepare the prompt
        prompt = f"Please provide a concise summary of the following text:\n\n{text}"

        # Call OpenAI API
        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant designed to summarize text concisely and accurately.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        # Extract and return the summary
        return response.choices[0].message.content

    except Exception as e:
        return f"Error during summarization: {str(e)}"
