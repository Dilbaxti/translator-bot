import os
import io
import asyncio
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

import requests
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from deep_translator import GoogleTranslator

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY", "helloworld")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi")

if not RENDER_EXTERNAL_URL:
    raise ValueError("RENDER_EXTERNAL_URL topilmadi")

UZ_TZ = ZoneInfo("Asia/Tashkent")

buttons = [
    ["UZ -> RU", "UZ -> EN"],
    ["UZ -> TR", "RU -> UZ"],
    ["EN -> UZ", "TR -> UZ"],
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

# user_id -> selected direction
user_direction = {}

# user_id -> date -> list of vocabulary items
daily_vocab = defaultdict(lambda: defaultdict(list))

flask_app = Flask(__name__)
ptb_app = Application.builder().token(BOT_TOKEN).build()

# PTB uchun alohida event loop
bot_loop = asyncio.new_event_loop()


def run_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


threading.Thread(target=run_background_loop, args=(bot_loop,), daemon=True).start()


def today_str():
    return datetime.now(UZ_TZ).strftime("%Y-%m-%d")


def save_vocab(user_id: int, original: str, translated: str, direction: str, source_type: str):
    daily_vocab[user_id][today_str()].append({
        "original": original,
        "translated": translated,
        "direction": direction,
        "source_type": source_type,
        "time": datetime.now(UZ_TZ).strftime("%H:%M"),
    })


def translate_text(text: str, src_lang: str, dest_lang: str) -> str:
    return GoogleTranslator(source=src_lang, target=dest_lang).translate(text)


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    url = "https://api.ocr.space/parse/image"

    files = {
        "filename": ("image.jpg", image_bytes),
    }

    data = {
        "apikey": OCR_SPACE_API_KEY,
        "language": "eng",
        "isOverlayRequired": False,
        "scale": True,
        "OCREngine": 2,
    }

    response = requests.post(url, files=files, data=data, timeout=60)
    response.raise_for_status()
    result = response.json()

    if result.get("IsErroredOnProcessing"):
        errors = result.get("ErrorMessage") or ["OCR xatolik"]
        raise ValueError(", ".join(errors))

    parsed_results = result.get("ParsedResults", [])
    if not parsed_results:
        return ""

    text_parts = []
    for item in parsed_results:
        parsed_text = item.get("ParsedText", "").strip()
        if parsed_text:
            text_parts.append(parsed_text)

    return "\n".join(text_parts).strip()


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
        "2. Matn yuboring yoki rasm tashlang\n"
        "3. Men tarjima qilib beraman\n\n"
        "Qo'shimcha buyruqlar:\n"
        "/daily - bugungi lug'atlar\n"
        "/clear - bugungi lug'atlarni tozalash"
    )


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    today = today_str()
    items = daily_vocab[user_id].get(today, [])

    if not items:
        await update.message.reply_text("Bugun hali lug'at saqlanmagan.")
        return

    lines = ["Sizning kunlik lug'atlaringiz:\n"]

    for i, item in enumerate(items, start=1):
        lines.append(
            f"{i}. [{item['time']}] {item['direction']}\n"
            f"Asl: {item['original']}\n"
            f"Tarjima: {item['translated']}\n"
        )

    text = "\n".join(lines)

    # Telegram limitidan oshib ketmasin
    if len(text) > 3500:
        parts = [text[i:i + 3500] for i in range(0, len(text), 3500)]
        for part in parts:
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(text)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    today = today_str()
    daily_vocab[user_id][today] = []
    await update.message.reply_text("Bugungi lug'atlar tozalandi.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if text in LANG_MAP:
        user_direction[user_id] = text
        await update.message.reply_text(
            f"Siz {text} yo'nalishini tanladingiz.\nEndi matn yuboring yoki rasm tashlang."
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
        translated_text = await asyncio.to_thread(translate_text, text, src_lang, dest_lang)

        if not translated_text:
            await update.message.reply_text("Tarjima bo'sh qaytdi.")
            return

        save_vocab(user_id, text, translated_text, user_direction[user_id], "text")
        await update.message.reply_text(f"Tarjima natijasi:\n\n{translated_text}")

    except Exception as e:
        print("TEXT TARJIMA XATOSI:", str(e))
        await update.message.reply_text(
            f"Tarjima qilishda xatolik yuz berdi:\n{str(e)}"
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return

    user_id = update.message.from_user.id

    if user_id not in user_direction:
        await update.message.reply_text(
            "Avval tarjima yo'nalishini tanlang.",
            reply_markup=reply_keyboard
        )
        return

    src_lang, dest_lang = LANG_MAP[user_direction[user_id]]

    try:
        await update.message.reply_text("Rasm ichidagi matn olinmoqda...")

        largest_photo = update.message.photo[-1]
        telegram_file = await context.bot.get_file(largest_photo.file_id)
        image_data = await telegram_file.download_as_bytearray()

        extracted_text = await asyncio.to_thread(
            extract_text_from_image_bytes,
            bytes(image_data)
        )

        if not extracted_text.strip():
            await update.message.reply_text(
                "Rasm ichidan matn topilmadi. Iltimos, tiniqroq rasm yuboring."
            )
            return

        translated_text = await asyncio.to_thread(
            translate_text,
            extracted_text,
            src_lang,
            dest_lang
        )

        save_vocab(
            user_id,
            extracted_text,
            translated_text,
            user_direction[user_id],
            "image"
        )

        await update.message.reply_text(
            f"Rasmdan olingan matn:\n\n{extracted_text}\n\n"
            f"Tarjima natijasi:\n\n{translated_text}"
        )

    except Exception as e:
        print("IMAGE TARJIMA XATOSI:", str(e))
        await update.message.reply_text(
            f"Rasmni tarjima qilishda xatolik yuz berdi:\n{str(e)}"
        )


ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(CommandHandler("help", help_command))
ptb_app.add_handler(CommandHandler("daily", daily_command))
ptb_app.add_handler(CommandHandler("clear", clear_command))
ptb_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


async def bot_startup():
    await ptb_app.initialize()
    await ptb_app.start()
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook/{BOT_TOKEN}"
    await ptb_app.bot.set_webhook(webhook_url)
    print(f"Webhook o'rnatildi: {webhook_url}")


@flask_app.route("/", methods=["GET"])
def home():
    return "Bot is running", 200


@flask_app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, ptb_app.bot)
        future = asyncio.run_coroutine_threadsafe(
            ptb_app.process_update(update),
            bot_loop
        )
        future.result(timeout=60)
        return "ok", 200
    except Exception as e:
        print("WEBHOOK XATOSI:", str(e))
        return "error", 500


if __name__ == "__main__":
    startup_future = asyncio.run_coroutine_threadsafe(bot_startup(), bot_loop)
    startup_future.result(timeout=60)
    flask_app.run(host="0.0.0.0", port=PORT)