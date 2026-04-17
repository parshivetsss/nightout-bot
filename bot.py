import os
import json
import datetime
import math
import anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

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

# Районы Москвы с координатами центра
DISTRICTS = {
    "Центр": (55.7558, 37.6176),
    "Арбат / Хамовники": (55.7425, 37.5865),
    "Патриаршие / Тверская": (55.7650, 37.5960),
    "Китай-город / Таганка": (55.7520, 37.6380),
    "Покровка / Чистые пруды": (55.7590, 37.6430),
    "Замоскворечье / Пятницкая": (55.7380, 37.6270),
    "Красная Пресня / Сити": (55.7520, 37.5570),
    "Сокольники / Преображенская": (55.7900, 37.6780),
    "ВДНХ / Алексеевская": (55.8230, 37.6400),
    "Измайлово / Партизанская": (55.7900, 37.7500),
    "Юго-Запад / Ленинский": (55.6900, 37.5500),
    "Юг / Варшавское шоссе": (55.6600, 37.6200),
    "Восток / Люблино": (55.6800, 37.7600),
    "Север / Войковская": (55.8200, 37.4900),
    "Северо-Запад / Строгино": (55.8000, 37.3900),
}

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
    "бюджетно": ["бюджет", "дёшево", "дешево", "недорого", "экономн", "скромно"],
    "дорого": ["дорогой", "дорого", "премиум", "люкс", "роскошн", "богатый", "шикарн", "элитн"],
}

PRICE_REQUEST_KEYWORDS = ["средний чек", "сколько стоит", "цены", "ценник", "бюджет", "сколько потрачу"]

REPEAT_KEYWORDS = ["ещё", "еще", "другой", "другое", "другие", "не то",
                   "не понравилось", "ещё варианты", "другие варианты",
                   "покажи ещё", "альтернатив", "другой вариант"]

FORMAT_BUTTONS = [
    [
        InlineKeyboardButton("Свидание", callback_data="format_свидание"),
        InlineKeyboardButton("Друзья", callback_data="format_друзья"),
    ],
    [
        InlineKeyboardButton("Клубная ночь", callback_data="format_клуб"),
        InlineKeyboardButton("Культурный вечер", callback_data="format_культура"),
    ],
    [
        InlineKeyboardButton("День рождения", callback_data="format_др"),
        InlineKeyboardButton("Просто погулять", callback_data="format_прогулка"),
    ],
]

DISTRICT_BUTTONS = [
    [
        InlineKeyboardButton("Центр", callback_data="district_Центр"),
        InlineKeyboardButton("Арбат / Хамовники", callback_data="district_Арбат / Хамовники"),
    ],
    [
        InlineKeyboardButton("Патриаршие / Тверская", callback_data="district_Патриаршие / Тверская"),
        InlineKeyboardButton("Китай-город / Таганка", callback_data="district_Китай-город / Таганка"),
    ],
    [
        InlineKeyboardButton("Покровка / Чистые пруды", callback_data="district_Покровка / Чистые пруды"),
        InlineKeyboardButton("Замоскворечье", callback_data="district_Замоскворечье / Пятницкая"),
    ],
    [
        InlineKeyboardButton("Красная Пресня / Сити", callback_data="district_Красная Пресня / Сити"),
        InlineKeyboardButton("ВДНХ / Алексеевская", callback_data="district_ВДНХ / Алексеевская"),
    ],
    [
        InlineKeyboardButton("Север", callback_data="district_Север / Войковская"),
        InlineKeyboardButton("Юг", callback_data="district_Юг / Варшавское шоссе"),
    ],
    [
        InlineKeyboardButton("Юго-Запад", callback_data="district_Юго-Запад / Ленинский"),
        InlineKeyboardButton("Другой район — напишу сам", callback_data="district_другой"),
    ],
]

def get_moscow_time():
    tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(tz)
    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    return now, days[now.weekday()], now.strftime("%H:%M")

def get_season():
    month = datetime.datetime.now().month
    if month in [12, 1, 2]:
        return "зима", "Зимой особенно хороши тёплые камерные места, рестораны с живым огнём и камином, горячие напитки."
    elif month in [3, 4, 5]:
        return "весна", "Весной стоит искать первые веранды которые открываются, парки и прогулочные маршруты."
    elif month in [6, 7, 8]:
        return "лето", "Летом идеальны веранды, крыши, парки и места у воды. Приоритет — заведения с открытым пространством."
    else:
        return "осень", "Осенью хороши уютные места с тёплым светом, пледами на верандах и горячими напитками."

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

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

def is_price_request(text):
    return any(kw in text.lower() for kw in PRICE_REQUEST_KEYWORDS)

