import json
import time
from datetime import datetime, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

# Загрузка конфигурации
with open('config.json', 'r') as f:
    config = json.load(f)

BOT_TOKEN = config['bot_token']
ADMIN_ID = config['admin_id']
TIME_ZONE = pytz.timezone(config['time_zone'])
DAILY_QUIZ_TIME = config['daily_quiz_time']
REMINDER_TIME = config['reminder_time']
HINT_INTERVAL_MINUTES = config['hint_interval_minutes']
MAX_HINTS = config['max_hints']

# Загрузка данных
def load_data():
    try:
        with open('data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(data):
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=4)

def load_users():
    try:
        with open('users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users(users):
    with open('users.json', 'w') as f:
        json.dump(users, f, indent=4)

# Базовые функции
def get_current_date():
    return datetime.now(TIME_ZONE).strftime('%Y-%m-%d')

def is_friday_bonus(date_str):
    date = datetime.strptime(date_str, '%Y-%m-%d')
    return date.weekday() == 4  # Пятница

# Обработчики команд
def start(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    users = load_users()
    if user_id not in users:
        users[user_id] = {"coins": 0, "last_answer_date": "", "answered_today": False, "used_hint": False}
        save_users(users)
    update.message.reply_text("Привет, друг! 🎉 Ты готов решать крутые загадки?")

def send_daily_quiz(context: CallbackContext):
    current_date = get_current_date()
    data = load_data()
    users = load_users()

    if current_date in data:
        quiz = data[current_date]
        for user_id, user_data in users.items():
            if not user_data.get("answered_today", False):
                try:
                    context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"💡 Загадка дня:\n\n{quiz['question']}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Подсказка", callback_data="hint")]])
                    )
                except Exception as e:
                    print(f"Не удалось отправить загадку пользователю {user_id}: {e}")
    else:
        print(f"Загадка для {current_date} не найдена!")

def reminder(context: CallbackContext):
    users = load_users()
    for user_id in users:
        try:
            context.bot.send_message(
                chat_id=int(user_id),
                text="⏰ Через 10 минут появится новая загадка!"
            )
        except Exception as e:
            print(f"Не удалось отправить напоминание пользователю {user_id}: {e}")

def check_answer(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    users = load_users()
    current_date = get_current_date()
    data = load_data()

    if current_date in data:
        quiz = data[current_date]
        answer = quiz["answer"].lower().replace(" ", "")
        user_answer = update.message.text.lower().replace(" ", "")

        if user_answer == answer:
            coins = 10 - len([u for u in users if users[u].get("last_answer_date") == current_date]) + 1
            if coins < 1:
                coins = 1
            if is_friday_bonus(current_date):
                coins += 3

            users[user_id]["coins"] += coins
            users[user_id]["last_answer_date"] = current_date
            users[user_id]["answered_today"] = True
            users[user_id]["used_hint"] = False
            save_users(users)

            update.message.reply_text(f"🎉 Верно! Ты получил {coins} НИТИкоинов!")
        else:
            update.message.reply_text("❌ Неверно! Попробуй еще раз.")
    else:
        update.message.reply_text("Загадка на сегодня еще не добавлена.")

def show_rating(update: Update, context: CallbackContext):
    users = load_users()
    sorted_users = sorted(users.items(), key=lambda x: x[1]['coins'], reverse=True)[:10]

    rating_text = "📊 Рейтинг игроков:\n"
    for i, (user_id, user_data) in enumerate(sorted_users, 1):
        rating_text += f"{i}. Пользователь {user_id}: {user_data['coins']} НИТИкоинов\n"

    update.message.reply_text(rating_text)

def my_coins(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    users = load_users()

    if user_id in users:
        coins = users[user_id]["coins"]
        update.message.reply_text(f"💰 У тебя {coins} НИТИкоинов!")
    else:
        update.message.reply_text("У тебя пока нет НИТИкоинов 😔")

def hint(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    user_id = str(query.from_user.id)
    users = load_users()
    current_date = get_current_date()
    data = load_data()

    if current_date in data:
        quiz = data[current_date]
        hints = quiz["hints"]
        user = users.get(user_id, {})

        if user.get("used_hint", False):
            query.edit_message_text("Ты уже использовал подсказку сегодня!")
            return

        hint_index = int((datetime.now(TIME_ZONE) - datetime.strptime(current_date, '%Y-%m-%d')).total_seconds() // (HINT_INTERVAL_MINUTES * 60))
        if hint_index >= len(hints):
            query.edit_message_text("Все подсказки уже использованы!")
        else:
            users[user_id]["used_hint"] = True
            save_users(users)
            query.edit_message_text(f"💭 Подсказка: {hints[hint_index]}")
    else:
        query.edit_message_text("Подсказка недоступна!")

# Админские команды
def admin_stats(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("У тебя нет прав администратора!")
        return

    users = load_users()
    sorted_users = sorted(users.items(), key=lambda x: x[1]['coins'], reverse=True)

    stats_text = "📊 Расширенный рейтинг:\n"
    for i, (user_id, user_data) in enumerate(sorted_users, 1):
        stats_text += f"{i}. Пользователь {user_id}: {user_data['coins']} НИТИкоинов\n"

    update.message.reply_text(stats_text)

def add_quiz(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("У тебя нет прав администратора!")
        return

    args = context.args
    if len(args) < 3:
        update.message.reply_text("Использование: /addquiz YYYY-MM-DD вопрос ответ подсказка1 подсказка2 ...")
        return

    date = args[0]
    question = args[1]
    answer = args[2]
    hints = args[3:]

    data = load_data()
    data[date] = {
        "question": question,
        "answer": answer,
        "hints": hints,
        "friday_bonus": is_friday_bonus(date)
    }
    save_data(data)

    update.message.reply_text(f"Загадка для {date} успешно добавлена!")

def main():
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Команды
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("rating", show_rating))
    dispatcher.add_handler(CommandHandler("mycoins", my_coins))
    dispatcher.add_handler(CallbackQueryHandler(hint))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, check_answer))

    # Админские команды
    dispatcher.add_handler(CommandHandler("adminstats", admin_stats))
    dispatcher.add_handler(CommandHandler("addquiz", add_quiz, pass_args=True))

    # Ежедневные задачи
    job_queue = updater.job_queue
    daily_quiz_time = TIME_ZONE.localize(datetime.strptime(DAILY_QUIZ_TIME, "%H:%M"))
    reminder_time = TIME_ZONE.localize(datetime.strptime(REMINDER_TIME, "%H:%M"))

    job_queue.run_daily(send_daily_quiz, daily_quiz_time.time(), days=(0, 1, 2, 3, 4, 5, 6))
    job_queue.run_daily(reminder, reminder_time.time(), days=(0, 1, 2, 3, 4, 5, 6))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
