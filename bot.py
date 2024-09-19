import telebot
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime


EVENTS_FILE = 'events.json'
USERS_FILE = 'users.json'
KEY_FILE = 'key.txt'


def load_api_token():
    with open(KEY_FILE, 'r') as f:
        return f.read().strip()



API_TOKEN = load_api_token()
bot = telebot.TeleBot(API_TOKEN)


def load_users():
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4, ensure_ascii=False)


def load_events():
    try:
        with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_events(events):
    with open(EVENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=4, ensure_ascii=False)


@bot.message_handler(commands=['start'])
def start(message):
    # Добавление пользователя в список
    users = load_users()
    user_id = message.from_user.id
    if user_id not in users:
        users.append(user_id)
        save_users(users)

    markup = InlineKeyboardMarkup()
    create_event_btn = InlineKeyboardButton("Создать событие", callback_data='create_event')
    join_event_btn = InlineKeyboardButton("Записаться в очередь", callback_data='join_event')
    markup.add(create_event_btn, join_event_btn)
    bot.send_message(message.chat.id, "Привет! Выберите действие:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data == 'create_event':
        msg = bot.send_message(call.message.chat.id, "Введите название события:")
        bot.register_next_step_handler(msg, get_event_name)
    elif call.data == 'join_event':
        show_events_list(call.message)
    elif call.data.startswith('view_event_'):
        event_id = call.data.split('_')[-1]
        show_event_page(call, event_id)
    elif call.data.startswith('join_'):
        event_id = call.data.split('_')[-1]
        join_event(call, event_id)
    elif call.data.startswith('leave_'):
        event_id = call.data.split('_')[-1]
        leave_event(call, event_id)


def get_event_name(message):
    event_name = message.text
    msg = bot.send_message(message.chat.id, "Введите дату и время события в формате ГГГГ-ММ-ДД ЧЧ:ММ:")
    bot.register_next_step_handler(msg, get_event_datetime, event_name)


def get_event_datetime(message, event_name):
    try:
        event_datetime = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        events = load_events()
        event_id = str(len(events) + 1)
        creator_username = message.from_user.username or "Без @юзернейма"
        events[event_id] = {
            'name': event_name,
            'datetime': event_datetime.strftime("%Y-%m-%d %H:%M"),
            'creator': creator_username,
            'participants': []
        }
        save_events(events)
        bot.send_message(message.chat.id,
                         f"Событие '{event_name}' успешно создано на {event_datetime}.\nСоздатель: @{creator_username}.")

        # Рассылка уведомлений всем пользователям
        users = load_users()
        for user_id in users:
            try:
                bot.send_message(user_id,
                                 f"Создано новое событие: '{event_name}' на {event_datetime}.\nСоздатель: @{creator_username}.")
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат даты. Попробуйте ещё раз.")


def show_events_list(message):
    events = load_events()
    if events:
        markup = InlineKeyboardMarkup()
        for event_id, event in events.items():
            markup.add(InlineKeyboardButton(event['name'], callback_data=f'view_event_{event_id}'))
        bot.send_message(message.chat.id, "Выберите событие:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Нет доступных событий для записи.")


def show_event_page(call, event_id):
    events = load_events()
    event = events.get(event_id)
    if event:
        markup = InlineKeyboardMarkup()
        join_btn = InlineKeyboardButton("Записаться", callback_data=f'join_{event_id}')
        leave_btn = InlineKeyboardButton("Отписаться", callback_data=f'leave_{event_id}')
        markup.add(join_btn, leave_btn)

        # Отображение участников
        participants_list = '\n'.join(
            [f"{idx + 1}. @{p}" for idx, p in enumerate(event['participants'])]) or "Нет участников"
        bot.edit_message_text(
            text=f"Название: {event['name']}\nДата и время: {event['datetime']}\nСоздатель: @{event['creator']}\nУчастники:\n{participants_list}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
    else:
        bot.send_message(call.message.chat.id, "Событие не найдено.")


def join_event(call, event_id):
    events = load_events()
    event = events.get(event_id)
    if event:
        user_id = call.from_user.id
        username = call.from_user.username or "Без @юзернейма"
        if user_id not in event['participants']:
            event['participants'].append(username)
            save_events(events)
            position = len(event['participants'])
            bot.send_message(call.message.chat.id,
                             f"Вы успешно записаны на событие '{event['name']}'. Ваш номер в очереди: {position}.")
            show_event_page(call, event_id)
        else:
            bot.send_message(call.message.chat.id, "Вы уже записаны на это событие.")
    else:
        bot.send_message(call.message.chat.id, "Событие не найдено.")


def leave_event(call, event_id):
    events = load_events()
    event = events.get(event_id)
    if event:
        user_id = call.from_user.id
        username = call.from_user.username or "Без @юзернейма"
        if username in event['participants']:
            event['participants'].remove(username)
            save_events(events)
            bot.send_message(call.message.chat.id, f"Вы успешно отписались от события '{event['name']}'.")
            show_event_page(call, event_id)
        else:
            bot.send_message(call.message.chat.id, "Вы не были записаны на это событие.")
    else:
        bot.send_message(call.message.chat.id, "Событие не найдено.")


bot.polling(none_stop=True)
