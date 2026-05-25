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
    client = _get_client()
    if not client:
        return None
    # Пробуем модели по порядку (на Vertex AI не все могут быть включены)
    models_to_try = [GEMINI_MODEL] + [m for m in VERTEX_MODELS if m != GEMINI_MODEL]
    for model in models_to_try:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"max_output_tokens": max_tokens, "temperature": 0.3},
            )
            return response.text.strip()
        except Exception as e:
            if "NOT_FOUND" in str(e) or "not found" in str(e).lower():
                continue  # Модель не доступна, пробуем следующую
            print(f"Gemini error ({model}): {e}")
            return None
    print("Gemini: ни одна модель не доступна")
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

def generate_natural_intro(dog_name: str, breed: str, summary: str) -> str:
    """Персональное вступление для PDF с натуральным рационом."""
    result = _ask(f"""Напиши короткое (3-4 предложения) вступление для PDF-документа с натуральным рационом собаки.
Обращайся к владельцу на «вы». Упомяни кличку и породу. Объясни, почему рацион подобран именно так.
Тон: дружелюбный, профессиональный. Без emoji.

Кличка: {dog_name}
Порода: {breed}
Данные: {summary}""", max_tokens=2000)
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
    result = _ask(f"""Напиши краткие персональные рекомендации (5-7 пунктов) для владельца собаки по натуральному питанию.

Профиль:
{json.dumps(dog_profile, ensure_ascii=False)}

Предупреждения системы: {warnings}

Формат: маркированный список. Каждый пункт — 1-2 предложения.
Тон: дружелюбный, конкретный. Без воды. Без emoji.
Примеры пунктов:
- Почему выбраны именно эти продукты
- На что обращать внимание при кормлении
- Когда пересчитать рацион (вес изменился, возраст)
- Лайфхаки по хранению и закупке""", max_tokens=500)
    return result or ""


def generate_personal_analysis(dog_profile: dict, diet_summary: dict) -> str:
    """Генерирует полноценный персональный анализ для отдельной страницы PDF.
    Возвращает готовый HTML с блоками-карточками."""
    sex = dog_profile.get("sex", "male")
    gender_note = f"Пол собаки: {'девочка' if sex == 'female' else 'мальчик'}. Используй правильный род местоимений и глаголов ({'она, её, ей' if sex == 'female' else 'он, его, ему'})."

    result = _ask(f"""Ты — AI-система «Кусь», специализирующаяся на расчёте рационов для собак. Напиши глубокий персональный анализ рациона для владельца собаки.

ДОСЬЕ СОБАКИ:
{json.dumps(dog_profile, ensure_ascii=False, indent=2)}

ПОЛНЫЙ РЕЗУЛЬТАТ РАСЧЁТА:
{json.dumps(diet_summary, ensure_ascii=False, indent=2)}

ЗАДАЧА: Объясни владельцу, ПОЧЕМУ рацион составлен именно так. Не общие фразы, а конкретный анализ совокупности факторов этой собаки.

Формат — строго HTML, блоки <div class="insight">. Теги: breed, health, nutrition, lifestyle.

ОБЯЗАТЕЛЬНЫЕ БЛОКИ (если применимо к этой собаке):

1. ПОРОДА (tag: breed) — генетические предрасположенности именно этой породы. Склонность к ожирению, аллергиям, проблемам с суставами, сердцем, ЖКТ. Как это повлияло на расчёт.

2. ВЕС И КОНДИЦИЯ (tag: health) — текущий вес vs целевой, почему выбран именно такой целевой вес. Если перевес — почему снижена калорийность, насколько, и когда ожидать результат. Если недовес — почему увеличена.

3. ПОЧЕМУ ИМЕННО ЭТИ ПРОДУКТЫ (tag: nutrition) — объясни логику выбора: почему эти виды мяса, почему именно такое распределение по группам (мясо X%, кости Y%, овощи Z%). Если исключены продукты (стоп-лист/аллергии) — чем заменены и почему.

4. ДОБАВКИ (tag: nutrition) — почему назначены именно эти добавки с именно такими дозировками. Привяжи к конкретным факторам: «глюкозамин потому что крупная порода + перевес = нагрузка на суставы», «цинк потому что крупные породы склонны к дефициту», «витамин C потому что щенок крупной породы — профилактика HOD».

5. ЕСЛИ ЕСТЬ ДИАГНОЗЫ — отдельный блок (tag: health) на каждый значимый диагноз.

6. ЕСЛИ ПРОБЛЕМНЫЙ СТУЛ (tag: health) — возможные причины и что в рационе поможет.

7. ЕСЛИ ЩЕНОК (tag: lifestyle) — что сейчас критично (Ca:P, скорость роста, не перекормить). Когда пересчитать рацион.

8. ЕСЛИ БЕРЕМЕННОСТЬ/ЛАКТАЦИЯ (tag: health) — почему увеличена калорийность, на что обратить внимание.

9. ОБРАЗ ЖИЗНИ (tag: lifestyle) — конкретный совет на основе совокупности факторов.

Требования:
- {gender_note}
- Обращайся на «вы», упоминай кличку
- Каждый блок — 2-4 предложения, но содержательные
- Анализируй СОВОКУПНОСТЬ факторов, не каждый по отдельности
- Пиши экспертно, но доступно — без канцелярита и без воды
- Без emoji. Каждое предложение несёт конкретную информацию.
- Пиши 4-6 блоков в зависимости от количества значимых факторов
- НЕ пиши блоки про факторы, которых у этой собаки нет
- НЕ представляйся диетологом/ветеринаром. Ты — AI-система, и это нормально.

В конце ОБЯЗАТЕЛЬНО добавь:
<div class="insight" style="background:#fef3c7;border-color:#fbbf24;">
  <div class="tag health">Важно</div>
  <p>Данные рекомендации носят информационный характер и не являются ветеринарной консультацией. При наличии заболеваний или тревожных симптомов обратитесь к ветеринарному врачу.</p>
</div>""", max_tokens=2500)
    return result or ""


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

    prompt = (
        f"A friendly happy {breed} dog sitting and looking at camera, "
        f"3D Pixar-style illustration, warm soft lighting, white clean background, "
        f"cute expressive eyes, high quality render, no text, no humans, "
        f"professional pet portrait style"
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
