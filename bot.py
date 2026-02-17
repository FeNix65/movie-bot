import json
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.error import BadRequest
from flask import Flask
from threading import Thread

# Flask для keep-alive (Render требует порт)
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

# Запускаем Flask в отдельном потоке
Thread(target=run_flask).start()

# Остальной код бота
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Берём из переменных окружения
DATA_FILE = "movies.json"

waiting_for_input = {}

DEFAULT_MOVIES = [
    "Бесстыжие (сериал)",
    "Шерлок Холмс (сериал)",
    "Рон Камонохаши невменяемый детектив (аниме) [S2E10]",
    "Убийство в восточном экспрессе 2017 (фильм)",
    "Sex education (сериал)",
    "Доктор Хаус (сериал)",
    "Агенты времени (аниме)",
    "Менталист (сериал)",
    "Линкольн для адвоката 2022 (сериал)",
    "Форсаж (фильм)",
    "Человек Паук (с Эндрю все части)",
    "Киберсталкер (сериал)",
    "Клаустрофобы (фильм 2 части)",
    "Песнь Ночных Сов (аниме)",
    "Волейбол (аниме)",
    "Семья шпиона (аниме)",
    "Герои энвелла (мультсериал)",
    "Убийца (Sicario 2 части)",
    "Как приручить дракона (3 фильма)",
    "Двадцать одно (фильм)",
    "Мрачные тени (фильм)",
    "Охота на воров",
    "Гравити фолз (мультсериал)",
    "Одноклассники (2 части)",
    "Обитель зла (фильм)",
    "Стажер (фильм)",
    "Джентельмены (фильм)",
    "Майор Пэйн (фильм)",
    "Короче план такой (сериал)",
    "Дэдпул (фильм)",
    "Ведьмак (сериал) [S2E4]",
    "Рик и морти (мультсериал)",
    "Харли квинн (мультсериал)",
    "Патриотизм мориарти (аниме)",
    "Один из нас лжет (сериал)",
    "Новокаин (фильм)",
    "Тайный орден (сериал)",
    "Зомбилэнд (фильм)",
    "Гран Туризмо (фильм)",
    "Тайлер Рейк: Операция по спасению (2 фильма)",
    "Кингсмен (фильм 3 части)",
    "Дьявол в деталях (фильм)",
    "Новичок (сериал)",
    "Сверхъестественное (сериал) [S1E6]"
]

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"movies": [{"title": m, "watched": False} for m in DEFAULT_MOVIES]}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def build_main_keyboard():
    data = load_data()
    keyboard = []
    
    unwatched_movies = [(idx, m) for idx, m in enumerate(data["movies"]) if not m["watched"]]
    
    for idx, movie in unwatched_movies:
        keyboard.append([
            InlineKeyboardButton(f"⬜️ {movie['title'][:40]}{'...' if len(movie['title']) > 40 else ''}", callback_data=f"toggle_{idx}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("Добавить фильм", callback_data="add"),
        InlineKeyboardButton("Удалить фильм", callback_data="delete_mode")
    ])
    
    watched_count = len([m for m in data["movies"] if m["watched"]])
    keyboard.append([
        InlineKeyboardButton(f"Просмотренные ({watched_count})", callback_data="watched_list"),
        InlineKeyboardButton("Статистика", callback_data="stats")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def build_watched_keyboard():
    data = load_data()
    keyboard = []
    
    for idx, movie in enumerate(data["movies"]):
        if movie["watched"]:
            keyboard.append([
                InlineKeyboardButton(f"✅ {movie['title'][:40]}{'...' if len(movie['title']) > 40 else ''}", callback_data=f"unwatch_{idx}")
            ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 Назад к списку", callback_data="back_to_main")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def build_delete_keyboard():
    data = load_data()
    keyboard = []
    
    for idx, movie in enumerate(data["movies"]):
        emoji = "✅" if movie["watched"] else "⬜️"
        keyboard.append([
            InlineKeyboardButton(f"🗑 {emoji} {movie['title'][:35]}{'...' if len(movie['title']) > 35 else ''}", callback_data=f"del_{idx}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Отмена", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = load_data()
    unwatched = len([m for m in data["movies"] if not m["watched"]])
    watched = len([m for m in data["movies"] if m["watched"]])
    
    try:
        await update.message.reply_text(
            f"<b>Список к просмотру</b>\n\n"
            f"⬜️ Осталось: {unwatched}\n"
            f"✅ Просмотрено: {watched}\n\n"
            f"Нажми на фильм, чтобы отметить просмотренным",
            reply_markup=build_main_keyboard(),
            parse_mode="HTML"
        )
    except BadRequest as e:
        logger.error(f"Ошибка при отправке: {e}")
        try:
            await update.message.reply_text(
                f"🎬 Список к просмотру\n\n"
                f"Осталось: {unwatched}\n"
                f"Просмотрено: {watched}\n\n"
                f"Нажми на фильм, чтобы отметить просмотренным",
                reply_markup=build_main_keyboard()
            )
        except Exception as e2:
            logger.error(f"Вторая ошибка: {e2}")
            await update.message.reply_text("Ошибка загрузки списка. Попробуй в личных сообщениях.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id
    movies_data = load_data()
    
    try:
        if data.startswith("toggle_"):
            idx = int(data.split("_")[1])
            movies_data["movies"][idx]["watched"] = True
            save_data(movies_data)
            
            await query.edit_message_text(
                f"<b>Список к просмотру</b>\n\n"
                f"✅ Отмечено: <i>{movies_data['movies'][idx]['title']}</i>",
                reply_markup=build_main_keyboard(),
                parse_mode="HTML"
            )
        
        elif data.startswith("unwatch_"):
            idx = int(data.split("_")[1])
            movies_data["movies"][idx]["watched"] = False
            save_data(movies_data)
            
            await query.edit_message_text(
                f"✅ <b>Просмотренные</b>\n\n"
                f"⬜️ Вернуто в список: <i>{movies_data['movies'][idx]['title']}</i>",
                reply_markup=build_watched_keyboard(),
                parse_mode="HTML"
            )
        
        elif data == "add":
            waiting_for_input[chat_id] = {"action": "add"}
            await query.edit_message_text(
                f"<b>Добавление фильма</b>\n\n"
                f"Напиши название фильма в ответ на это сообщение:",
                parse_mode="HTML"
            )
        
        elif data == "delete_mode":
            await query.edit_message_text(
                f"🗑 <b>Удаление фильма</b>\n\n"
                f"Выбери фильм для удаления:",
                reply_markup=build_delete_keyboard(),
                parse_mode="HTML"
            )
        
        elif data.startswith("del_"):
            idx = int(data.split("_")[1])
            deleted = movies_data["movies"].pop(idx)
            save_data(movies_data)
            
            await query.edit_message_text(
                f"🗑 Удалено: <i>{deleted['title']}</i>\n\n"
                f"<b>Список к просмотру</b>",
                reply_markup=build_main_keyboard(),
                parse_mode="HTML"
            )
        
        elif data == "watched_list":
            watched_movies = [m for m in movies_data["movies"] if m["watched"]]
            
            if not watched_movies:
                await query.answer("Пока нет просмотренных фильмов!", show_alert=True)
                return
            
            await query.edit_message_text(
                f"✅ <b>Просмотренные ({len(watched_movies)})</b>\n\n"
                f"Нажми на фильм, чтобы вернуть в список к просмотру:",
                reply_markup=build_watched_keyboard(),
                parse_mode="HTML"
            )
        
        elif data == "back_to_main":
            unwatched = len([m for m in movies_data["movies"] if not m["watched"]])
            watched = len([m for m in movies_data["movies"] if m["watched"]])
            
            await query.edit_message_text(
                f"<b>Список к просмотру</b>\n\n"
                f"⬜️ Осталось: {unwatched}\n"
                f"✅ Просмотрено: {watched}\n\n"
                f"Нажми на фильм, чтобы отметить просмотренным",
                reply_markup=build_main_keyboard(),
                parse_mode="HTML"
            )
        
        elif data == "stats":
            total = len(movies_data["movies"])
            watched = len([m for m in movies_data["movies"] if m["watched"]])
            percent = (watched / total * 100) if total > 0 else 0
            
            await query.edit_message_text(
                f"<b>Статистика</b>\n\n"
                f"Всего фильмов: {total}\n"
                f"✅ Просмотрено: {watched}\n"
                f"⬜️ Осталось: {total - watched}\n"
                f"📈 Прогресс: {percent:.1f}%",
                reply_markup=build_main_keyboard(),
                parse_mode="HTML"
            )
            
    except BadRequest as e:
        logger.error(f"Ошибка в кнопке: {e}")
        if "Topic_closed" in str(e):
            await query.answer("Ошибка: тема закрыта. Напиши боту в личку.", show_alert=True)
        else:
            await query.answer("Ошибка обработки. Попробуй еще раз.", show_alert=True)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    if chat_id in waiting_for_input and waiting_for_input[chat_id]["action"] == "add":
        del waiting_for_input[chat_id]
        
        if len(text) < 2:
            await update.message.reply_text("❌ Слишком короткое название")
            return
        
        movies_data = load_data()
        
        for m in movies_data["movies"]:
            if m["title"].lower() == text.lower():
                await update.message.reply_text(f"⚠️ '{text}' уже есть в списке!")
                return
        
        movies_data["movies"].append({"title": text, "watched": False})
        save_data(movies_data)
        
        unwatched = len([m for m in movies_data["movies"] if not m["watched"]])
        watched = len([m for m in movies_data["movies"] if m["watched"]])
        
        try:
            await update.message.reply_text(
                f"✅ Добавлено: <i>{text}</i>\n\n"
                f"<b>Список к просмотру</b>\n"
                f"⬜️ Осталось: {unwatched}\n"
                f"✅ Просмотрено: {watched}",
                reply_markup=build_main_keyboard(),
                parse_mode="HTML"
            )
        except BadRequest:
            await update.message.reply_text(
                f"✅ Добавлено: {text}\n\n"
                f"Список к просмотру\n"
                f"Осталось: {unwatched}\n"
                f"Просмотрено: {watched}",
                reply_markup=build_main_keyboard()
            )

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