def search_places(text, district=None, exclude_names=None, limit=15):
    if not PLACES:
        return []

    cats = detect_categories(text)
    price_level = detect_price_level(text)
    filtered = [p for p in PLACES if p.get("category") in cats]

    if price_level == "дорого":
        filtered = [p for p in filtered if p.get("price_level") in ["дорого", "средне-дорого"]]
    elif price_level == "бюджетно":
        filtered = [p for p in filtered if p.get("price_level") in ["бюджетно", "бюджетно-средне"]]

    # Сортируем по близости к выбранному району
    if district and district in DISTRICTS:
        dlat, dlon = DISTRICTS[district]
        def sort_key(p):
            try:
                dist = haversine(dlat, dlon, float(p.get("lat", 0)), float(p.get("lon", 0)))
                return (dist, -(p.get("rating") or 0))
            except:
                return (999, -(p.get("rating") or 0))
        filtered.sort(key=sort_key)
    else:
        filtered.sort(key=lambda x: (-(x.get("rating") or 0), -(x.get("reviews") or 0)))

    if exclude_names:
        filtered = [p for p in filtered if p["name"] not in exclude_names]

    return filtered[:limit]

def extract_shown_names(history):
    names = set()
    for msg in history:
        if msg["role"] == "assistant":
            for place in PLACES:
                if place["name"] in msg["content"]:
                    names.add(place["name"])
    return names

def format_places(places, show_price=False):
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
        if show_price and p.get("price_range"):
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
- Используй места из предоставленного списка как основу
- Дополняй своими знаниями о Москве — добавляй известные заведения которые знаешь хорошо. Пиши только то в чём уверен: название, адрес если знаешь точно, метро, рейтинг если знаешь реальную цифру. Если не уверен в деталях — пиши только название и район.
- Рейтинг и часы работы — всегда указывай если есть в данных
- Средний чек — только если пользователь сам спросил
- Бары и алкоголь — только если пользователь сам просит
- Если просят другие варианты — давай новые места, не повторяй показанные
- Учитывай сезон при выборе мест — летом веранды и открытые пространства, зимой тёплые камерные места
- Учитывай день недели и время

ФОРМАТ каждого места:
Название — одна живая фраза почему стоит идти
Адрес | ⭐рейтинг | часы работы

Между точками — одна строка как добраться.
В конце — одна короткая тёплая фраза напутствие."""

WELCOME = """Привет, {name}. Меня зовут Nightout.

Я знаю Москву лучше большинства москвичей — где поужинать так чтобы запомнилось, куда пойти после, как провести вечер без лишних раздумий.

Выбери формат вечера — и я составлю план:"""

user_histories = {}
user_last_request = {}
user_district = {}
user_format = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    user_last_request[user_id] = ""
    user_district[user_id] = None
    user_format[user_id] = None
    name = update.effective_user.first_name
    await update.message.reply_text(
        WELCOME.format(name=name),
        reply_markup=InlineKeyboardMarkup(FORMAT_BUTTONS)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("format_"):
        fmt = data.replace("format_", "")
        user_format[user_id] = fmt
        await query.edit_message_text(
            f"Отлично. В каком районе планируешь вечер?",
            reply_markup=InlineKeyboardMarkup(DISTRICT_BUTTONS)
        )

    elif data.startswith("district_"):
        district = data.replace("district_", "")
        if district == "другой":
            user_district[user_id] = None
            await query.edit_message_text("Напиши свой район или станцию метро — и я подберу места рядом.")
        else:
            user_district[user_id] = district
            fmt = user_format.get(user_id, "вечер")
            await query.edit_message_text(
                f"Район — {district}, формат — {fmt}. Есть пожелания по бюджету, компании или кухне? Или сразу составить план?"
            )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    text = update.message.text

    if user_id not in user_histories:
        user_histories[user_id] = []
        user_last_request[user_id] = ""
        user_district[user_id] = None
        user_format[user_id] = None

    now, day_name, time_str = get_moscow_time()
    moscow_time = f"Сейчас в Москве: {day_name}, {time_str}"
    season, season_tip = get_season()

    district = user_district.get(user_id)
    fmt = user_format.get(user_id)
    show_price = is_price_request(text)

    # Если написали район текстом
    for d in DISTRICTS:
        if d.lower() in text.lower() or any(part.lower() in text.lower() for part in d.split("/")):
            user_district[user_id] = d
            district = d
            break

    if is_repeat_request(text):
        exclude = extract_shown_names(user_histories[user_id])
        search_query = user_last_request.get(user_id, text)
        places = search_places(search_query, district=district, exclude_names=exclude)
        note = "Пользователь просит другие варианты — не повторяй места которые уже предлагал."
    else:
        full_query = f"{fmt or ''} {text}".strip()
        places = search_places(full_query, district=district)
        user_last_request[user_id] = full_query
        note = ""

    price_note = "Пользователь спросил о ценах — укажи примерный ценник." if show_price else "Средний чек не указывай."
    district_note = f"Пользователь хочет вечер в районе: {district}. Приоритет — места рядом с этим районом." if district else ""
    format_note = f"Формат вечера: {fmt}." if fmt else ""

    places_text = format_places(places, show_price=show_price)

    user_message = f"""{moscow_time}
Сезон: {season}. {season_tip}
Меня зовут {name}. Мой запрос: {text}
{format_note}
{district_note}
{note}
{price_note}

Доступные заведения из базы:
{places_text}

Составь сценарий. Начни с короткого обращения по имени и одной фразы под настроение. Затем ВЕЧЕР ГОТОВ и план. В конце — одна фраза напутствие."""

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
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Nightout бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
