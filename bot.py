import database
import gpt
import logging
from telebot.types import Message
import telebot
from config import BOT_TOKEN

database.create_db()
database.create_table()

bot = telebot.TeleBot(BOT_TOKEN)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="log_file.txt",
    filemode="w"
)
help_message = (
    "Я бот-помощник. Сперва тебе надо выбрать тему и сложность общения. Всё выбирается с помощью команды /settings и изменить можно в любое время.\n"
    "Перед каждым вопросом нужно писать 'Задать вопрос ИИ'. Учитывайте, что при смене темы в настройках, история общения с нейросетью стирается.\n"
    "Если нейросеть не смогла до конца написать ответ, то попроси её продолжить объснение.")

subjects = ["Физика", "Программирование"]
levels = ["Простой", "Средний", "Сложный"]


def create_keyboard(buttons_list: list) -> telebot.types.ReplyKeyboardMarkup:
    keyboard = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(*buttons_list)
    return keyboard


@bot.message_handler(commands=['start'])
def start(message: Message):
    user_id = message.from_user.id
    logging.info(f"{message.from_user.username} c id {message.from_user.id} присоединился к нам!")
    if not database.is_value_in_table(user_id, user_id):
        database.insert_row(column_name='(user_id, subject, level, task, answer)',
                            values=f'({user_id}, NULL, NULL, NULL, "Решим задачу по шагам:")')
    bot.send_message(
        user_id,
        f"Привет, {message.from_user.username}! Я бот-помощник, попытаюсь ответить на все твои вопросы по теме физики или программирования.\n"
        "Мои ответы могут быть прописаны не полностью - в этом случае ты можешь написать 'продолжить'.\n"
        "Сперва прошу ознакомиться с тем, как надо взаимодействовать с ботом: /help.",
        reply_markup=create_keyboard(["Выбрать сложность/тему", "/help"]),
    )


@bot.message_handler(commands=['help'])
def support(message):
    bot.send_message(message.chat.id,
                     text=help_message,
                     reply_markup=create_keyboard(["Задать вопрос ИИ", "Выбрать сложность/тему"]))


@bot.message_handler(func=lambda message: message.text in ["Выбрать сложность/тему", "/settings"])
def open_settings(message: Message):
    bot.send_message(message.from_user.id,
                     "Выберите, что хотите изменить:",
                     reply_markup=create_keyboard(["Тема общения", "Сложность ответа"]))
    bot.register_next_step_handler(message, chouse_settings)


def chouse_settings(message: Message):
    if message.text == "Тема общения":
        set_subject(message)
    elif message.text == "Сложность ответа":
        set_level(message)


def set_subject(message):
    bot.send_message(message.from_user.id,
                     text="Выберите тему диалога из представленных ниже вариантов:",
                     reply_markup=create_keyboard(["Физика", "Программирование"]))
    bot.register_next_step_handler(message, get_subject)


def get_subject(message):
    database.update_row_value(message.chat.id, "subject", message.text)
    database.update_row_value(message.chat.id, "task", "NULL")
    database.update_row_value(message.chat.id, "answer", "NULL")
    bot.send_message(message.chat.id, "Отлично, тема сохранилась.",
                     reply_markup=create_keyboard(['Выбрать сложность/тему', 'Задать вопрос ИИ']))
    return


def set_level(message):
    bot.send_message(message.from_user.id,
                     text="Выберите сложность ответа. \n"
                          "Сложный ответ ориентирован на людей, которые хорошо понимают в теме,  в то время как простой будет для людей, далеко знакомых от темы вопроса.",
                     reply_markup=create_keyboard(levels))
    bot.register_next_step_handler(message, get_level)


def get_level(message):
    database.update_row_value(message.chat.id, column_name="level", new_value=message.text)
    return


@bot.message_handler(func=lambda message: message.text in ["Задать вопрос ИИ", "/solve_task"])
def choose_requests(message: Message):
    bot.send_message(message.from_user.id,
                     "Введи любое сообщение. Оно будет распознано как новое задание. Если до этого было какое-то незавершенное задание, то оно будет завершено."
                     "\nМожешь попросить продолжить решение, нажав 'Продолжить объяснение' или начать новое, нажав 'Задать вопрос ИИ'",
                     reply_markup=create_keyboard(
                         ['Продолжить объяснение', "Задать вопрос ИИ", "Выбрать сложность/тему"]))
    bot.register_next_step_handler(message, add_task)


