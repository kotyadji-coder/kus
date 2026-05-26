"""
AI-адаптер на Gemini (Google AI Studio).
Используется для:
- Парсинг свободного текста (диагнозы, стоп-продукты)
- Персонализация текстов PDF (натуралка + сухой корм)
- Генерация недельного меню с ротацией (натуралка)
- Разбор состава и обоснование выбора (сухой корм)
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "project-5c6fc698-9b69-4d2d-95d")
GOOGLE_CREDS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(__file__), "google-credentials.json"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
VERTEX_MODELS = ["gemini-3.5-flash", "gemini-3.1-pro", "gemini-2.5-flash"]

_client = None


def _get_client():
    global _client
    if _client:
        return _client

    try:
        from google import genai

        # Способ 1: Vertex AI через service account (надёжнее, облачная квота)
        if os.path.exists(GOOGLE_CREDS_PATH):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDS_PATH
            _client = genai.Client(
                vertexai=True,
                project=GOOGLE_CLOUD_PROJECT,
                location="us-central1",
            )
            return _client

        # Способ 2: API ключ (Google AI Studio)
        if GEMINI_API_KEY:
            _client = genai.Client(api_key=GEMINI_API_KEY)
            return _client

        return None
    except ImportError:
        return None


def _ask(prompt: str, max_tokens: int = 1000) -> str | None:
    """Отправляет запрос в Gemini, возвращает текст ответа."""
    import time
    client = _get_client()
    if not client:
        return None
    # Gemini 2.5 flash uses thinking tokens that count against max_output_tokens
    # Multiply by 8x to ensure enough room for actual text
    effective_max = max_tokens * 8
    # Пробуем модели по порядку (на Vertex AI не все могут быть включены)
    models_to_try = [GEMINI_MODEL] + [m for m in VERTEX_MODELS if m != GEMINI_MODEL]
    for model in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"max_output_tokens": effective_max, "temperature": 0.3},
                )
                text = response.text
                if text:
                    return text.strip()
                # Пустой ответ — retry
                print(f"Gemini ({model}): empty response, attempt {attempt + 1}/3")
                time.sleep(1)
                continue
            except Exception as e:
                if "NOT_FOUND" in str(e) or "not found" in str(e).lower():
                    break  # Модель не доступна, пробуем следующую
                print(f"Gemini error ({model}), attempt {attempt + 1}/3: {e}")
                time.sleep(2)
        else:
            continue
        continue
    print("Gemini: все попытки исчерпаны")
    return None


# =====================================================================
# ПАРСИНГ ТЕКСТА (общее для натуралки и сухого корма)
# =====================================================================

def parse_diagnoses(raw_text: str) -> list[str]:
    """Парсит свободный текст диагнозов в структурированный список."""
    if not raw_text or not raw_text.strip():
        return []

    result = _ask(f"""Извлеки из текста владельца собаки список ветеринарных диагнозов/проблем.
Верни ТОЛЬКО JSON-массив строк на русском языке. Никакого текста кроме JSON.
Если диагнозов нет — верни [].

Текст: "{raw_text}"

Примеры:
"у нас панкреатит и на курицу сыпь" -> ["панкреатит", "аллергия на курицу"]
"всё ок" -> []""", max_tokens=500)

    if result:
        try:
            start = result.index("[")
            end = result.rindex("]") + 1
            return json.loads(result[start:end])
        except (ValueError, json.JSONDecodeError):
            pass
    return _simple_parse_diagnoses(raw_text)


def parse_stop_products(raw_text: str) -> list[str]:
    """Парсит свободный текст стоп-продуктов в список."""
    if not raw_text or not raw_text.strip():
        return []

    result = _ask(f"""Извлеки из текста владельца собаки список продуктов, которые НЕЛЬЗЯ включать в рацион.
Верни ТОЛЬКО JSON-массив строк (базовое название продукта, единственное число).
Если стоп-продуктов нет — верни [].

Текст: "{raw_text}"

