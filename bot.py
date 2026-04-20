import os
import json
import datetime
import math
import random
import asyncio
import anthropic
import urllib.request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import JobQueue

def get_weather():
    """Получаем погоду в Москве через wttr.in (бесплатно, без API ключа)"""
    try:
        url = "https://wttr.in/Moscow?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        current = data["current_condition"][0]
        temp = current["temp_C"]
        desc = current["weatherDesc"][0]["value"].lower()
        feels = current["FeelsLikeC"]
        rain = int(current.get("precipMM", "0").split(".")[0]) if "." in current.get("precipMM","0") else int(current.get("precipMM","0"))

        is_rain = any(w in desc for w in ["rain","drizzle","shower","thunder","sleet","snow","blizzard"])
        is_cold = int(temp) < 5
        is_hot = int(temp) > 25
        is_wind = int(current.get("windspeedKmph","0")) > 30

        weather_note = f"Погода в Москве: {temp}°C, ощущается как {feels}°C, {desc}."
        if is_rain:
            weather_note += " Идёт дождь — предлагай только крытые места, никаких веранд и прогулок."
        elif is_cold:
            weather_note += " Холодно — предлагай тёплые места с уютной атмосферой."
        elif is_hot:
            weather_note += " Жарко — приоритет верандам, паркам и местам с кондиционером."
        if is_wind:
            weather_note += " Сильный ветер — избегай открытых пространств."

        weather_emoji = "🌧" if is_rain else ("❄️" if is_cold else ("☀️" if is_hot else "🌤"))
        return weather_note, weather_emoji, temp, is_rain
    except Exception as e:
        print(f"Погода недоступна: {e}")
        return "", "🌤", "?", False

# Хранение пользователей для уведомлений
user_registry = {}

def register_user(user_id, name):
    user_registry[user_id] = {"name": name, "id": user_id}
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

DISTRICTS = {
    "Центр": (55.7558, 37.6176),
    "Арбат / Хамовники": (55.7425, 37.5865),
    "Патриаршие / Тверская": (55.7650, 37.5960),
    "Китай-город / Таганка": (55.7520, 37.6380),
    "Покровка / Чистые пруды": (55.7590, 37.6430),
    "Замоскворечье / Пятницкая": (55.7380, 37.6270),
    "Красная Пресня / Сити": (55.7520, 37.5570),
    "ВДНХ / Алексеевская": (55.8230, 37.6400),
    "Север / Войковская": (55.8200, 37.4900),
    "Юг / Варшавское шоссе": (55.6600, 37.6200),
    "Юго-Запад / Ленинский": (55.6900, 37.5500),
}

FORMAT_MAP = {
    "f_sv": "свидание",
    "f_fr": "друзья",
    "f_cl": "клуб",
    "f_ku": "культура",
    "f_dr": "день рождения",
    "f_pr": "прогулка",
}

DISTRICT_MAP = {
    "d_c":  "Центр",
    "d_a":  "Арбат / Хамовники",
    "d_p":  "Патриаршие / Тверская",
    "d_k":  "Китай-город / Таганка",
    "d_po": "Покровка / Чистые пруды",
    "d_z":  "Замоскворечье / Пятницкая",
    "d_s":  "Красная Пресня / Сити",
    "d_v":  "ВДНХ / Алексеевская",
    "d_se": "Север / Войковская",
    "d_yu": "Юг / Варшавское шоссе",
    "d_yz": "Юго-Запад / Ленинский",
    "d_xx": "другой",
}

DISTRICT_LEGEND = ""

FORMAT_BUTTONS = [
    [
        InlineKeyboardButton("🌹 Свидание",      callback_data="f_sv"),
        InlineKeyboardButton("👥 С друзьями",    callback_data="f_fr"),
    ],
    [
        InlineKeyboardButton("🎵 Клубная ночь",  callback_data="f_cl"),
        InlineKeyboardButton("🎨 Культура",      callback_data="f_ku"),
    ],
    [
        InlineKeyboardButton("🎂 День рождения", callback_data="f_dr"),
        InlineKeyboardButton("🚶 Прогулка",      callback_data="f_pr"),
    ],
]