def add_task(message):
    user_id = message.from_user.id
    if message.content_type != "text":
        bot.send_message(user_id, "Необходимо отправить именно текстовое сообщение")
        bot.register_next_step_handler(message, choose_requests)
        return
    if database.is_value_in_table(user_id, "task"):
        bot.send_message(user_id, "Решение предыдущей задачи завершено. Тема и сложность остались прежними.")
    database.update_row_value(user_id, "answer", "Реши задачу по шагам: ")
    user_request = message.text
    if gpt.is_current(user_request):
        database.update_row_value(user_id, "task", user_request)
        if check(message):
            bot.send_message(user_id, "Новая задача добавлена и нейросети скоро тебе ответит!")
            continue_solve(message)
    else:
        bot.send_message(user_id, "Запрос превышает количество символов\nУкоротите запрос")
        bot.register_next_step_handler(message, choose_requests)


def check(message):
    user_id = message.from_user.id
    if not database.is_value_in_table(user_id, "task"):
        bot.send_message(user_id, "Сначала напиши запрос.", reply_markup=create_keyboard(["Задать вопрос ИИ"]))
        logging.warning(f"У пользователя с id {user_id} не добавлено задание")
        return False
    if (database.is_value_in_table(user_id, "subject") not in subjects
            or database.is_value_in_table(user_id, "level") not in levels):
        bot.send_message(user_id, "Выбери для начала тему/сложность ответа.",
                         reply_markup=create_keyboard(['Выбрать сложность/тему']))
        logging.warning(f"У пользователя с id {user_id} не добавлены значения в настройках.")
        return False
    return True


@bot.message_handler(func=lambda message: message.text in ["Продолжить объяснение"])
def continue_solve(message):
    user_id = message.from_user.id
    if check(message):
        logging.info(f"{message.from_user.username} c id {user_id} написал(a) нейросети: '{message.text}'")
        response = gpt.get_response(user_id)
        if response[0]:
            if response[1] == "":
                bot.send_message(user_id, "Ответ был полность получен.",
                                 reply_markup=create_keyboard(['Задать вопрос ИИ']))
                bot.register_next_step_handler(message, choose_requests)
            else:
                answer = database.is_value_in_table(user_id, "answer")
                answer += response[1]
                database.update_row_value(user_id, "answer", answer)
                bot.send_message(user_id, f"<i>{response[1]}</i>",
                                 reply_markup=create_keyboard(["Продолжить объяснение", "/solve_task", "/set_level"]),
                                 parse_mode="HTML")

        else:
            bot.send_message(user_id,
                             "Произошла ошибка. Чтобы понять, в чем причина перейди в режим debug или пропиши /help и сделай все по шагам.",
                             reply_markup=create_keyboard(["/debug", "/help"]))


@bot.message_handler(commands=["debug"])
def debug(message):
    user_id = message.from_user.id
    logging.info(f"{message.from_user.id} запросил дебаг-файл")
    with open("log_file.txt", "rb") as f:
        bot.send_document(user_id, f)


@bot.message_handler(commands=["statistics"])
def statistics(message):
    user_id = message.from_user.id
    answer = "Вот сколько пользователей задало вопрос по каждой теме: \n"
    logging.info(f"{message.from_user.id} запросил статистику")
    res = database.show_column("subject")
    cnt = {lang: 0 for lang in subjects}
    for row in res:
        cnt[row[0]] += 1
    cnt = sorted(cnt.items(), key=lambda item: item[1], reverse=True)
    for i in cnt:
        answer += f"{i[0]}:    {i[1]} \n"
    bot.send_message(user_id, answer)


@bot.message_handler()
def else_message(message: Message):
    bot.send_message(message.from_user.id, "Выберите вариант из предложенных снизу:")


if __name__ == "__main__":
    logging.info("Бот запущен")
    bot.infinity_polling()
