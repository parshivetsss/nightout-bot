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

METRO_STATIONS = {
    "сокольники": (55.7892, 37.6796),
    "красносельская": (55.7795, 37.6736),
    "комсомольская": (55.7762, 37.6553),
    "красные ворота": (55.7688, 37.6589),
    "чистые пруды": (55.7641, 37.6389),
    "лубянка": (55.7597, 37.6271),
    "охотный ряд": (55.7576, 37.6152),
    "библиотека имени ленина": (55.7515, 37.6102),
    "кропоткинская": (55.7449, 37.5950),
    "парк культуры": (55.7349, 37.5936),
    "фрунзенская": (55.7279, 37.5836),
    "спортивная": (55.7194, 37.5757),
    "воробьёвы горы": (55.7097, 37.5588),
    "университет": (55.6999, 37.5350),
    "проспект вернадского": (55.6796, 37.5083),
    "юго-западная": (55.6635, 37.4847),
    "теплый стан": (55.6421, 37.4613),
    "ясенево": (55.6229, 37.4636),
    "новоясеневская": (55.6116, 37.4830),
    "арбатская": (55.7520, 37.5936),
    "смоленская": (55.7479, 37.5820),
    "киевская": (55.7432, 37.5660),
    "студенческая": (55.7389, 37.5510),
    "кутузовская": (55.7368, 37.5391),
    "филёвский парк": (55.7411, 37.5163),
    "пионерская": (55.7368, 37.4980),
    "кунцевская": (55.7311, 37.4196),
    "молодёжная": (55.7306, 37.3940),
    "крылатское": (55.7593, 37.4013),
    "строгино": (55.7890, 37.3977),
    "митино": (55.8385, 37.3548),
    "пятницкое шоссе": (55.8547, 37.3253),
    "речной вокзал": (55.8561, 37.4787),
    "водный стадион": (55.8396, 37.4882),
    "войковская": (55.8196, 37.4970),
    "сокол": (55.8052, 37.5120),
    "аэропорт": (55.7955, 37.5246),
    "динамо": (55.7900, 37.5594),
    "белорусская": (55.7767, 37.5797),
    "маяковская": (55.7706, 37.5958),
    "тверская": (55.7660, 37.6018),
    "театральная": (55.7588, 37.6181),
    "новокузнецкая": (55.7434, 37.6295),
    "павелецкая": (55.7298, 37.6435),
    "автозаводская": (55.7133, 37.6549),
    "коломенская": (55.6917, 37.6660),
    "каширская": (55.6649, 37.6636),
    "кантемировская": (55.6414, 37.6641),
    "царицыно": (55.6194, 37.6641),
    "орехово": (55.6036, 37.6646),
    "домодедовская": (55.5882, 37.6641),
    "красногвардейская": (55.5693, 37.6641),
    "алма-атинская": (55.5555, 37.6641),
    "медведково": (55.8715, 37.6590),
    "бабушкинская": (55.8561, 37.6590),
    "свиблово": (55.8401, 37.6590),
    "ботанический сад": (55.8226, 37.6590),
    "вднх": (55.8226, 37.6399),
    "алексеевская": (55.8070, 37.6385),
    "рижская": (55.7929, 37.6385),
    "проспект мира": (55.7799, 37.6385),
    "сухаревская": (55.7690, 37.6323),
    "тургеневская": (55.7629, 37.6385),
    "китай-город": (55.7519, 37.6353),
    "таганская": (55.7376, 37.6522),
    "пролетарская": (55.7229, 37.6644),
    "волгоградский проспект": (55.7089, 37.6825),
    "текстильщики": (55.7028, 37.7213),
    "кузьминки": (55.6942, 37.7590),
    "рязанский проспект": (55.7028, 37.7916),
    "выхино": (55.7249, 37.8413),
    "лермонтовский проспект": (55.7409, 37.8622),
    "жулебино": (55.7295, 37.8973),
    "котельники": (55.6715, 37.8677),
    "новогиреево": (55.7619, 37.8167),
    "перово": (55.7651, 37.7770),
    "шоссе энтузиастов": (55.7683, 37.7382),
    "авиамоторная": (55.7511, 37.7276),
    "площадь ильича": (55.7459, 37.7080),
    "марксистская": (55.7393, 37.6671),
    "третьяковская": (55.7408, 37.6271),
    "октябрьская": (55.7296, 37.6095),
    "шаболовская": (55.7187, 37.6095),
    "ленинский проспект": (55.7028, 37.5887),
    "академическая": (55.6869, 37.5695),
    "профсоюзная": (55.6758, 37.5470),
    "новые черёмушки": (55.6649, 37.5470),
    "калужская": (55.6518, 37.5385),
    "беляево": (55.6386, 37.5298),
    "коньково": (55.6229, 37.5048),
    "тёплый стан": (55.6421, 37.4613),
    "черкизовская": (55.7951, 37.7374),
    "преображенская площадь": (55.7961, 37.7054),
    "семёновская": (55.7815, 37.7317),
    "электрозаводская": (55.7847, 37.7022),
    "бауманская": (55.7722, 37.6780),
    "курская": (55.7585, 37.6599),
    "чкаловская": (55.7574, 37.6467),
    "пушкинская": (55.7650, 37.5995),
    "кузнецкий мост": (55.7610, 37.6253),
    "сретенский бульвар": (55.7673, 37.6374),
    "трубная": (55.7706, 37.6192),
    "цветной бульвар": (55.7746, 37.6206),
    "новослободская": (55.7785, 37.5971),
    "менделеевская": (55.7820, 37.5936),
    "савёловская": (55.7955, 37.5849),
    "достоевская": (55.7785, 37.6097),
    "марьина роща": (55.7943, 37.6192),
    "шереметьевская": (55.8079, 37.6235),
    "петровско-разумовская": (55.8213, 37.5563),
    "фонвизинская": (55.8106, 37.5989),
    "бутырская": (55.8012, 37.5921),
    "телецентр": (55.8360, 37.5921),
    "лихоборы": (55.8447, 37.5680),
    "верхние лихоборы": (55.8568, 37.5329),
    "окружная": (55.8385, 37.5892),
    "владыкино": (55.8419, 37.5975),
    "отрадное": (55.8561, 37.6038),
    "владыкино": (55.8419, 37.5975),
    "бибирево": (55.8843, 37.6192),
    "алтуфьево": (55.8951, 37.5862),
    "лесопарковая": (55.5762, 37.6192),
    "битцевский парк": (55.5878, 37.5885),
    "ясенево": (55.6229, 37.4636),
    "теплый стан": (55.6421, 37.4613),
    "чертановская": (55.6387, 37.6095),
    "южная": (55.6229, 37.6192),
    "пражская": (55.6114, 37.6046),
    "аннино": (55.5943, 37.5980),
    "улица скобелевская": (55.5834, 37.5762),
    "бульвар адмирала ушакова": (55.5699, 37.5625),
    "улица горчакова": (55.5580, 37.5448),
    "щербинка": (55.5097, 37.5639),
    "столбово": (55.5023, 37.5161),
    "некрасовка": (55.7171, 37.9498),
    "лухмановская": (55.7328, 37.9178),
    "улица дмитриевского": (55.7328, 37.8940),
    "косино": (55.7328, 37.8622),
    "юго-восточная": (55.6934, 37.8305),
    "окская": (55.6871, 37.7959),
    "стахановская": (55.7028, 37.7677),
    "нижегородская": (55.7419, 37.7467),
    "авиамоторная": (55.7511, 37.7276),
    "деловой центр": (55.7493, 37.5392),
    "международная": (55.7493, 37.5225),
    "выставочная": (55.7507, 37.5392),
    "деловой центр": (55.7493, 37.5392),
    "москва-сити": (55.7493, 37.5392),
    "патриаршие пруды": (55.7650, 37.5920),
    "патриаршие": (55.7650, 37.5920),
    "арбат": (55.7520, 37.5950),
    "замоскворечье": (55.7380, 37.6270),
    "хамовники": (55.7300, 37.5800),
    "измайлово": (55.7900, 37.7500),
    "сокольники парк": (55.7892, 37.6796),
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
        InlineKeyboardButton("💑 Свидание", callback_data="format_свидание"),
        InlineKeyboardButton("👥 С друзьями", callback_data="format_друзья"),
    ],
    [
        InlineKeyboardButton("🎵 Клубная ночь", callback_data="format_клуб"),
        InlineKeyboardButton("🎨 Культура", callback_data="format_культура"),
    ],
    [
        InlineKeyboardButton("🎂 День рождения", callback_data="format_др"),
        InlineKeyboardButton("🚶 Прогулка", callback_data="format_прогулка"),
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

    # Берём топ-150 и случайно выбираем — так каждый раз разные места но все качественные
    import random
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

WELCOME = """Привет, {name}. Я Nightout — твой консьерж по вечерам в Москве.

Какой вечер планируешь?"""

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
        fmt_names = {
            "свидание": "свидание 💑",
            "друзья": "вечер с друзьями 👥",
            "клуб": "клубную ночь 🎵",
            "культура": "культурный вечер 🎨",
            "др": "день рождения 🎂",
            "прогулка": "прогулку 🚶",
        }
        fmt_label = fmt_names.get(fmt, fmt)
        await query.edit_message_text(
            f"Отлично, планируем {fmt_label}.\n\nВ каком районе города?",
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
                f"Район — {district}.\n\nЕсть пожелания по кухне, бюджету или количеству человек? Или просто напиши \"вперёд\" — и я сразу составлю план."
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

    # Если написали район или метро текстом
    text_lower = text.lower()
    found_district = False
    # Сначала ищем в районах
    for d in DISTRICTS:
        if d.lower() in text_lower or any(part.lower() in text_lower for part in d.split("/")):
            user_district[user_id] = d
            district = d
            found_district = True
            break
    # Если не нашли район — ищем метро
    if not found_district:
        for station, coords in METRO_STATIONS.items():
            if station in text_lower:
                user_district[user_id] = f"метро {station}"
                # Сохраняем координаты метро как временный район
                district = f"метро {station}"
                # Добавляем координаты в DISTRICTS динамически
                DISTRICTS[f"метро {station}"] = coords
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
