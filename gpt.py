import logging
import requests
from transformers import AutoTokenizer

import database
from config import *

tokenizer = AutoTokenizer.from_pretrained(MODEL)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="log_file.txt",
    filemode="w"
)


def count_tokens(user_request):
    tokens = tokenizer.encode(user_request)
    return len(tokens)


def is_current(user_request):
    if count_tokens(user_request) <= MAX_REQUESTS_TOKENS:
        return True
    else:
        return False


def make_promt(user_id):
    subject = database.is_value_in_table(user_id, "subject")
    level = database.is_value_in_table(user_id, "level")
    system_message = f"{system_role(subject)}. {system_level(level)}"
    json = {
        "messages": [
            {
                "role": "user",
                "content": database.is_value_in_table(user_id, "task")
            },
            {
                "role": "system",
                "content": system_message
            },
            {
                "role": "assistant",
                "content": database.is_value_in_table(user_id, "answer")
            }
        ],
        "temperature": 1,
        "max_tokens": 512,
    }
    return json


def get_response(user_id):
    try:
        promt = make_promt(user_id)
        response = requests.post(url=GPT_LOCAL_URL, headers=HEADERS, json=promt)
        content = response.json()['choices'][0]['message']['content']
        return [True, content]
    except Exception as e:
        logging.error(e)
        return [False]


def system_role(subject: str) -> str:
    if subject == 'Программирование':
        role = "Ты лучший помощник по программированию. Твоя цель - помочь твоему собеседнику со всеми вопросами связанные с програмированием. Если тема разговора перестает быть про програмирование, то скажи, что тема уходит в другое русло, и ты не можешь продолжать из-за этого разговор. Отвечай на каждый вопрос понятно и без ошибок."
    elif subject == 'Физика':
        role = "Ты лучший помощник по физике. Твоя цель - помочь твоему собеседнику со всеми вопросами связанные с физикой. Если тема разговора перестает быть про физику, то скажи, что тема уходит в другое русло, и ты не можешь продолжать из-за этого разговор. Отвечай на каждый вопрос понятно и без ошибок."
    else:
        role = "Ты обычный бот-помощник. Отвечай на вопросы кратко и верно."
    return role


def system_level(level: str) -> str:
    if level == 'Слабый':
        level = "Отвечай как для маленького ребенка, то-есть легко и понятно. Нельзя употреблять никаких терминов, лишь общепонятные слова. Если ответить не сможешь, то попроси повысить сложность ответа."
    elif level == 'Средний':
        level = "Отвечай как для школьника старших классов. Каждый сложный термин обьясняй. Задачу решай поэтапно."
    elif level == "Сложный":
        level = "Отвечай как для студента. Краткие, но понятные ответы должны быть в приоритете. Задау решай быстро и качественно."
    else:
        level = ""
    return level
