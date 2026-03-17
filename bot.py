import os
import asyncio
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from deep_translator import GoogleTranslator

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

user_direction = {}

buttons = [
    ["UZ -> RU", "UZ -> EN"],
    ["UZ -> TR", "RU -> UZ"],
    ["EN -> UZ", "TR -> UZ"]
]

reply_keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)

LANG_MAP = {
    "UZ -> RU": ("uz", "ru"),
    "UZ -> EN": ("uz", "en"),
    "UZ -> TR": ("uz", "tr"),
    "RU -> UZ": ("ru", "uz"),
    "EN -> UZ": ("en", "uz"),
    "TR -> UZ": ("tr", "uz"),
}

flask_app = Flask(__name__)
ptb_app = Application.builder().token(TOKEN).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum!\n\n"
        "Men tarjimon botman.\n"
        "Tarjima yo'nalishini tanlang:",
        reply_markup=reply_keyboard
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Foydalanish tartibi:\n"
        "1. Tarjima yo'nalishini tanlang\n"
        "2. Matn yuboring\n"
        "3. Men tarjima qilib beraman"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if text in LANG_MAP:
        user_direction[user_id] = text
        await update.message.reply_text(
            f"Siz {text} yo'nalishini tanladingiz.\nEndi matn yuboring."
        )
        return

    if user_id not in user_direction:
        await update.message.reply_text(
            "Avval tarjima yo'nalishini tanlang.",
            reply_markup=reply_keyboard
        )
        return

    src_lang, dest_lang = LANG_MAP[user_direction[user_id]]

    try:
        result = GoogleTranslator(source=src_lang, target=dest_lang).translate(text)
        await update.message.reply_text(f"Tarjima natijasi:\n\n{result}")
    except Exception as e:
        print("Xatolik:", e)
        await update.message.reply_text(
            "Tarjima qilishda xatolik yuz berdi. Qayta urinib ko'ring."
        )


ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(CommandHandler("help", help_command))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


@flask_app.route("/", methods=["GET"])
def home():
    return "Bot is running", 200


@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, ptb_app.bot)
    asyncio.run(ptb_app.process_update(update))
    return "ok", 200


async def setup():
    await ptb_app.initialize()
    await ptb_app.start()
    webhook_url = f"{RENDER_EXTERNAL_URL}/{TOKEN}"
    await ptb_app.bot.set_webhook(webhook_url)
    print(f"Webhook set: {webhook_url}")


if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("BOT_TOKEN topilmadi")
    if not RENDER_EXTERNAL_URL:
        raise ValueError("RENDER_EXTERNAL_URL topilmadi")

    asyncio.run(setup())
    flask_app.run(host="0.0.0.0", port=PORT)