import os
import json
import datetime
import anthropic
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")

claude = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

PLACES = []
try:
    with open("moscow_places_full.json", encoding="utf-8") as f:
        PLACES = json.load(f)
    PLACES = [p for p in PLACES if (p.get("rating") or 0) >= 3.8]
    print(f"База загружена: {len(PLACES)} заведений")
except Exception as e:
    print(f"База не найдена: {e}")

CATEGORY_KEYWORDS = {
    "Ресторан": ["ресторан", "ужин", "поесть", "еда", "обед", "стейк", "суши", "пицца", "грузин", "итальян", "японск", "кавказ", "мясо", "рыба"],
    "Кафе": ["кафе", "перекус", "быстро поесть"],
    "Бар": ["бар", "коктейл", "выпить", "пиво", "вино", "бар-хоппинг", "паб", "напитк", "крафт"],
    "Кофейня": ["кофе", "кофейня", "капучино", "латте", "чай"],
    "Кондитерская": ["десерт", "торт", "кондитер", "пирожн", "выпечк", "сладк"],
    "Клуб": ["клуб", "танцевать", "вечеринк", "дискотек", "техно", "хаус", "рейв", "ночн"],
    "Антикафе": ["антикафе", "настолки", "настольные игры", "поиграть"],
    "Активность": ["квест", "боулинг", "бильярд", "картинг", "батут", "активност", "развлечен", "аттракцион"],
    "Культура": ["музей", "галерея", "театр", "выставк", "кино", "культур", "искусств", "спектакл"],
    "Баня/Спа": ["баня", "сауна", "спа", "spa", "расслабит"],
}

PRICE_KEYWORDS = {
    "бюджетно": ["бюджет", "дёшево", "дешево", "недорого", "экономн", "скромно", "до 500", "до 1000", "до 1500"],
    "дорого": ["дорогой", "дорого", "премиум", "люкс", "роскошн", "богатый", "шикарн", "лучшее", "топовый", "элитн"],
    "средне": ["средн", "нормальн", "обычн"],
}

REPEAT_KEYWORDS = ["ещё", "еще", "другой", "другое", "другие", "не то",
                   "не понравилось", "ещё варианты", "другие варианты",
                   "покажи ещё", "что ещё", "альтернатив", "другой вариант"]

def get_moscow_time():
    tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(tz)
    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    return now, days[now.weekday()], now.strftime("%H:%M")

def detect_categories(text):
    text_lower = text.lower()
    cats = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            cats.append(cat)
    return cats if cats else ["Ресторан", "Кафе", "Кофейня"]

def detect_price_level(text):
    text_lower = text.lower()
    for level, keywords in PRICE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return level
    return None

def is_repeat_request(text):
    return any(kw in text.lower() for kw in REPEAT_KEYWORDS)

def search_places(text, exclude_names=None, limit=15):
    if not PLACES:
        return []
    cats = detect_categories(text)
    price_level = detect_price_level(text)

    filtered = [p for p in PLACES if p.get("category") in cats]

    if price_level == "дорого":
        filtered = [p for p in filtered if p.get("price_level") in ["дорого", "средне-дорого"]]
    elif price_level == "бюджетно":
        filtered = [p for p in filtered if p.get("price_level") in ["бюджетно", "бюджетно-средне"]]

    if exclude_names:
        filtered = [p for p in filtered if p["name"] not in exclude_names]

    filtered.sort(key=lambda x: (-(x.get("rating") or 0), -(x.get("reviews") or 0)))
    return filtered[:limit]

def extract_shown_names(history):
    names = set()
    for msg in history:
        if msg["role"] == "assistant":
            for place in PLACES:
                if place["name"] in msg["content"]:
                    names.add(place["name"])
    return names

def format_places(places):
    if not places:
        return "Подходящих заведений не найдено."
    lines = []
    for p in places:
        line = f"- {p['name']} ({p.get('category','')})"
        if p.get("address"):
            line += f" | {p['address']}"
        if p.get("rating"):
            line += f" | ⭐{p['rating']}"
        if p.get("hours"):
            line += f" | {p['hours']}"
        if p.get("price_range"):
            line += f" | ~{p['price_range']}"
        lines.append(line)
    return "\n".join(lines)

SYSTEM_PROMPT = """Ты — Nightout. Личный консьерж по вечерам в Москве. Говоришь как умный друг — тепло, уверенно, с лёгкой иронией. Никогда не пишешь как справочник или робот.

СТИЛЬ:
- Живой и приятный текст — как будто друг рассказывает, а не перечисляет
- Компактно — каждое слово на месте, без воды
- Немного характера и настроения, без пафоса
- Никакого markdown, звёздочек, решёток — только чистый текст

ПРАВИЛА:
- Используй ТОЛЬКО места из предоставленного списка. Никаких других заведений.
- Рейтинг и часы работы — обязательно для каждого места если они есть
- Примерный ценник — всегда указывай если есть в данных
- Если рейтинг, часы или цена неизвестны — не упоминай их
- Адрес — только если есть в данных
- Бары и алкоголь — только если пользователь сам просит
- Если просят другие варианты — давай новые места, не повторяй показанные
- Учитывай бюджет пользователя при выборе мест
- Учитывай день недели и время — клубы работают в основном пт-сб

ФОРМАТ каждого места:
Название — одна живая фраза почему стоит идти
Адрес | ⭐рейтинг | часы | ~ценник

Между точками — одна строка как добраться.
В конце — одна короткая тёплая фраза напутствие."""

WELCOME = """Привет, {name}. Меня зовут Nightout.

Я знаю Москву лучше большинства москвичей — где поужинать так чтобы запомнилось, куда пойти после, как провести вечер без лишних раздумий.

Просто напиши что тебе нужно — остальное за мной."""

user_histories = {}
user_last_request = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    user_last_request[user_id] = ""
    name = update.effective_user.first_name
    await update.message.reply_text(WELCOME.format(name=name))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    text = update.message.text

    if user_id not in user_histories:
        user_histories[user_id] = []
        user_last_request[user_id] = ""

    now, day_name, time_str = get_moscow_time()
    moscow_time = f"Сейчас в Москве: {day_name}, {time_str}"

    if is_repeat_request(text):
        exclude = extract_shown_names(user_histories[user_id])
        search_query = user_last_request.get(user_id, text)
        places = search_places(search_query, exclude_names=exclude)
        note = "Пользователь просит другие варианты — не повторяй места которые уже предлагал."
    else:
        places = search_places(text)
        user_last_request[user_id] = text
        note = ""

    places_text = format_places(places)

    user_message = f"""{moscow_time}
Меня зовут {name}. Мой запрос: {text}
{note}

Доступные заведения из базы:
{places_text}

Составь сценарий используя только эти места. Начни с короткого обращения по имени и одной фразы под настроение. Затем ВЕЧЕР ГОТОВ и план. В конце — одна фраза напутствие."""

    user_histories[user_id].append({"role": "user", "content": user_message})

    if len(user_histories[user_id]) > 12:
        user_histories[user_id] = user_histories[user_id][-12:]

    try:
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=user_histories[user_id]
        )
        answer = response.content[0].text
        user_histories[user_id].append({"role": "assistant", "content": answer})
    except Exception as e:
        answer = "Что-то пошло не так. Попробуй ещё раз через минуту."
        print(f"Ошибка: {e}")

    await update.message.reply_text(answer)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Nightout бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