Примеры:
"на курицу сыпь, говядину тоже не даём" -> ["курица", "говядина"]
"нет аллергий" -> []
"рыбу не ест, от молочки понос" -> ["рыба", "молоко"]""", max_tokens=500)

    if result:
        try:
            start = result.index("[")
            end = result.rindex("]") + 1
            return json.loads(result[start:end])
        except (ValueError, json.JSONDecodeError):
            pass
    return _simple_parse_stop(raw_text)


# =====================================================================
# НАТУРАЛКА — AI-генерация
# =====================================================================

def _gender_note(sex: str) -> str:
    """Строгая инструкция по полу для всех AI-промптов."""
    if sex == "female":
        return (
            "ВАЖНО — пол собаки: ДЕВОЧКА. Используй ТОЛЬКО женский род: она, её, ей, для неё. "
            "Примеры: «она активна», «для неё подобран», «её рацион», «ей подходит». "
            "НИКОГДА не пиши «он», «его», «ему», «для него». "
            "Обращение к владельцу на «вы» с МАЛЕНЬКОЙ буквы (не «Вы», не «Вам»)."
        )
    return (
        "ВАЖНО — пол собаки: МАЛЬЧИК. Используй ТОЛЬКО мужской род: он, его, ему, для него. "
        "Примеры: «он активен», «для него подобран», «его рацион», «ему подходит». "
        "НИКОГДА не пиши «она», «её», «ей», «для неё». "
        "Обращение к владельцу на «вы» с МАЛЕНЬКОЙ буквы (не «Вы», не «Вам»)."
    )


def generate_natural_intro(dog_name: str, breed: str, summary: str, sex: str = "male") -> str:
    """Персональное вступление для PDF с натуральным рационом."""
    gender_note = _gender_note(sex)
    result = _ask(f"""Напиши вступление (4-5 полных предложений, минимум 200 символов) для PDF-документа с натуральным рационом собаки.
Обращайся к владельцу на «вы» (с маленькой буквы, НЕ «Вы»). Упомяни кличку и породу. Объясни, почему рацион подобран именно так.
{gender_note}
Тон: дружелюбный, профессиональный. Без emoji. Не представляйся диетологом/ветеринаром.
Напиши ПОЛНЫЙ текст, не обрезай, не сокращай.

Кличка: {dog_name}
Порода: {breed}
Данные: {summary}""", max_tokens=800)
    return result or ""


def generate_natural_weekly_menu(dog_profile: dict, products: dict, daily_grams: float) -> str:
    """AI генерирует разнообразное недельное меню для натуралки.

    Это ключевая функция: AI берёт рассчитанные калькулятором граммовки
    и создаёт разнообразное меню на 7 дней с ротацией продуктов,
    рыбными днями и правильным распределением по кормлениям.
    """
    result = _ask(f"""Ты — ветеринарный диетолог. Составь меню на 7 дней для собаки на натуральном питании.

ПРОФИЛЬ СОБАКИ:
{json.dumps(dog_profile, ensure_ascii=False, indent=2)}

ДОСТУПНЫЕ ПРОДУКТЫ И СУТОЧНЫЕ ГРАММОВКИ:
{json.dumps(products, ensure_ascii=False, indent=2)}

СУТОЧНЫЙ ОБЪЁМ: {daily_grams} г

ПРАВИЛА:
1. Каждый день — 2 кормления (утро и вечер)
2. Ротация: не повторяй одинаковое мясо 2 дня подряд
3. Среда и суббота — рыбные дни (рыба вместо части мяса вечером)
4. Субпродукты (печень, сердце, рубец) — чередуй, не давай всё сразу
5. Овощи — разные каждый день
6. Кисломолочка — утром
7. Яйца — 3 раза в неделю
8. Суммарный вес за день должен быть ~{int(daily_grams)} г (±10%)

Верни JSON-массив из 7 объектов:
[{{"day": "Понедельник", "morning": [{{"product": "Говядина", "grams": 100}}, ...], "evening": [...]}}]

