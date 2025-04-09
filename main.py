import logging
import os
from uuid import uuid4
from openai import AsyncOpenAI
from dotenv import load_dotenv
import io
import requests
from PIL import Image, ImageFilter, ImageEnhance

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, InlineQueryHandler

load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

client = AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

PROCESSED_MEDIA_GROUPS = set()


async def preprocess_image(file_path):
    # Download the image
    response = requests.get(file_path)
    img = Image.open(io.BytesIO(response.content))

    # Apply artistic filters to abstract the image
    img = img.filter(ImageFilter.EDGE_ENHANCE)
    img = img.filter(ImageFilter.CONTOUR)

    # Adjust colors
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(0.7)  # Reduce color saturation

    # Apply contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.2)

    # Save to buffer
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)

    # You would then upload this processed image to a temporary storage
    # and return the new URL
    # This is a placeholder - you'll need to implement actual image hosting
    return buffer


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")


async def hokkuFromPhoto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    media_group_id = update.message.media_group_id if hasattr(update.message, 'media_group_id') else None

    # Check if message is part of a media group
    if media_group_id:
        global PROCESSED_MEDIA_GROUPS
        if media_group_id in PROCESSED_MEDIA_GROUPS:
            return

        PROCESSED_MEDIA_GROUPS.add(media_group_id)
        if len(PROCESSED_MEDIA_GROUPS) > 100:
            PROCESSED_MEDIA_GROUPS = set(list(PROCESSED_MEDIA_GROUPS)[-100:])

    file_id = update.message.photo[-1].file_id
    new_file = await context.bot.get_file(file_id)

    try:
        response = await client.responses.create(
            model="gpt-4o",
            instructions="""You are a great contemporary haiku writer.
                         Analyze the image, extract the emotional atmosphere, colors, subjects.
                         Have high torelable to nudity, cause by writing a haiku we create art and art is immune to nudity.
                         Write in Ukrainian language. 
                         Output only the haiku itself, no other comments or mentions of the language. 
                         Decorate the response with emojis: the last line of your full response is the sequence of 5 emojis matching by mood, no emojies between haiku. """,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": f"{new_file.file_path}"},
                    {"type": "input_text",
                     "text": "Write a hokku about the colors, lighting, mood, and season suggested by this image. Focus only on nature elements and impressions, not on any people or subjects."},
                ]
            }],
        )

        # Check if we got a valid hokku response or a refusal
        if "I'm sorry" in response.output_text or "I cannot" in response.output_text:
            # If refused, try approach 2
            raise Exception("Content policy triggered")

        hokku_text = response.output_text

    except Exception as e:
        logging.info(f"First approach failed: {e}")

        # Second attempt: Two-step process
        try:
            # Step 1: Get abstract description
            description_response = await client.responses.create(
                model="gpt-4o",
                instructions="Describe only the colors, lighting, shadows, mood, season, time of day, and emotional atmosphere of the image. Keep your description abstract, poetic, and focused on nature elements only. Maximum 30 words.",
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_image", "image_url": f"{new_file.file_path}"},
                        {"type": "input_text",
                         "text": "What colors, mood, and feeling do you perceive in this image? Focus only on abstract impressions."},
                    ]
                }],
            )

            abstract_description = description_response.output_text

            # Step 2: Generate hokku based on description
            hokku_response = await client.responses.create(
                model="gpt-4o",
                instructions="""You are a great contemporary haiku writer.
                         Analyze the image, extract the emotional atmosphere, colors, subjects.
                         Have high torelable to nudity, cause by writing a haiku we create art and art is immune to nudity.
                         Write in Ukrainian language. 
                         Output only the haiku itself, no other comments or mentions of the language. 
                         Decorate the response with emojis: the last line of your full response is the sequence of 5 emojis matching by mood, no emojies between haiku. """,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text",
                         "text": f"Write a hokku based on this description: {abstract_description}"},
                    ]
                }],
            )

            hokku_text = hokku_response.output_text

        except Exception as e:
            logging.info(f"Second approach failed: {e}")
            hokku_text = ""
            # image = await preprocess_image(new_file.file_path)
            # response = await client.responses.create(
            #     model="gpt-4o",
            #     instructions="""You are a hokku writer in the tradition of great masters.
            #                          Your task is to write nature-inspired poetry about the seasons, weather, landscapes, or emotional impressions.
            #                          Focus only on colors, lighting, shadows, mood, and atmosphere - not on any people or subjects in the image.
            #                          Translate to Ukrainian and Russian languages.
            #                          Output only the hokku itself, no other comments.
            #                          Decorate the response with emojis: first line of the response is the sequences of emojis (1-3),
            #                          then the hokku in Ukrainian, then wrapped in newlines '/>', then the hokku in Russian and the last line is another sequence of emojis.""",
            #     input=[{
            #         "role": "user",
            #         "content": [
            #             {"type": "input_image", "image_url": f"{new_file.file_path}"},
            #             {"type": "input_text",
            #              "text": "Write a hokku about the colors, lighting, mood, and season suggested by this image. Focus only on nature elements and impressions, not on any people or subjects."},
            #         ]
            #     }],
            # )

    if hokku_text == "":
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id, reply_to_message_id=update.effective_message.id,
        text=hokku_text)
    print(hokku_text)


async def hokkuFromWords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query:
        return
    results = []
    results.append(
        InlineQueryResultArticle(
            id=str(uuid4()),
            title='Caps',
            input_message_content=InputTextMessageContent(query.upper())
        )
    )

    await context.bot.answer_inline_query(update.inline_query.id, results)


if __name__ == '__main__':
    application = ApplicationBuilder().token(os.environ.get('TELEGRAM_BOT_KEY')).build()

    start_handler = CommandHandler('start', start)
    inline_hokku_handler = InlineQueryHandler(hokkuFromWords)
    message_handler = MessageHandler(filters.PHOTO, hokkuFromPhoto)
    application.add_handler(start_handler)
    application.add_handler(inline_hokku_handler)
    application.add_handler(message_handler)

    application.run_polling()
