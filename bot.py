import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.error import BadRequest
from flask import Flask
from threading import Thread
import httpx

# Flask для keep-alive
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

Thread(target=run_flask).start()

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# HTTP клиент для Supabase
http_client = httpx.Client(
    base_url=f"{SUPABASE_URL}/rest/v1",
    headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
)

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

def init_db():
    """Добавляем дефолтные фильмы если таблица пустая"""
    try:
        response = http_client.get("/movies?select=*")
        movies = response.json()
        
        if len(movies) == 0:
            for movie in DEFAULT_MOVIES:
                try:
                    http_client.post("/movies", json={"title": movie, "watched": False})
                except Exception as e:
                    logger.error(f"Ошибка добавления {movie}: {e}")
            logger.info("Добавлены дефолтные фильмы")
    except Exception as e:
        logger.error(f"Ошибка инициализации: {e}")

def get_all_movies():
    """Получить все фильмы"""
    try:
        response = http_client.get("/movies?select=*&order=id")
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка получения фильмов: {e}")
        return []

def add_movie(title):
    """Добавить фильм"""
    try:
        response = http_client.post("/movies", json={"title": title, "watched": False})
        return response.status_code == 201
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            return False  # Дубликат
        logger.error(f"Ошибка добавления: {e}")
        return False

def delete_movie(movie_id):
    """Удалить фильм"""
    try:
        http_client.delete(f"/movies?id=eq.{movie_id}")
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")

def toggle_watched(movie_id, watched):
    """Переключить статус просмотра"""
    try:
        http_client.patch(f"/movies?id=eq.{movie_id}", json={"watched": watched})
    except Exception as e:
        logger.error(f"Ошибка обновления: {e}")

def build_main_keyboard():
    """Клавиатура для непросмотренных фильмов"""
    movies = get_all_movies()
    keyboard = []
    
    unwatched = [(m["id"], m) for m in movies if not m["watched"]]
    
    for movie_id, movie in unwatched:
        keyboard.append([
            InlineKeyboardButton(f"⬜️ {movie['title'][:40]}{'...' if len(movie['title']) > 40 else ''}", callback_data=f"toggle_{movie_id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("➕ Добавить фильм", callback_data="add"),
        InlineKeyboardButton("🗑 Удалить фильм", callback_data="delete_mode")
    ])
    
    watched_count = len([m for m in movies if m["watched"]])
    keyboard.append([
        InlineKeyboardButton(f"✅ Просмотренные ({watched_count})", callback_data="watched_list"),
        InlineKeyboardButton("📊 Статистика", callback_data="stats")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def build_watched_keyboard():
    """Клавиатура для просмотренных фильмов"""
    movies = get_all_movies()
    keyboard = []
    
    for movie in movies:
        if movie["watched"]:
            keyboard.append([
                InlineKeyboardButton(f"✅ {movie['title'][:40]}{'...' if len(movie['title']) > 40 else ''}", callback_data=f"unwatch_{movie['id']}")
            ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 Назад к списку", callback_data="back_to_main")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def build_delete_keyboard():
    """Клавиатура для удаления"""
    movies = get_all_movies()
    keyboard = []
    
    for movie in movies:
        emoji = "✅" if movie["watched"] else "⬜️"
        keyboard.append([
            InlineKeyboardButton(f"🗑 {emoji} {movie['title'][:35]}{'...' if len(movie['title']) > 35 else ''}", callback_data=f"del_{movie['id']}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Отмена", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    movies = get_all_movies()
    unwatched = len([m for m in movies if not m["watched"]])
    watched = len([m for m in movies if m["watched"]])
    
    try:
        await update.message.reply_text(
            f"🎬 <b>Список к просмотру</b>\n\n"
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
            await update.message.reply_text("Ошибка загрузки списка.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id
    
    try:
        if data.startswith("toggle_"):
            movie_id = int(data.split("_")[1])
            toggle_watched(movie_id, True)
            movies = get_all_movies()
            movie = next((m for m in movies if m["id"] == movie_id), None)
            
            await query.edit_message_text(
                f"🎬 <b>Список к просмотру</b>\n\n"
                f"✅ Отмечено: <i>{movie['title'] if movie else 'Фильм'}</i>",
                reply_markup=build_main_keyboard(),
                parse_mode="HTML"
            )
        
        elif data.startswith("unwatch_"):
            movie_id = int(data.split("_")[1])
            toggle_watched(movie_id, False)
            movies = get_all_movies()
            movie = next((m for m in movies if m["id"] == movie_id), None)
            
            await query.edit_message_text(
                f"✅ <b>Просмотренные</b>\n\n"
                f"⬜️ Вернуто в список: <i>{movie['title'] if movie else 'Фильм'}</i>",
                reply_markup=build_watched_keyboard(),
                parse_mode="HTML"
            )
        
        elif data == "add":
            waiting_for_input[chat_id] = {"action": "add"}
            await query.edit_message_text(
                f"📝 <b>Добавление фильма</b>\n\n"
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
            movie_id = int(data.split("_")[1])
            movies = get_all_movies()
            movie = next((m for m in movies if m["id"] == movie_id), None)
            delete_movie(movie_id)
            
            await query.edit_message_text(
                f"🗑 Удалено: <i>{movie['title'] if movie else 'Фильм'}</i>\n\n"
                f"🎬 <b>Список к просмотру</b>",
                reply_markup=build_main_keyboard(),
                parse_mode="HTML"
            )
        
        elif data == "watched_list":
            movies = get_all_movies()
            watched_movies = [m for m in movies if m["watched"]]
            
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
            movies = get_all_movies()
            unwatched = len([m for m in movies if not m["watched"]])
            watched = len([m for m in movies if m["watched"]])
            
            await query.edit_message_text(
                f"🎬 <b>Список к просмотру</b>\n\n"
                f"⬜️ Осталось: {unwatched}\n"
                f"✅ Просмотрено: {watched}\n\n"
                f"Нажми на фильм, чтобы отметить просмотренным",
                reply_markup=build_main_keyboard(),
                parse_mode="HTML"
            )
        
        elif data == "stats":
            movies = get_all_movies()
            total = len(movies)
            watched = len([m for m in movies if m["watched"]])
            percent = (watched / total * 100) if total > 0 else 0
            
            await query.edit_message_text(
                f"📊 <b>Статистика</b>\n\n"
                f"Всего фильмов: {total}\n"
                f"✅ Просмотрено: {watched}\n"
                f"⬜️ Осталось: {total - watched}\n"
                f"📈 Прогресс: {percent:.1f}%",
                reply_markup=build_main_keyboard(),
                parse_mode="HTML"
            )
            
    except BadRequest as e:
        logger.error(f"Ошибка в кнопке: {e}")
        await query.answer("Ошибка обработки. Попробуй еще раз.", show_alert=True)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    if chat_id in waiting_for_input and waiting_for_input[chat_id]["action"] == "add":
        del waiting_for_input[chat_id]
        
        if len(text) < 2:
            await update.message.reply_text("❌ Слишком короткое название")
            return
        
        if add_movie(text):
            movies = get_all_movies()
            unwatched = len([m for m in movies if not m["watched"]])
            watched = len([m for m in movies if m["watched"]])
            
            try:
                await update.message.reply_text(
                    f"✅ Добавлено: <i>{text}</i>\n\n"
                    f"🎬 <b>Список к просмотру</b>\n"
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
        else:
            await update.message.reply_text(f"⚠️ '{text}' уже есть в списке!")

def main():
    init_db()
    
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