ТОЛЬКО JSON, без текста.""", max_tokens=3000)

    return result


def generate_natural_product_notes(dog_profile: dict, warnings: list) -> str:
    """AI пишет персональные заметки: почему выбраны эти продукты, на что обращать внимание."""
    sex = dog_profile.get("sex", "male")
    gender_note = _gender_note(sex)
    result = _ask(f"""Напиши краткие персональные рекомендации (5-7 пунктов) для владельца собаки по натуральному питанию.

{gender_note}
Профиль:
{json.dumps(dog_profile, ensure_ascii=False)}

Предупреждения системы: {warnings}

Формат: маркированный список (простой текст, без markdown). Каждый пункт — 1-2 предложения.
Тон: дружелюбный, конкретный. Обращение на «вы» (с маленькой буквы, НЕ «Вы»). Без воды. Без emoji.
Темы:
- Почему выбраны именно эти продукты
- На что обращать внимание при кормлении
- Когда пересчитать рацион
- Лайфхаки по хранению и закупке""", max_tokens=600)
    return result or ""


def generate_personal_analysis(dog_profile: dict, diet_summary: dict) -> str:
    """Генерирует ровно 6 блоков персонального анализа. Возвращает список HTML-блоков."""
    sex = dog_profile.get("sex", "male")
    gender_note = _gender_note(sex)

    result = _ask(f"""Ты — AI-система «Кусь». Напиши ровно 6 блоков персонального анализа рациона.

ДОСЬЕ СОБАКИ:
{json.dumps(dog_profile, ensure_ascii=False, indent=2)}

РЕЗУЛЬТАТ РАСЧЁТА:
{json.dumps(diet_summary, ensure_ascii=False, indent=2)}

Напиши РОВНО 6 блоков. Формат каждого блока — строго:
<div class="insight">
  <div class="tag ТИП">ЗАГОЛОВОК</div>
  <p>Текст 3-5 предложений.</p>
</div>

Типы тегов: breed, health, nutrition, lifestyle.

Выбери 6 самых важных тем из списка (в порядке приоритета):
1. Порода — генетические предрасположенности, как повлияли на расчёт
2. Вес и кондиция — текущий vs целевой, почему именно так
3. Продукты — логика выбора, распределение по группам
4. Добавки — почему именно эти, с привязкой к факторам
5. Диагнозы (если есть) — как учтены в рационе
6. Стул (если проблемный) — причины и что поможет
7. Щенок (если да) — Ca:P, рост, когда пересчитать
8. Беременность/лактация (если да) — калорийность
9. Образ жизни — советы по активности + кондиции + породе
10. Контроль веса — как отслеживать прогресс

Требования:
- {gender_note}
- Обращайся на «вы» (с маленькой буквы, НЕ «Вы»), упоминай кличку
- Каждый блок — 3-5 содержательных предложений
- Анализируй СОВОКУПНОСТЬ факторов
- Экспертно, но доступно. Без воды, без emoji
- РОВНО 6 блоков, не больше и не меньше
- Последний (6-й) блок обязательно:
<div class="insight" style="background:#fef3c7;border-color:#fbbf24;">
  <div class="tag health">Важно</div>
  <p>Данные рекомендации носят информационный характер и не являются ветеринарной консультацией. При наличии заболеваний или тревожных симптомов обратитесь к ветеринарному врачу.</p>
</div>""", max_tokens=4000)

    if not result:
        return ""

    # Fix truncated HTML
    open_divs = result.count('<div') - result.count('</div>')
    if open_divs > 0:
        result += '</div>' * open_divs

    return result


# =====================================================================
# СУХОЙ КОРМ — AI-генерация
# =====================================================================

def generate_dry_food_analysis(food: dict, dog_profile: dict) -> str:
    """AI пишет честный персональный разбор конкретного корма для конкретной собаки."""
    result = _ask(f"""Ты — независимый эксперт по кормам для собак. Напиши честный разбор корма для конкретной собаки.

КОРМ:
Бренд: {food.get('brand')} — {food.get('name')}
Состав (первые 5): {', '.join(food.get('ingredients_top5', []))}
Белок: {food.get('protein_pct')}%, Жир: {food.get('fat_pct')}%, Зола: {food.get('ash_pct')}%
Мясо: ~{food.get('meat_estimate_pct')}%
Зерновой: {'Нет' if food.get('grain_free') else 'Да — ' + ', '.join(food.get('grain_sources', []))}
Цена: ~{food.get('price_per_kg')} руб/кг

