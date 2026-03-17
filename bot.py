import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from googletrans import Translator

TOKEN = os.getenv("BOT_TOKEN")

translator = Translator()
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum!\n\nTarjima yo'nalishini tanlang:",
        reply_markup=reply_keyboard
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        result = await translator.translate(text, src=src_lang, dest=dest_lang)
        await update.message.reply_text(f"Tarjima natijasi:\n\n{result.text}")
    except Exception as e:
        print("Xatolik:", e)
        await update.message.reply_text("Tarjima qilishda xatolik yuz berdi.")

def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN topilmadi")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Tarjimon bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()