DISTRICT_BUTTONS = [
    [
        InlineKeyboardButton("Центр",       callback_data="d_c"),
        InlineKeyboardButton("Арбат",       callback_data="d_a"),
        InlineKeyboardButton("Патриаршие",  callback_data="d_p"),
    ],
    [
        InlineKeyboardButton("Китай-город", callback_data="d_k"),
        InlineKeyboardButton("Покровка",    callback_data="d_po"),
        InlineKeyboardButton("Пятницкая",   callback_data="d_z"),
    ],
    [
        InlineKeyboardButton("Пресня",      callback_data="d_s"),
        InlineKeyboardButton("ВДНХ",        callback_data="d_v"),
        InlineKeyboardButton("Север",       callback_data="d_se"),
    ],
    [
        InlineKeyboardButton("Юг",          callback_data="d_yu"),
        InlineKeyboardButton("Юго-Запад",   callback_data="d_yz"),
        InlineKeyboardButton("📍 Другой",   callback_data="d_xx"),
    ],
]

def get_main_keyboard(name="", username=""):
    params = f"?name={name}"
    if username:
        params += f"&username={username}"
    url = f"https://nightout-bot-production.up.railway.app{params}"
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🗺 Открыть приложение", web_app=WebAppInfo(url=url))],
            [KeyboardButton("🏙 Новый вечер"), KeyboardButton("🎲 Сюрприз")],
            [KeyboardButton("🔄 Другой вариант"), KeyboardButton("ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )

METRO_STATIONS = {
    "сокольники": (55.7892, 37.6796),
    "красносельская": (55.7795, 37.6736),
    "комсомольская": (55.7762, 37.6553),
    "чистые пруды": (55.7641, 37.6389),
    "лубянка": (55.7597, 37.6271),
    "охотный ряд": (55.7576, 37.6152),
    "кропоткинская": (55.7449, 37.5950),
    "парк культуры": (55.7349, 37.5936),
    "фрунзенская": (55.7279, 37.5836),
    "спортивная": (55.7194, 37.5757),
    "арбатская": (55.7520, 37.5936),
    "смоленская": (55.7479, 37.5820),
    "киевская": (55.7432, 37.5660),
    "белорусская": (55.7767, 37.5797),
    "маяковская": (55.7706, 37.5958),
    "тверская": (55.7660, 37.6018),
    "театральная": (55.7588, 37.6181),
    "новокузнецкая": (55.7434, 37.6295),
    "павелецкая": (55.7298, 37.6435),
    "таганская": (55.7376, 37.6522),
    "китай-город": (55.7519, 37.6353),
    "курская": (55.7585, 37.6599),
    "третьяковская": (55.7408, 37.6271),
    "октябрьская": (55.7296, 37.6095),
    "добрынинская": (55.7228, 37.6235),
    "серпуховская": (55.7162, 37.6235),
    "пушкинская": (55.7650, 37.5995),
    "кузнецкий мост": (55.7610, 37.6253),
    "трубная": (55.7706, 37.6192),
    "цветной бульвар": (55.7746, 37.6206),
    "новослободская": (55.7785, 37.5971),
    "менделеевская": (55.7820, 37.5936),
    "савёловская": (55.7955, 37.5849),
    "динамо": (55.7900, 37.5594),
    "аэропорт": (55.7955, 37.5246),
    "сокол": (55.8052, 37.5120),
    "войковская": (55.8196, 37.4970),
    "речной вокзал": (55.8561, 37.4787),
    "проспект мира": (55.7799, 37.6385),
    "сухаревская": (55.7690, 37.6323),
    "рижская": (55.7929, 37.6385),
    "алексеевская": (55.8070, 37.6385),
    "вднх": (55.8226, 37.6399),
    "бабушкинская": (55.8561, 37.6590),
    "медведково": (55.8715, 37.6590),
    "бауманская": (55.7722, 37.6780),
    "электрозаводская": (55.7847, 37.7022),
    "семёновская": (55.7815, 37.7317),
    "черкизовская": (55.7951, 37.7374),
    "преображенская площадь": (55.7961, 37.7054),
    "марьина роща": (55.7943, 37.6192),
    "достоевская": (55.7785, 37.6097),
    "шереметьевская": (55.8079, 37.6235),
    "патриаршие": (55.7650, 37.5920),
    "замоскворечье": (55.7380, 37.6270),
    "хамовники": (55.7300, 37.5800),
}

CATEGORY_KEYWORDS = {
    "Ресторан":    ["ресторан", "ужин", "поесть", "еда", "обед", "стейк", "суши", "пицца", "грузин", "итальян", "японск", "кавказ", "мясо", "рыба"],
    "Кафе":        ["кафе", "перекус"],
    "Бар":         ["бар", "коктейл", "выпить", "пиво", "вино", "бар-хоппинг", "паб", "напитк", "крафт"],
    "Кофейня":     ["кофе", "кофейня", "капучино", "латте", "чай"],
    "Кондитерская":["десерт", "торт", "кондитер", "пирожн", "выпечк", "сладк"],
    "Клуб":        ["клуб", "клубн", "танцевать", "вечеринк", "дискотек", "техно", "хаус", "рейв", "ночн", "ночной", "тусовк", "потанцевать", "клубная"],
    "Антикафе":    ["антикафе", "настолки", "настольные игры"],
    "Активность":  ["квест", "боулинг", "бильярд", "картинг", "батут", "активност", "развлечен", "аттракцион"],
    "Культура":    ["музей", "галерея", "театр", "выставк", "кино", "культур", "искусств", "спектакл"],
    "Баня/Спа":    ["баня", "сауна", "спа", "spa", "расслабит"],
}

FORMAT_CATEGORY_MAP = {
    "свидание":      ["Ресторан", "Кафе", "Кофейня", "Культура"],
    "друзья":        ["Ресторан", "Бар", "Кафе", "Активность", "Антикафе"],
    "клуб":          ["Клуб", "Бар", "Антикафе"],
    "культура":      ["Культура", "Кофейня", "Ресторан"],
    "день рождения": ["Ресторан", "Бар", "Активность"],
    "прогулка":      ["Кофейня", "Кондитерская", "Культура", "Кафе"],
}

PRICE_KEYWORDS = {
    "бюджетно": ["бюджет", "дёшево", "дешево", "недорого", "экономн", "скромно"],
    "дорого":   ["дорогой", "дорого", "премиум", "люкс", "роскошн", "богатый", "шикарн", "элитн"],
}

PRICE_REQUEST_KEYWORDS = ["средний чек", "сколько стоит", "цены", "ценник",
                          "сколько потрачу", "по деньгам", "что по деньгам",
                          "сколько денег", "во сколько обойдётся", "сколько выйдет"]

REPEAT_KEYWORDS = ["ещё", "еще", "другой", "другое", "другие", "не то",
                   "не понравилось", "ещё варианты", "другие варианты",
                   "покажи ещё", "альтернатив", "другой вариант"]

FOLLOWUP_KEYWORDS = ["а что", "а сколько", "а как", "расскажи подробнее",
                     "по деньгам", "по ценам", "уточни", "поподробнее",
                     "что насчёт", "а если"]

def get_moscow_time():
    tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(tz)
    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    return now, days[now.weekday()], now.strftime("%H:%M")

def get_season():
    month = datetime.datetime.now().month
    if month in [12, 1, 2]:
        return "зима", "Зимой приоритет — тёплые камерные места, рестораны с живым огнём."
    elif month in [3, 4, 5]:
        return "весна", "Весной ищем первые веранды и парки."
    elif month in [6, 7, 8]:
        return "лето", "Летом идеальны веранды, крыши и места у воды."
    else:
        return "осень", "Осенью хороши уютные места с тёплым светом."

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def detect_categories(text, fmt=None):
    if fmt and fmt in FORMAT_CATEGORY_MAP:
        cats = FORMAT_CATEGORY_MAP[fmt].copy()
    else:
        cats = []
    text_lower = text.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords) and cat not in cats:
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

def is_followup(text):
    t = text.lower().strip()
    return any(kw in t for kw in FOLLOWUP_KEYWORDS) and len(t) < 60

def is_open_now(place):
    """Проверяем открыто ли заведение сейчас"""
    hours = place.get("hours", "")
    if not hours:
        return False  # Нет данных — не берём

    tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(tz)
    h = now.hour

    hours_lower = hours.lower()

    # Круглосуточные
    if "круглосуточно" in hours_lower or "24" in hours_lower:
        return True

    # Ищем время закрытия для текущего дня
    # Простая проверка — если в строке есть время после текущего
    import re
    pat = r'(\d{1,2}):(\d{2})'
    times = re.findall(pat, hours)
    if len(times) >= 2:
        try:
            open_h, open_m = int(times[0][0]), int(times[0][1])
            close_h, close_m = int(times[-1][0]), int(times[-1][1])
            # Учитываем заведения работающие за полночь
            if close_h < open_h:  # например 18:00-02:00
                if h >= open_h or h < close_h - 1:
                    return True
            else:
                if open_h <= h < close_h - 1:
                    return True
        except:
            pass
    return False

def search_places(text, fmt=None, district=None, exclude_names=None, limit=15):
    if not PLACES:
        return []
    cats = detect_categories(text, fmt)
    price_level = detect_price_level(text)
    filtered = [p for p in PLACES if p.get("category") in cats]

    # Фильтруем по времени работы
    tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(tz)
    h = now.hour
    late_night = h >= 23 or h < 6

    if late_night:
        # Поздно — берём только места с данными о часах и которые открыты
        open_places = [p for p in filtered if is_open_now(p)]
        if len(open_places) >= 3:
            filtered = open_places
        # Если совсем мало — берём хотя бы те у кого есть часы
        elif open_places:
            filtered = open_places
    else:
        # Обычное время — исключаем только явно закрытые
        filtered = [p for p in filtered if not p.get("hours") or is_open_now(p)]
    if price_level == "дорого":
        filtered = [p for p in filtered if p.get("price_level") in ["дорого", "средне-дорого"]]
    elif price_level == "бюджетно":
        filtered = [p for p in filtered if p.get("price_level") in ["бюджетно", "бюджетно-средне"]]
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
    pool = filtered[:150]
    if len(pool) > limit:
        weights = [(p.get("rating") or 3.8) ** 3 for p in pool]
        selected = random.choices(pool, weights=weights, k=min(limit * 3, len(pool)))
        seen = set()
        unique = []
        for p in selected:
            if p["name"] not in seen:
                seen.add(p["name"])
                unique.append(p)
        return unique[:limit]
    return pool[:limit]

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
- Грамотность — абсолютный приоритет. Никаких орфографических, пунктуационных или грамматических ошибок.

ПРАВИЛА О МЕСТАХ — САМОЕ ВАЖНОЕ:
- Называй ТОЛЬКО реально существующие заведения Москвы которые ты точно знаешь
- Если не уверен в названии или адресе на 100% — НЕ называй это место вообще
- Никогда не придумывай названия заведений — лучше предложить меньше мест но все реальные
- Адрес указывай только если знаешь точно. Если не знаешь точный адрес — пиши только название и метро
- Рейтинг только если знаешь реальную цифру с реального сайта
- Часы работы только если знаешь точно
- Лучше написать меньше информации но достоверной, чем много но выдуманной

ПРАВИЛА:
- Используй места из предоставленного списка как основу
- Дополняй только проверенными местами которые точно существуют: White Rabbit, Selfie, Delicatessen, Strelka Bar, Propaganda, Симачёв, Белуга, Пушкин, Кофемания, Coffeemania, Вермель, 16 Тонн и подобные известные места
- Средний чек — только если пользователь сам спросил
- Бары и алкоголь — только если пользователь сам просит
- Если просят другие варианты — давай новые места, не повторяй показанные
- Если уточняющий вопрос про план — отвечай на вопрос, не создавай новый план
- Учитывай сезон — летом веранды и открытые пространства, зимой тёплые камерные места
- Учитывай день недели и время СТРОГО. Только места которые точно открыты прямо сейчас и проработают ещё минимум час.
- Если не знаешь часы работы места — НЕ предлагай его совсем. Лучше меньше мест но все проверенные.
- Если сейчас позднее время (после 23:00) или раннее утро — честно скажи что выбор сильно ограничен. Предложи только то что точно работает: круглосуточные заведения, ночные клубы (если пт/сб), либо предложи запланировать вечер на другое время.
- Если подходящих открытых мест совсем нет — так и скажи: "В это время в понедельник почти ничего не работает. Могу составить план на завтра или на выходные — напиши когда планируешь."

ФОРМАТ каждого места:
Название — одна живая фраза почему стоит идти
Адрес | ⭐рейтинг | часы работы

Между точками — одна строка как добраться.
В конце — одна короткая тёплая фраза напутствие."""

WELCOME = "Привет, {name}. Я Nightout — твой консьерж по вечерам в Москве.\n\nКакой вечер планируем?"

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
    username = update.effective_user.username or ""
    username = update.effective_user.username or ""
    register_user(user_id, name)
    await update.message.reply_text(
        "Эти кнопки всегда доступны 👇",
        reply_markup=get_main_keyboard(name, username)
    )
    await update.message.reply_text(
        WELCOME.format(name=name),
        reply_markup=InlineKeyboardMarkup(FORMAT_BUTTONS)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_histories:
        user_histories[user_id] = []
        user_last_request[user_id] = ""
        user_district[user_id] = None
        user_format[user_id] = None

    if data in FORMAT_MAP:
        fmt = FORMAT_MAP[data]
        user_format[user_id] = fmt
        fmt_labels = {
            "свидание":      "свидание 💑",
            "друзья":        "вечер с друзьями 👥",
            "клуб":          "клубную ночь 🎵",
            "культура":      "культурный вечер 🎨",
            "день рождения": "день рождения 🎂",
            "прогулка":      "прогулку 🚶",
        }
        fmt_label = fmt_labels.get(fmt, fmt)
        await query.edit_message_text(
            f"Отлично, планируем {fmt_label}.\n\nВ каком районе города?\n\n{DISTRICT_LEGEND}",
            reply_markup=InlineKeyboardMarkup(DISTRICT_BUTTONS)
        )

    elif data in DISTRICT_MAP:
        district = DISTRICT_MAP[data]
        if district == "другой":
            user_district[user_id] = None
            await query.edit_message_text(
                "Напиши свой район или станцию метро — и я подберу места рядом."
            )
        else:
            user_district[user_id] = district
            await query.edit_message_text(
                f"Район — {district}.\n\nЕсть пожелания по кухне, бюджету или компании? Или просто напиши \"вперёд\" — и я сразу составлю план."
            )

    elif data.startswith("rate_"):
        score = data.replace("rate_", "")
        responses = {
            "5": "Рад слышать! Приятного вечера 🌙",
            "3": "Понял. Буду лучше подбирать.",
            "1": "Жаль. Напиши что не понравилось — исправлюсь."
        }
        await query.edit_message_text(responses.get(score, "Спасибо за оценку."))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    text = update.message.text

    if user_id not in user_histories:
        user_histories[user_id] = []
        user_last_request[user_id] = ""
        user_district[user_id] = None
        user_format[user_id] = None

    # Постоянные кнопки
    if text == "🏙 Новый вечер":
        user_histories[user_id] = []
        user_last_request[user_id] = ""
        user_district[user_id] = None
        user_format[user_id] = None
        await update.message.reply_text(
            WELCOME.format(name=name),
            reply_markup=get_main_keyboard(name, username)
        )
        await update.message.reply_text(
            WELCOME.format(name=name),
            reply_markup=InlineKeyboardMarkup(FORMAT_BUTTONS)
        )
        return

    if text == "🔄 Другой вариант":
        text = "ещё варианты"

    if text == "💰 Что по деньгам?":
        text = "что по деньгам"

    if text == "ℹ️ Помощь":
        await update.message.reply_text(
            "Просто напиши что хочешь — я подберу вечер.\n\nНапример:\n— Хочу романтический ужин в центре\n— Куда пойти с друзьями в пятницу\n— Клубная ночь на Патриарших\n— Что-нибудь необычное до 3000 рублей",
            reply_markup=get_main_keyboard(name)
        )
        return

    if text == "🎲 Сюрприз":
        now2, day2, time2 = get_moscow_time()
        weather_note, weather_emoji, temp, is_rain = get_weather()
        formats = ["свидание", "друзья", "культура", "прогулка"]
        if day2 in ["пятница", "суббота"]:
            formats.append("ночной клуб")
        import random as _r
        rand_fmt = _r.choice(formats)
        rand_district = _r.choice(list(DISTRICTS.keys()))
        user_format[user_id] = rand_fmt
        user_district[user_id] = rand_district
        text = f"Сюрприз: {rand_fmt} в районе {rand_district}"
        await update.message.reply_text(
            f"{weather_emoji} Берёшь риск — хорошо. Составляю сюрприз-вечер...",
            reply_markup=get_main_keyboard(name)
        )

    now, day_name, time_str = get_moscow_time()
    moscow_time = f"Сейчас в Москве: {day_name}, {time_str}"
    season, season_tip = get_season()

    district = user_district.get(user_id)
    fmt = user_format.get(user_id)
    show_price = is_price_request(text)

    # Ищем район или метро в тексте
    text_lower = text.lower()
    for d in DISTRICTS:
        if d.lower() in text_lower:
            user_district[user_id] = d
            district = d
            break
    else:
        for station, coords in METRO_STATIONS.items():
            if station in text_lower:
                key = f"метро {station}"
                DISTRICTS[key] = coords
                user_district[user_id] = key
                district = key
                break

    if is_repeat_request(text):
        exclude = extract_shown_names(user_histories[user_id])
        search_query = user_last_request.get(user_id, text)
        places = search_places(search_query, fmt=fmt, district=district, exclude_names=exclude)
        note = "Пользователь просит другие варианты — не повторяй места которые уже предлагал."
    elif is_followup(text):
        places = search_places(user_last_request.get(user_id, text), fmt=fmt, district=district)
        note = "ВАЖНО: уточняющий вопрос про уже предложенный план. Не создавай новый план. Просто ответь на вопрос."
    else:
        full_query = f"{fmt or ''} {text}".strip()
        places = search_places(full_query, fmt=fmt, district=district)
        user_last_request[user_id] = full_query
        note = ""

    price_note = "Пользователь спросил о ценах — укажи примерный ценник для мест из плана." if show_price else "Средний чек не указывай."
    district_note = f"Район пользователя: {district}. Приоритет — места рядом." if district else ""
    format_note = f"Формат вечера: {fmt}." if fmt else ""

    places_text = format_places(places, show_price=show_price)

    weather_note, weather_emoji, temp, is_rain = get_weather()
    user_message = (
        f"{moscow_time}\n"
        f"Сезон: {season}. {season_tip}\n"
        f"{weather_note}\n"
        f"Меня зовут {name}. Мой запрос: {text}\n"
        f"{format_note}\n{district_note}\n{note}\n{price_note}\n\n"
        f"Доступные заведения:\n{places_text}\n\n"
        f"Составь сценарий. Начни с короткого обращения по имени и одной фразы под настроение. Затем ВЕЧЕР ГОТОВ и план. В конце — одна фраза напутствие."
    )

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

    # Предлагаем оценить если это был новый запрос (не уточнение)
    if not is_followup(text) and not is_repeat_request(text) and "ВЕЧЕР ГОТОВ" in answer:
        rating_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👍 Отлично", callback_data="rate_5"),
                InlineKeyboardButton("👌 Нормально", callback_data="rate_3"),
                InlineKeyboardButton("👎 Не то", callback_data="rate_1"),
            ]
        ])
        await update.message.reply_text(
            "Как план?",
            reply_markup=rating_keyboard
        )

async def send_notifications(context):
    """Отправляем уведомления дважды в неделю — пт и вс вечером"""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
    _, weather_emoji, temp, is_rain = get_weather()
    weather_txt = f"На улице {temp}°C{'☔ дождь' if is_rain else ''}."

    day = now.weekday()
    if day == 4:  # пятница
        msg = f"{weather_emoji} Пятница вечером — лучшее время выдохнуть. {weather_txt}\n\nКуда идём?"
    elif day == 6:  # воскресенье
        msg = f"{weather_emoji} Воскресенье ещё не кончилось. {weather_txt}\n\nУспеваем провести вечер?"
    else:
        return

    for uid, udata in list(user_registry.items()):
        try:
            kb = ReplyKeyboardMarkup(
                [[KeyboardButton("🎲 Сюрприз"), KeyboardButton("🏙 Новый вечер")]],
                resize_keyboard=True
            )
            await context.bot.send_message(chat_id=uid, text=msg, reply_markup=kb)
        except Exception as e:
            print(f"Не удалось отправить уведомление {uid}: {e}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Уведомления — каждый день в 19:00 МСК, срабатывает только пт и вс
    job_queue = app.job_queue
    job_queue.run_daily(
        send_notifications,
        time=datetime.time(hour=19, minute=0, tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
    )

    print("Nightout бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
