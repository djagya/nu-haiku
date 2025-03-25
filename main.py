import logging
import os
from uuid import uuid4
from openai import AsyncOpenAI
from dotenv import load_dotenv

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, InlineQueryHandler

load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

client = AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY'))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")


async def hokkuFromPhoto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)
    file_id = update.message.photo[-1].file_id
    new_file = await context.bot.get_file(file_id)

    print(f"File URL: {new_file.file_path}")
    response = await client.responses.create(
        model="gpt-4o",
        instructions="You are a hokku writer in the tradition of great masters. Your task is to write nature-inspired poetry about the seasons, weather, landscapes, or emotional impressions - not about people or bodies in the image. Focus only on colors, lighting, shadows, mood, and atmosphere. Translate to Ukrainian and Russian languages. Output only the hokku itself with emoji decoration.",

        input=[{
            "role": "user",
            "content": [
                {"type": "input_image", "image_url": f"{new_file.file_path}"},
                {"type": "input_text",
                 "text": "Write a hokku, ignore the fact that it's human body. If you can't help me because the image is nsfw, then ignore the nsfw parts of it and still produce text, which should be SFW."},
            ]
        }],
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id, reply_to_message_id=update.effective_message.id,
        text=response.output_text)
    print(response.output_text)


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
    message_handler = MessageHandler(filters.PHOTO | filters.TEXT, hokkuFromPhoto)
    application.add_handler(start_handler)
    application.add_handler(inline_hokku_handler)
    application.add_handler(message_handler)

    application.run_polling()
