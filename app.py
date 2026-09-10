import json
import os
import asyncio
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ============ НАСТРОЙКИ ============
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
WEBHOOK_PATH = "webhook_secret_9d"
DATA_FILE = "homework.json"
# ===================================

SUBJECTS = {
    "russian":    "Русский язык",
    "algebra":    "Алгебра",
    "geometry":   "Геометрия",
    "physics":    "Физика",
    "literature": "Литература",
    "history":    "История",
    "biology":    "Биология",
    "chemistry":  "Химия",
    "geography":  "География",
    "english":    "Английский язык",
    "informatics":"Информатика",
    "obzh":       "ОБЖ",
    "pe":         "Физкультура",
}

DEFAULT_HOMEWORK = {key: "Домашнее задание пока не задано." for key in SUBJECTS}


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("homework", DEFAULT_HOMEWORK.copy()), data.get("owner_id", 0)
    return DEFAULT_HOMEWORK.copy(), 0


def save_data(homework, owner_id):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"homework": homework, "owner_id": owner_id}, f, ensure_ascii=False, indent=2)


homework, OWNER_ID = load_data()


def is_owner(update: Update) -> bool:
    global OWNER_ID
    user_id = update.effective_user.id
    if OWNER_ID == 0:
        OWNER_ID = user_id
        save_data(homework, OWNER_ID)
        return True
    return user_id == OWNER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID
    user_id = update.effective_user.id
    if OWNER_ID == 0:
        OWNER_ID = user_id
        save_data(homework, OWNER_ID)
        await update.message.reply_text(
            f"👑 Вы назначены владельцем бота.\nВаш user_id: {user_id}"
        )
    keyboard = [[InlineKeyboardButton(name, callback_data=key)] for key, name in SUBJECTS.items()]
    await update.message.reply_text(
        "📚 *Д/З 9Д*\n\nКакой предмет вас интересует?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def subject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data
    name = SUBJECTS.get(key, "Неизвестный предмет")
    task = homework.get(key, "Домашнее задание пока не задано.")
    await query.message.reply_text(f"📖 *{name}*\n\n{task}", parse_mode="Markdown")


async def set_hw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ У вас нет прав для изменения Д/З.")
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Формат: `/set <предмет> <текст>`\nПример: `/set algebra № 345`",
            parse_mode="Markdown",
        )
        return
    key = context.args[0].lower()
    text = " ".join(context.args[1:])
    if key not in SUBJECTS:
        await update.message.reply_text(f"❌ Предмет не найден.\nДоступные: {', '.join(SUBJECTS.keys())}")
        return
    homework[key] = text
    save_data(homework, OWNER_ID)
    await update.message.reply_text(f"✅ Д/З по «{SUBJECTS[key]}» обновлено.")


async def list_hw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ Команда только для владельца.")
        return
    lines = [f"• *{SUBJECTS[k]}*: {homework.get(k, '—')}" for k in SUBJECTS]
    await update.message.reply_text("📋 *Все Д/З:*\n\n" + "\n".join(lines), parse_mode="Markdown")


# ============ FLASK + ВЕБХУК ============
flask_app = Flask(__name__)

application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("set", set_hw))
application.add_handler(CommandHandler("all", list_hw))
application.add_handler(CallbackQueryHandler(subject_callback))

# Один общий event loop на всё приложение
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


@flask_app.route("/")
def index():
    return "Bot is running"


@flask_app.route("/health")
def health():
    return "OK"


@flask_app.route(f"/{WEBHOOK_PATH}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    loop.run_until_complete(application.process_update(update))
    return "OK"


def init_app():
    """Инициализируем Application и ставим вебхук один раз при старте."""
    async def setup():
        await application.initialize()
        if RENDER_URL:
            webhook_url = f"{RENDER_URL}/{WEBHOOK_PATH}"
            await application.bot.set_webhook(url=webhook_url)
            print(f"Вебхук установлен: {webhook_url}")
        else:
            print("RENDER_URL не задан — вебхук не настроен")

    loop.run_until_complete(setup())


if __name__ == "__main__":
    init_app()
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