СОБАКА:
Кличка: {dog_profile.get('name')}, Порода: {dog_profile.get('breed')}
Вес: {dog_profile.get('weight_kg')} кг, Кондиция: {dog_profile.get('condition')}
Стоп-продукты: {dog_profile.get('stop_products', [])}
Диагнозы: {dog_profile.get('diagnoses', [])}

Напиши 2-3 предложения: почему этот корм подходит или не подходит именно этой собаке.
Будь конкретен — упоминай кличку, породу, особенности.
Если в корме есть проблемы — скажи честно.
Тон: экспертный, но понятный обычному человеку. Без emoji.""", max_tokens=2000)
    return result or ""


def generate_dry_food_intro(dog_profile: dict) -> str:
    """Персональное вступление для PDF с подбором корма."""
    result = _ask(f"""Напиши короткое (3-4 предложения) вступление для PDF-документа с подборкой сухих кормов.
Обращайся к владельцу на «вы». Упомяни кличку и породу.
Объясни принцип подбора: анализ состава, не маркетинг. 3 ценовые категории, по 3 корма.
Тон: дружелюбный, экспертный. Без emoji.

Кличка: {dog_profile.get('name')}
Порода: {dog_profile.get('breed')}
Вес: {dog_profile.get('weight_kg')} кг
Кондиция: {dog_profile.get('condition')}
Стоп-продукты: {dog_profile.get('stop_products', [])}""", max_tokens=2000)
    return result or ""


def generate_dry_food_conclusion(budget_foods: list, mid_foods: list, premium_foods: list, dog_profile: dict) -> str:
    """AI пишет итоговую рекомендацию: какой корм выбрать в каждой категории."""
    foods_summary = []
    for cat, foods in [("Бюджет", budget_foods), ("Средний", mid_foods), ("Премиум", premium_foods)]:
        for f in foods:
            fd = f if isinstance(f, dict) else f.food
            foods_summary.append(f"{cat}: {fd.get('brand','')} {fd.get('name','')} (~{fd.get('meat_estimate_pct','')}% мяса, {fd.get('price_per_kg','')} руб/кг)")

    result = _ask(f"""Напиши краткий итог (3-4 предложения) — какой корм лучше всего подходит этой собаке.
Выдели ОДИН лучший вариант из всех 9 и объясни почему.
Также скажи, какой лучший в бюджетной категории.

Собака: {dog_profile.get('name')}, {dog_profile.get('breed')}, {dog_profile.get('weight_kg')}кг, кондиция: {dog_profile.get('condition')}
Стоп: {dog_profile.get('stop_products', [])}

Корма:
{chr(10).join(foods_summary)}

Тон: уверенный, конкретный. Без emoji.""", max_tokens=2000)
    return result or ""


# =====================================================================
# ГЕНЕРАЦИЯ ОБЛОЖКИ — Imagen 3
# =====================================================================

COVER_CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "cover_cache")


def _breed_cache_key(breed: str) -> str:
    """Превращает название породы в имя файла: 'Лабрадор-ретривер' -> 'лабрадор-ретривер.png'."""
    import re
    key = breed.lower().strip()
    key = re.sub(r'[^\w\s-]', '', key)
    key = re.sub(r'\s+', '_', key)
    return f"{key}.png"


def generate_cover_image(breed: str, dog_name: str) -> str | None:
    """Генерирует иллюстрацию собаки по породе через Imagen 3.
    Кэширует по породе — повторная генерация не нужна.
    Возвращает base64-строку PNG или None при ошибке.
    """
    import base64

    # Проверяем кэш
    os.makedirs(COVER_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(COVER_CACHE_DIR, _breed_cache_key(breed))

    if os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    # Генерируем новую
    client = _get_client()
    if not client:
        return None

    # Use AI to get English breed name and detailed visual description
    breed_desc = _ask(f"""I need to generate an image of a "{breed}" dog breed.

