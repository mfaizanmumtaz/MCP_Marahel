import logging
import os
from langchain_openai import ChatOpenAI
from rag_cag_agent.config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)
formatter = logging.Formatter(
    "%(asctime)s:%(name)s:%(levelname)s:%(message)s:%(funcName)s"
)
os.makedirs(settings.LOG_DIR, exist_ok=True)  # Ensure the directory exists
file_handler = logging.FileHandler(f"{settings.LOG_DIR}/translation_utils.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

llm = ChatOpenAI(
    model=settings.OPENAI_MODEL, temperature=0, openai_api_key=settings.OPENAI_API_KEY
)


async def translate_text(text: str, target_language: str) -> str:
    """
    Translate text to the target language using OpenAI's API.

    Args:
        text (str): The text to translate
        target_language (str): The target language ('arabic' or 'english')

    Returns:
        str: The translated text
    """
    try:
        # Validate input
        if not text.strip():
            return "Error: Text cannot be empty"
        if not target_language.strip():
            return "Error: Target language must be specified"

        # Initialize OpenAI client
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # Prepare the prompt
        prompt = f"Translate the following text to {target_language}. Maintain the original meaning and tone:\n\n{text}"

        # Call OpenAI API
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
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
        logger.error(f"Error during translation: {str(e)}")
        return f"Error during translation: {str(e)}"


# Test the function
# async def main():
#     print("Testing translation_utils.py")

#     # Test case 1: English to Arabic
#     english_text = "Hello, how are you?"
#     arabic_translation = await translate_text(english_text, "arabic")
#     print(f"Original (English): {english_text}")
#     print(f"Translated (Arabic): {arabic_translation}")
#     print("-" * 20)

#     # Test case 2: Arabic to English
#     arabic_text = "شكرا جزيلا"
#     english_translation = await translate_text(arabic_text, "english")
#     print(f"Original (Arabic): {arabic_text}")
#     print(f"Translated (English): {english_translation}")
#     print("-" * 20)

#     # Test case 3: Empty string
#     empty_text = ""
#     empty_translation = await translate_text(empty_text, "arabic")
#     print(f"Original (Empty): '{empty_text}'")
#     print(f"Translated (Arabic): '{empty_translation}'")
#     print("-" * 20)

#     # Test case 4: Text already in target language (should ideally return original)
#     english_text_already = "This is already in English."
#     english_translation_again = await translate_text(english_text_already, "english")
#     print(f"Original (English): {english_text_already}")
#     print(f"Translated (English): {english_translation_again}")
#     print("-" * 20)


# if __name__ == "__main__":
#     asyncio.run(main())