Step 1: Write the EXACT English breed name (e.g. "Бигль" = "Beagle", "Лабрадор-ретривер" = "Labrador Retriever").
Step 2: Describe this breed's TYPICAL appearance in detail.

Format your answer as ONE paragraph, like this example:
"Beagle, a small to medium-sized hound dog with a short tricolor coat (black, brown, and white), long droopy ears, large brown or hazel eyes, square muzzle, medium-length tail carried high, muscular compact body"

Include: exact English breed name, size, coat type/color/length, ear shape, eye color, muzzle shape, tail, body type.
Write ONLY the description, nothing else. Max 50 words.""", max_tokens=200)

    if not breed_desc or len(breed_desc) < 10:
        breed_desc = f"{breed} dog"

    prompt = (
        f"A single friendly happy {breed_desc.strip().rstrip('.')}, "
        f"sitting and looking at camera with a gentle smile, "
        f"3D Pixar-style illustration, warm soft studio lighting, clean solid white background, "
        f"cute big expressive eyes, detailed fur texture, high quality 3D render, "
        f"no text, no watermark, no humans, no other animals, no props, centered composition"
    )

    try:
        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            config={
                "number_of_images": 1,
                "aspect_ratio": "16:9",
                "person_generation": "dont_allow",
            },
        )
        if response.generated_images:
            image_bytes = response.generated_images[0].image.image_bytes
            # Сохраняем в кэш
            with open(cache_file, "wb") as f:
                f.write(image_bytes)
            return base64.b64encode(image_bytes).decode("utf-8")
    except Exception as e:
        print(f"Imagen error: {e}")

    return None


# =====================================================================
# Fallback-парсеры (без AI)
# =====================================================================

def _simple_parse_diagnoses(text: str) -> list[str]:
    keywords = {
        "панкреатит": "панкреатит", "гастрит": "гастрит",
        "мкб": "МКБ", "мочекаменн": "МКБ",
        "печен": "проблемы с печенью", "почк": "проблемы с почками",
        "аллерг": "аллергия", "дерматит": "дерматит",
        "диабет": "диабет", "эпилепс": "эпилепсия",
    }
    result = []
    lower = text.lower()
    for key, val in keywords.items():
        if key in lower and val not in result:
            result.append(val)
    return result


def _simple_parse_stop(text: str) -> list[str]:
    keywords = [
        "курица", "курятина", "говядина", "свинина", "баранина",
        "утка", "кролик", "индейка", "рыба", "молоко", "творог",
        "кефир", "яйцо", "кукуруза", "пшеница", "соя",
    ]
    result = []
    lower = text.lower()
    for kw in keywords:
        if kw[:4] in lower and kw not in result:
            result.append(kw)
    return result


# =====================================================================
# Тест
# =====================================================================

if __name__ == "__main__":
    print("=== Тест парсеров ===")
    print("Диагнозы:", parse_diagnoses("у нас панкреатит и аллергия на курицу"))
    print("Стоп-продукты:", parse_stop_products("курицу не даём, от говядины чешется"))

    print("\n=== Тест генерации (натуралка) ===")
    intro = generate_natural_intro("Барон", "Лабрадор-ретривер",
        "32 кг, лёгкий перевес, кастрирован, средняя активность, BARF, без курицы")
    print(f"Вступление: {intro}")

    print("\n=== Тест генерации (сухой корм) ===")
    dog = {"name": "Барон", "breed": "Лабрадор-ретривер", "weight_kg": 32,
           "condition": "chubby", "stop_products": ["курица"], "diagnoses": []}
    food = {"brand": "Grandorf", "name": "Adult Large Breed Lamb & Rice",
            "ingredients_top5": ["дегидрированное мясо ягнёнка 24%", "индейка 15%", "рис", "жир индейки", "ягнёнок 3%"],
            "protein_pct": 25, "fat_pct": 13, "ash_pct": 7, "meat_estimate_pct": 52,
            "grain_free": False, "grain_sources": ["рис"], "price_per_kg": 600}
    analysis = generate_dry_food_analysis(food, dog)
    print(f"Разбор корма: {analysis}")
