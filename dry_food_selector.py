"""
Подбор сухого корма по составу.
Выдаёт 3 корма в каждой ценовой категории (9 всего) с честным разбором.
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from declension import decline_name, decline

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load_json(filename: str):
    with open(os.path.join(DATA_DIR, filename), "r", encoding="utf-8") as f:
        return json.load(f)


def _balanced_chunks(items, maxsize=3):
    """Бьёт список на страницы по <= maxsize карточек, раскладывая ОСТАТОК поровну,
    чтобы не было полупустого «хвоста» из одинокой карточки.
    4 -> [2,2] (а не [3,1]), 5 -> [3,2], 7 -> [3,2,2]. Одинокая карточка только
    если в категории всего 1 корм. Проверено на переполнение: tools/measure_dry.py."""
    n = len(items)
    if n == 0:
        return []
    pages = (n + maxsize - 1) // maxsize  # минимум страниц
    base, rem = divmod(n, pages)          # base или base+1 карточек на страницу
    sizes = [base + 1] * rem + [base] * (pages - rem)
    chunks, i = [], 0
    for s in sizes:
        chunks.append(items[i:i + s])
        i += s
    return chunks


# ---------------------------------------------------------------------------
# Профиль собаки (вход)
# ---------------------------------------------------------------------------

@dataclass
class DogProfileDry:
    name: str
    breed: str
    age_months: int
    sex: str
    neutered: bool
    weight_kg: float
    condition: str          # thin / athletic / chubby / obese
    activity: str           # lazy / moderate / high / puppy
    diagnoses: list[str] = field(default_factory=list)
    stool: str = "good"
    stop_products: list[str] = field(default_factory=list)  # ["курица", "говядина"]
    size: str = ""          # mini / small / medium / large / giant (из породы)


# ---------------------------------------------------------------------------
# Результат
# ---------------------------------------------------------------------------

@dataclass
class FoodRecommendation:
    food: dict              # полный объект корма из базы
    score: float            # внутренний рейтинг (0-100)
    reasons_for: list[str]  # почему подходит
    reasons_against: list[str]  # на что обратить внимание
    meat_bar: int           # процент мяса для визуальной шкалы (0-100)


@dataclass
class DryFoodResult:
    dog: DogProfileDry
    budget: list[FoodRecommendation]     # корма "Честный бюджет"
    mid: list[FoodRecommendation]        # корма "Золотая середина"
    premium: list[FoodRecommendation]    # корма "Лучшее из лучшего"
    warnings: list[str]
    empty_categories: list[str] = field(default_factory=list)  # категории без подходящих кормов


# ---------------------------------------------------------------------------
# Селектор
# ---------------------------------------------------------------------------

SIZE_MAP = {
    "mini": "mini", "small": "small", "medium": "medium",
    "large": "large", "giant": "giant",
}

# Маппинг стоп-слов к аллергенам в базе кормов
STOP_TO_ALLERGEN = {
    "курица": "chicken", "курятина": "chicken",
    "говядина": "beef", "телятина": "beef",
    "кукуруза": "corn",
    "пшеница": "wheat",
    "соя": "soy",
    "рыба": "fish",
    "баранина": "lamb", "ягнёнок": "lamb",
}

# Частые аллергены: токен в allergens_absent -> корни для поиска в составе (рус.)
COMMON_ALLERGENS = {
    "chicken": ["куриц", "куриный", "птица", "птиц"],
    "beef": ["говядин", "говяж", "телятин"],
    "corn": ["кукуруз"],
    "wheat": ["пшениц", "пшеничн"],
    "soy": ["соя", "соев"],
}


def _food_has_common_allergen(food: dict) -> bool:
    """Корм содержит частый аллерген (курица/говядина/кукуруза/пшеница/соя),
    если он не гарантирован отсутствующим, а его след найден в составе."""
    absent = set(food.get("allergens_absent", []))
    haystack = " ".join(
        food.get("main_protein_sources", [])
        + food.get("grain_sources", [])
        + food.get("ingredients_top5", [])
    ).lower()
    for allergen, roots in COMMON_ALLERGENS.items():
        if allergen in absent:
            continue  # производитель гарантирует отсутствие
        if any(root in haystack for root in roots):
            return True
    return False


def _allergen_in_food(food: dict, allergen: str) -> tuple[list[str], list[str]]:
    """Где аллерген найден в ПОЛНОМ составе: (мясо/мука, жир).

    Различаем МЯСО/МУКУ (содержит белок — настоящий аллерген, исключаем) и ЖИР
    (рафинированный, без белка — обычно безопасен при чувствительности). Жир
    нельзя исключать (пул кормов рушится), но клиенту со стоп-листом — раскрыть.
    """
    roots = COMMON_ALLERGENS.get(allergen, [])
    ings = [i.lower() for i in (food.get("ingredients_top5", [])
            + food.get("main_protein_sources", []) + food.get("grain_sources", []))]
    meat = [i for i in ings if any(r in i for r in roots) and "жир" not in i]
    fat = [i for i in ings if any(r in i for r in roots) and "жир" in i]
    return meat, fat


class DryFoodSelector:

    def __init__(self):
        db = load_json("dry_foods.json")
        self.foods = db["foods"]
        self.breeds = load_json("breeds.json")
        self._breed_map = {b["name"]: b for b in self.breeds}

    def select(self, dog: DogProfileDry) -> DryFoodResult:
        # Определяем размер собаки
        if not dog.size:
            dog.size = self._detect_size(dog)

        # Определяем возрастную категорию
        age_cat = self._age_category(dog)

        # Фильтруем по базовым параметрам
        candidates = self._filter_candidates(dog, age_cat)

        def _by_price(items, cat):
            return [s for s in items if s[0]["price_category"] == cat]

        def _scored(foods):
            s = [(f, self._score(f, dog)) for f in foods]
            s.sort(key=lambda x: x[1], reverse=True)
            return s

        scored_strict = _scored(candidates)
        # Смягчённый по возрасту пул — добор при дефиците (аллергены/стоп НЕ трогаем)
        scored_relaxed = _scored(self._filter_candidates(dog, age_cat, relax_age=True))

        # Пул по категории: сначала строгие, потом доборные; дедуп по id и бренду.
        def pool(cat):
            seen_ids, seen_brands, out = set(), set(), []
            for src, is_relaxed in ((scored_strict, False), (scored_relaxed, True)):
                for food, score in src:
                    if food["price_category"] != cat:
                        continue
                    if food["id"] in seen_ids or food["brand"] in seen_brands:
                        continue
                    seen_ids.add(food["id"])
                    seen_brands.add(food["brand"])
                    out.append((food, score, is_relaxed))
            return out

        pools = {c: pool(c) for c in ("budget", "mid", "premium")}
        avail = {c: len(pools[c]) for c in pools}
        empty_categories = [c for c in ("budget", "mid", "premium") if avail[c] == 0]

        # Всегда стремимся показать 9 кормов: по 3 на категорию, а слоты пустых
        # категорий перераспределяем на непустые (в пределах доступного).
        TARGET = 9
        alloc = {c: min(3, avail[c]) for c in pools}
        # Перераспределяем оставшиеся слоты по кругу (баланс категорий)
        while sum(alloc.values()) < TARGET:
            progressed = False
            for c in ("mid", "premium", "budget"):
                if sum(alloc.values()) >= TARGET:
                    break
                if alloc[c] < avail[c]:
                    alloc[c] += 1
                    progressed = True
            if not progressed:
                break

        def build(cat):
            recs = []
            for food, score, _r in pools[cat][:alloc[cat]]:
                reasons_for, reasons_against = self._build_reasons(food, dog)
                recs.append(FoodRecommendation(
                    food=food,
                    score=round(score, 1),
                    reasons_for=reasons_for,
                    reasons_against=reasons_against,
                    meat_bar=food.get("meat_estimate_pct", 0),
                ))
            return recs

        budget_recs = build("budget")
        mid_recs = build("mid")
        premium_recs = build("premium")

        is_allergic = any("аллерг" in d.lower() for d in dog.diagnoses)
        relaxed_used = any(r for cat in pools for (_f, _s, r) in pools[cat][:alloc[cat]])
        warnings = self._generate_warnings(dog, scored_strict, relaxed_used, is_allergic)

        return DryFoodResult(
            dog=dog,
            budget=budget_recs,
            mid=mid_recs,
            premium=premium_recs,
            warnings=warnings,
            empty_categories=empty_categories,
        )

    # --- Определение размера ---

    def _detect_size(self, dog: DogProfileDry) -> str:
        breed_info = self._breed_map.get(dog.breed)
        if breed_info:
            return breed_info.get("size", "medium")
        # По весу
        if dog.weight_kg < 5:
            return "mini"
        elif dog.weight_kg < 10:
            return "small"
        elif dog.weight_kg < 25:
            return "medium"
        elif dog.weight_kg < 45:
            return "large"
        return "giant"

    # --- Возрастная категория ---

    def _age_category(self, dog: DogProfileDry) -> str:
        breed_info = self._breed_map.get(dog.breed)
        adult_months = 12
        senior_years = 8
        if breed_info:
            adult_months = breed_info.get("adult_months", 12)
            senior_years = breed_info.get("senior_years", 8)

        if dog.age_months < adult_months:
            return "puppy"
        elif dog.age_months >= senior_years * 12:
            return "senior"
        return "adult"

    # --- Фильтрация ---

    def _filter_candidates(self, dog: DogProfileDry, age_cat: str,
                           relax_age: bool = False) -> list[dict]:
        result = []
        stop_allergens = self._stop_to_allergens(dog.stop_products)
        is_allergic = any("аллерг" in d.lower() for d in dog.diagnoses)

        for food in self.foods:
            # Размер
            if dog.size not in food.get("size_suitable", []):
                # Giant подходит к large, mini — к small
                size_compatible = False
                if dog.size == "giant" and "large" in food.get("size_suitable", []):
                    size_compatible = True
                if dog.size == "mini" and "small" in food.get("size_suitable", []):
                    size_compatible = True
                if not size_compatible:
                    continue

            # Возраст (relax_age снимает ограничение — fallback при дефиците кормов)
            if not relax_age and age_cat not in food.get("age_suitable", []):
                # senior может есть adult корм
                if not (age_cat == "senior" and "adult" in food.get("age_suitable", [])):
                    continue

            # Стоп-продукты. Исключаем корм, если стоп-белок встречается в ПОЛНОМ
            # составе как МЯСО/МУКА (не только в main_protein_sources — раньше так
            # просачивалось вторичное мясо). ЖИР не исключаем (без белка, безопасен;
            # клиенту раскрываем в reasons). allergens_absent = гарантия без белка.
            food_allergens_absent = set(food.get("allergens_absent", []))
            has_allergen = False
            for allergen in stop_allergens:
                if allergen in food_allergens_absent:
                    continue
                meat, _fat = _allergen_in_food(food, allergen)
                if meat:
                    has_allergen = True
                    break
            if has_allergen:
                continue

            # Аллергия без указанных аллергенов: исключаем корма с частыми
            # аллергенами (курица/говядина/кукуруза/пшеница/соя)
            if is_allergic and _food_has_common_allergen(food):
                continue

            # Доступность
            if food.get("availability_ru") == "unavailable":
                continue

            result.append(food)

        return result

    # --- Скоринг ---

    def _score(self, food: dict, dog: DogProfileDry) -> float:
        score = 0.0

        # 1. Процент мяса (макс 30 баллов)
        meat = food.get("meat_estimate_pct", 0)
        score += min(meat * 0.5, 30)

        # 2. Отсутствие splitting (5 баллов)
        if not food.get("splitting_detected", False):
            score += 5

        # 3. Натуральные консерванты (5 баллов)
        if "натуральн" in food.get("preservatives", "").lower():
            score += 5

        # 4. Зольность < 7.5 (5 баллов)
        if food.get("ash_pct", 10) <= 7.5:
            score += 5

        # 5. Стабильность поставок (10 баллов)
        avail = food.get("availability_ru", "")
        if avail == "stable":
            score += 10
        elif avail == "unstable":
            score += 3

        # 6. Гипоаллергенность. «Тяжёлая аллергия» = диагноз аллергии ИЛИ стоп на
        # ≥2 белка (мульти-аллергик). Для таких собак гидролизат — самый безопасный
        # вариант (белок расщеплён), но он низкомясный и иначе проигрывает по %мяса,
        # поэтому сильно поднимаем, чтобы он гарантированно был в опциях.
        high_allergy = (any("аллерг" in d.lower() for d in dog.diagnoses)
                        or len(dog.stop_products) >= 2)
        traits = food.get("special_traits", [])
        if high_allergy:
            if "hypoallergenic" in traits:
                score += 10
            if "single_protein" in traits:
                score += 5
            if "hydrolyzed" in traits:
                score += 25  # гарантируем гидролизат в подборке тяжёлым аллергикам

        # 7. Контроль веса (бонус для толстых собак)
        if dog.condition in ("chubby", "obese"):
            if food.get("fat_pct", 20) <= 13:
                score += 8
            if "weight_control" in food.get("special_traits", []):
                score += 5

        # 8. Суставы (бонус для крупных)
        if dog.size in ("large", "giant"):
            if "joint_support" in food.get("special_traits", []):
                score += 5

        # 9. Шерсть/кожа (бонус если проблемы)
        if dog.stool == "loose" or any("дерматит" in d.lower() for d in dog.diagnoses):
            if "skin_coat" in food.get("special_traits", []):
                score += 5

        # 10. Беззерновой (небольшой бонус)
        if food.get("grain_free", False):
            score += 3

        # 11. Белок > 28% (бонус для активных)
        if dog.activity in ("high", "puppy") and food.get("protein_pct", 0) >= 28:
            score += 5

        # 12. Штраф за кукурузу
        grains = food.get("grain_sources", [])
        if "кукуруза" in grains:
            score -= 5

        return score

    # --- Причины рекомендации ---

    def _build_reasons(self, food: dict, dog: DogProfileDry) -> tuple[list[str], list[str]]:
        pros = []
        cons = []
        meat = food.get("meat_estimate_pct", 0)

        # Мясо. Для гидролизатных лечебных диет %мяса не применим (белок расщеплён,
        # это не мускульное мясо) — не считаем «мало мяса» минусом.
        if "hydrolyzed" in food.get("special_traits", []):
            pros.append("Лечебный гидролизат — белок расщеплён, гипоаллергенный")
        elif meat >= 55:
            pros.append(f"{meat}% мяса — отличный показатель")
        elif meat >= 40:
            pros.append(f"{meat}% мяса — хороший показатель")
        elif meat >= 25:
            pros.append(f"{meat}% мяса — приемлемо для ценовой категории")
        else:
            cons.append(f"Всего {meat}% мяса — невысокий показатель")

        # Белки
        proteins = ", ".join(food.get("main_protein_sources", []))
        pros.append(f"Основной белок: {proteins}")

        # Аллергии
        stop_allergens = self._stop_to_allergens(dog.stop_products)
        absent = food.get("allergens_absent", [])
        for allergen in stop_allergens:
            names = {"chicken": "курицы", "beef": "говядины", "corn": "кукурузы",
                     "wheat": "пшеницы", "soy": "сои", "lamb": "ягнёнка", "fish": "рыбы"}
            if allergen in absent:
                pros.append(f"Без {names.get(allergen, allergen)}")
            # Раскрываем стоп-жир (без белка): не протечка, но клиент должен знать.
            _meat, fat = _allergen_in_food(food, allergen)
            if fat:
                cons.append(f"Содержит жир {names.get(allergen, allergen)} "
                            f"(рафинированный, без белка — обычно безопасен при чувствительности)")

        # Злаки
        grains = food.get("grain_sources", [])
        if not grains:
            pros.append("Беззерновой")
        elif grains == ["рис"]:
            pros.append("Один злак (рис) — мягкий для ЖКТ")
        elif "кукуруза" in grains:
            cons.append("Содержит кукурузу")

        # Splitting
        if food.get("splitting_detected"):
            cons.append("Обнаружен splitting ингредиентов (занижение зерновых)")

        # Доступность
        if food.get("availability_ru") == "unstable":
            cons.append("Поставки в РФ бывают нестабильны")
        elif food.get("availability_ru") == "stable":
            pros.append("Стабильные поставки в РФ")

        # Особые нужды собаки
        if dog.condition in ("chubby", "obese"):
            fat = food.get("fat_pct", 20)
            if fat <= 13:
                pros.append(f"Пониженная жирность ({fat}%) — хорошо для снижения веса")
            elif fat >= 18:
                cons.append(f"Жирность {fat}% — высоковата для собаки с лишним весом")

        if dog.size in ("large", "giant") and "joint_support" in food.get("special_traits", []):
            pros.append("Глюкозамин и хондроитин для суставов")

        # Из базы
        for p in food.get("pros", []):
            if p not in pros:
                pros.append(p)
        for c in food.get("cons", []):
            if c not in cons:
                cons.append(c)

        return pros[:6], cons[:4]  # Ограничиваем количество

    # --- Предупреждения ---

    def _generate_warnings(self, dog: DogProfileDry, scored: list,
                           relaxed_used: bool = False,
                           is_allergic: bool = False) -> list[str]:
        warnings = []
        if not scored:
            warnings.append("Не удалось найти подходящие корма. Попробуйте ослабить ограничения.")
        if is_allergic:
            warnings.append(
                "У собаки аллергия, конкретные аллергены не указаны — мы исключили "
                "корма с курицей, говядиной, кукурузой, пшеницей и соей. Если знаете "
                "точный аллерген, укажите его — подбор станет точнее."
            )
        if relaxed_used:
            warnings.append(
                "Гипоаллергенных кормов для этого размера/возраста в продаже немного, "
                "поэтому в некоторых категориях показаны корма для всех возрастов. "
                "Для щенка уточните норму на упаковке."
            )
        if dog.diagnoses:
            warnings.append("У собаки есть диагнозы — рекомендуем согласовать выбор корма с ветеринаром.")
        if dog.condition == "obese":
            warnings.append("При ожирении важно строго соблюдать нормы кормления. Не завышайте порции!")
        return warnings

    # --- Утилиты ---

    def _stop_to_allergens(self, stop_products: list[str]) -> set[str]:
        result = set()
        for stop in stop_products:
            s = stop.lower().strip()
            if s in STOP_TO_ALLERGEN:
                result.add(STOP_TO_ALLERGEN[s])
            else:
                # Пробуем по корню
                for key, val in STOP_TO_ALLERGEN.items():
                    if key[:3] in s or s[:3] in key:
                        result.add(val)
        return result


# ---------------------------------------------------------------------------
# Генерация PDF (HTML)
# ---------------------------------------------------------------------------

PRICE_LABELS = {
    "budget": ("Честный бюджет", "до 400 руб/кг"),
    "mid": ("Золотая середина", "400-800 руб/кг"),
    "premium": ("Лучшее из лучшего", "от 800 руб/кг"),
}

CONDITION_LABELS_DRY = {"thin": "недовес", "athletic": "норма", "chubby": "лёгкий перевес", "obese": "ожирение"}
ACTIVITY_LABELS_DRY = {"lazy": "низкая", "moderate": "средняя", "high": "высокая", "puppy": "щенок"}

_SVG_PAW_DRY = '<svg width="{w}" height="{w}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="9" r="1.6"/><circle cx="10" cy="6" r="1.6"/><circle cx="14" cy="6" r="1.6"/><circle cx="18" cy="9" r="1.6"/><path d="M8.5 14c0-2 1.6-3.5 3.5-3.5s3.5 1.5 3.5 3.5c0 1.6 1 2.2 1 3.5 0 1.4-1.2 2-2.6 2-1 0-1.4-.5-1.9-.5s-.9.5-1.9.5C8.7 19.5 7.5 18.9 7.5 17.5c0-1.3 1-1.9 1-3.5z"/></svg>'
_SVG_CHECK_DRY = '<svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>'
_SVG_WARN_DRY = '<svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>'
_SVG_STAR = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 5.6L20 10l-5.6 2.4L12 18l-2.4-5.6L4 10l5.6-2.4z"/></svg>'
_SVG_STAR_SM = '<svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 5.6L20 10l-5.6 2.4L12 18l-2.4-5.6L4 10l5.6-2.4z"/></svg>'


def _dry_page_head(meta_text: str) -> str:
    return f'''<div class="page-head">
    <div class="logo">
      <span class="mark">{_SVG_PAW_DRY.format(w=16)}</span>
      <span class="name">Кусь</span>
    </div>
    <div class="meta">{meta_text}</div>
  </div>'''


def _renumber_pages(html: str) -> str:
    """Проставляет сквозные номера страниц по факту собранных секций.

    Каждый футер/обложка содержит плейсхолдеры §PG§ (порядковый номер) и §TOT§
    (всего). Считаем реальное число секций и нумеруем их по порядку — номера
    больше не «врут» при разбивке категорий на несколько страниц.
    """
    total = html.count("§PG§")
    counter = {"i": 0}

    def _next(_m):
        counter["i"] += 1
        return str(counter["i"])

    html = re.sub("§PG§", _next, html)
    html = html.replace("§TOT§", str(total))
    return html


def _dry_page_foot(num: int, total: int, doc_id: str) -> str:
    # Номер и общее число страниц проставляются динамически в конце сборки
    # (см. _renumber_pages): секций может быть больше из-за разбивки категорий.
    return f'<div class="page-foot">стр. <strong>§PG§</strong> / §TOT§ · Кусь · {doc_id}</div>'


def generate_dry_food_html(result: DryFoodResult) -> str:
    dog = result.dog
    today = date.today().strftime("%d.%m.%Y")
    from pdf_generator import _fmt_age
    age_text = _fmt_age(dog.age_months)
    sex_text = "мальчик" if dog.sex == "male" else "девочка"
    doc_id = f"Подбор {dog.name}"

    # Склонения клички
    name = dog.name
    name_g = decline_name(dog.name, "gent", dog.sex)
    name_d = decline_name(dog.name, "datv", dog.sex)
    name_a = decline_name(dog.name, "accs", dog.sex)
    total_pages = 10
    total_foods = len(result.budget) + len(result.mid) + len(result.premium)
    total_foods_in_db = len(load_json("dry_foods.json")["foods"])
    stop_text = ", ".join(dog.stop_products) if dog.stop_products else "нет"

    # --- Detect food photo ---
    STATIC_DIR = os.path.join(os.path.dirname(__file__), "static", "dry-foods")
    _photo_cache = {}
    _SVG_BAG = '<svg width="44" height="52" viewBox="0 0 48 56" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M12 16 Q12 10 18 10 L20 7 H28 L30 10 Q36 10 36 16 L38 50 Q38 52 36 52 H12 Q10 52 10 50 Z"/><rect x="17" y="22" width="14" height="10" rx="1.5" stroke-width="1.4"/><path d="M14 38 H34 M14 42 H30" stroke-width="1.2" stroke-linecap="round"/><circle cx="22" cy="9" r="0.8" fill="currentColor"/><circle cx="26" cy="9" r="0.8" fill="currentColor"/></svg>'
    def _food_photo_tag(food_id: str) -> str:
        # Встраиваем картинку как base64-миниатюру: отчёт остаётся самодостаточным
        # (открывается standalone-файлом / в headless-браузере / в PDF без живого сервера).
        if food_id not in _photo_cache:
            tag = _SVG_BAG
            for ext in ("jpg", "png", "webp"):
                path = os.path.join(STATIC_DIR, f"{food_id}.{ext}")
                if not os.path.exists(path):
                    continue
                try:
                    import base64
                    from io import BytesIO
                    from PIL import Image
                    img = Image.open(path)
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    img.thumbnail((240, 240), Image.LANCZOS)  # карточка ~16×20мм
                    buf = BytesIO()
                    img.save(buf, format="JPEG", quality=72, optimize=True)
                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                    tag = (f'<img src="data:image/jpeg;base64,{b64}" alt="" '
                           f'style="width:100%;height:100%;object-fit:contain;'
                           f'position:relative;z-index:1;">')
                except Exception:
                    tag = _SVG_BAG
                break
            _photo_cache[food_id] = tag
        return _photo_cache[food_id]

    # --- Food card builder ---
    def food_card(rec: FoodRecommendation, rank: int, cat_label: str, is_best_overall: bool = False) -> str:
        f = rec.food
        meat_pct = f.get('meat_estimate_pct', 0)
        brand = f.get('brand', '')
        formula = f.get('name', '')
        country = f.get('country', '')
        price = f.get('price_per_kg', '?')

        # Badges
        badges_html = ""
        if f.get('grain_free'):
            badges_html += '<span class="badge green">Беззерновой</span>'
        if 'hypoallergenic' in f.get('special_traits', []):
            badges_html += '<span class="badge blue">Гипоаллергенный</span>'
        if is_best_overall:
            badges_html += '<span class="badge amber">★ Лучший</span>'

        # Nutrients
        nutri_html = f'''<div class="nutri">
          <div class="n"><span class="lbl">Белок</span> <strong>{f.get("protein_pct", "?")}%</strong></div>
          <div class="n"><span class="lbl">Жир</span> <strong>{f.get("fat_pct", "?")}%</strong></div>
          <div class="n"><span class="lbl">Зола</span> <strong>{f.get("ash_pct", "?")}%</strong></div>
          <div class="n"><span class="lbl">Клетчатка</span> <strong>{f.get("fiber_pct", "?")}%</strong></div>
        </div>'''

        # Ingredients
        ingredients_text = ", ".join(f.get("ingredients_top5", []))
        ingredients_html = f'<div class="ingredients"><strong>Первые 5:</strong> {ingredients_text}</div>'

        # Pros/cons — use table wrapper for 2-column grid
        pros_items = ""
        cons_items = ""
        for p in rec.reasons_for:
            pros_items += f'<div class="pc pro"><span class="ic">{_SVG_CHECK_DRY}</span>{p}</div>\n'
        for c in rec.reasons_against:
            cons_items += f'<div class="pc con"><span class="ic">{_SVG_WARN_DRY}</span>{c}</div>\n'

        all_pc = []
        for p in rec.reasons_for:
            all_pc.append(f'<div class="pc pro"><span class="ic">{_SVG_CHECK_DRY}</span>{p}</div>')
        for c in rec.reasons_against:
            all_pc.append(f'<div class="pc con"><span class="ic">{_SVG_WARN_DRY}</span>{c}</div>')

        # Build 2-column table for proscons
        proscons_rows = ""
        for i in range(0, len(all_pc), 2):
            left = all_pc[i] if i < len(all_pc) else ""
            right = all_pc[i + 1] if i + 1 < len(all_pc) else ""
            proscons_rows += f"<tr><td>{left}</td><td>{right}</td></tr>\n"

        proscons = f'<table class="proscons-t"><tbody>{proscons_rows}</tbody></table>' if all_pc else ''

        # AI block
        ai_text = getattr(rec, 'ai_analysis', '') or (rec.reasons_for[0] if rec.reasons_for else "")
        ai_html = f'''<div class="ai-block">
          <div class="ai-h"><span class="ai-ico">{_SVG_STAR_SM}</span>Чем подходит</div>
          {ai_text}
        </div>'''

        # Buy links
        links = f.get("buy_links") or {}
        buy_html = '<div class="buy-row">'
        if links.get("ozon"):
            buy_html += f'<a class="buy-btn primary" href="https://{links["ozon"]}">Купить на Ozon <span class="arr">→</span></a>'
        if links.get("wb"):
            buy_html += f'<a class="buy-btn" href="https://{links["wb"]}">Wildberries <span class="arr">→</span></a>'
        if links.get("4paws"):
            buy_html += f'<a class="buy-btn" href="https://{links["4paws"]}">Четыре лапы <span class="arr">→</span></a>'
        buy_html += '</div>'

        rank_meta = f"{cat_label}<br/>лучший" if rank == 1 else cat_label
        border_style = ' style="border: 1.5px solid var(--primary);"' if is_best_overall else ''

        return f'''<div class="food"{border_style}>
      <table class="food-layout"><tr>
      <td>
        <div class="rank"><span class="hash">#</span>{rank}</div>
        <div class="rank-meta">{rank_meta}</div>
      </td>
      <td>
        <div class="bag-photo">
          {_food_photo_tag(f.get('id', ''))}
        </div>
      </td>
      <td><div class="body">
        <div class="top">
          <div>
            <div class="brand">{brand}</div>
            <div class="formula">{formula}</div>
            <div class="origin">
              <span>{country}</span><span class="sep"></span><span>~{price} ₽/кг</span>
            </div>
          </div>
          <div class="badges">{badges_html}</div>
        </div>

        <table class="meat-scale-t"><tr>
        <td><div class="meat-bar">
            <div class="meat-fill" style="width: {min(meat_pct, 100)}%;"></div>
            <div class="meat-label">% мяса</div>
        </div></td>
        <td class="meat-pct-cell"><div class="meat-pct">{meat_pct}<span class="small">%</span></div></td>
        </tr></table>

        {nutri_html}
        {ingredients_html}
        <div class="proscons">{proscons}</div>
        {ai_html}
        {buy_html}
      </div></td>
      </tr></table>
    </div>'''

    # --- Category page builder ---
    is_allergic = any("аллерг" in d.lower() for d in dog.diagnoses)

    def category_page(foods, cat_key, cat_css, page_num, best_overall_idx=-1):
        label, price_range = PRICE_LABELS[cat_key]
        cat_num = {"budget": 1, "mid": 2, "premium": 3}[cat_key]
        cat_names = {"budget": "бюджет", "mid": "среднее", "premium": "премиум"}
        price_big = {"budget": "≤ 400 ₽", "mid": "400–800 ₽", "premium": "≥ 800 ₽"}[cat_key]
        cat_sub = {"budget": "Хороший базовый рацион без переплаты за бренд.",
                    "mid": "Лучший баланс цена / состав. Рекомендуем как основу.",
                    "premium": "Холистики и супер-премиум: максимум мяса, минимум углеводов."}[cat_key]

        banner = f'''<div class="cat-banner {cat_css}">
    <div class="left">
      <div class="eyebrow-line">Категория {cat_num} · {label.lower()}</div>
      <div class="ttl">Корма {price_range}</div>
      <div class="sub">{cat_sub}</div>
    </div>
    <div class="price">
      <div class="big">{price_big}</div>
      <div class="sml">за килограмм</div>
    </div>
  </div>'''

        if not foods:
            # Страница-заглушка: честно объясняем, почему в категории пусто
            stub_extra = ""
            if is_allergic and cat_key == "budget":
                stub_title = "В этой ценовой категории мы ничего не рекомендуем"
                stub_text = (
                    f"У {name_g} аллергия, а гипоаллергенных кормов дешевле "
                    f"{price_big.replace('≤ ', '').replace('≥ ', '')}/кг в России "
                    f"по сути нет. Это не упущение подбора, а устройство рынка."
                )
                stub_hint = ("Экономия здесь обернётся лечением кожи и ЖКТ. "
                             "Лучше взять корм из средней или премиум-категории — "
                             "мы подобрали их с запасом.")
                stub_extra = '''
    <table class="stub-cols"><tr>
      <td>
        <div class="stub-h">Что чаще всего вызывает аллергию</div>
        <ul class="stub-list">
          <li><b>Курица</b> и куриное яйцо — аллерген №1</li>
          <li><b>Говядина</b> и молочные продукты</li>
          <li><b>Пшеница и кукуруза</b> — дешёвые злаки-наполнители</li>
          <li><b>Соя</b></li>
        </ul>
      </td>
      <td>
        <div class="stub-h">Почему дёшево = аллергенно</div>
        <p class="stub-p">Дешёвый корм дешёв именно потому, что сделан из самого доступного сырья — курицы, субпродуктов, кукурузы и пшеницы. А это и есть главные аллергены. Гипоаллергенный рацион требует <b>одного редкого белка</b> (ягнёнок, лосось, оленина) и <b>отказа от зерна</b> — такие компоненты дороже по определению, поэтому дешёвыми они не бывают.</p>
      </td>
    </tr></table>'''
            else:
                stub_title = "Подходящих кормов в этой категории не нашлось"
                stub_text = (
                    f"Под параметры {name_g} (размер, возраст и ограничения) в этой "
                    f"ценовой категории корма с честным составом не попали."
                )
                stub_hint = "Смотрите другие категории — там есть достойные варианты."

            return f'''<section class="page">
  {_dry_page_head(f"<strong>Категория {cat_num} / 3</strong> · {cat_names[cat_key]}")}

  {banner}

  <div class="stub-card">
    <div class="stub-ico">{_SVG_WARN_DRY}</div>
    <div class="stub-title">{stub_title}</div>
    <p class="stub-text">{stub_text}</p>
    <div class="stub-hint">{stub_hint}</div>
    {stub_extra}
  </div>

  {_dry_page_foot(page_num, total_pages, doc_id)}
</section>'''

        # 2 карточки на лист: в Chromium (движок, которым клиент печатает «Сохранить
        # PDF») 3 карточки НЕ влезают в A4 и вытекают на 2-ю страницу, ломая сквозную
        # нумерацию. Проверка — рендером Chromium, tools/report_qa. Остаток делим
        # балансно (4 -> 2+2). Одинокая карточка при 3 кормах в категории пока
        # неизбежна (2+1) — открытый вопрос #3 по компоновке «хвоста».
        chunks = _balanced_chunks(foods, maxsize=2)
        sections = []
        gi = 0  # сквозной номер корма в категории (чанки разного размера)
        for ci, chunk in enumerate(chunks):
            cards = ""
            for rec in chunk:
                is_best = (gi == best_overall_idx)
                cards += food_card(rec, gi + 1, cat_names[cat_key], is_best)
                gi += 1
            part = f" · часть {ci + 1}/{len(chunks)}" if len(chunks) > 1 else ""
            sections.append(f'''<section class="page">
  {_dry_page_head(f"<strong>Категория {cat_num} / 3</strong> · {cat_names[cat_key]}{part}")}

  {banner if ci == 0 else ''}

  <div class="foods">
    {cards}
  </div>

  {_dry_page_foot(page_num, total_pages, doc_id)}
</section>''')
        return "\n".join(sections)

    # --- Build comparison table ---
    best_budget = result.budget[0] if result.budget else None
    best_mid = result.mid[0] if result.mid else None
    best_premium = result.premium[0] if result.premium else None

    def _cell(rec, key, default="—"):
        if not rec:
            return default
        return rec.food.get(key, default)

    # Лучший общий — берём из непустой категории (mid → premium → budget)
    best_overall = best_mid or best_premium or best_budget
    _cat_label = {"budget": "Честный бюджет", "mid": "Золотая середина",
                  "premium": "Премиум"}.get(
                      best_overall.food.get("price_category") if best_overall else "", "Наш выбор")
    # Бюджетная альтернатива — только если она есть
    budget_alt = (f' Если бюджет ограничен — <strong>{_cell(best_budget, "brand")}</strong> '
                  f'({_cell(best_budget, "price_per_kg")} ₽/кг) достойная альтернатива.'
                  if best_budget else '')

    compare_html = ""
    if best_budget and best_mid and best_premium:
        compare_html = f'''<div class="compare-wrap">
    <table class="compare">
      <thead>
        <tr>
          <th></th>
          <th class="col">Бюджет<span class="sub">≤ 400 ₽/кг</span></th>
          <th class="col winner head">Среднее<span class="sub">400–800 ₽/кг</span><span class="winner-tag">★ выбор</span></th>
          <th class="col">Премиум<span class="sub">≥ 800 ₽/кг</span></th>
        </tr>
      </thead>
      <tbody>
        <tr><td class="k">Корм</td><td>{_cell(best_budget, "brand")}</td><td class="winner"><strong>{_cell(best_mid, "brand")}</strong></td><td>{_cell(best_premium, "brand")}</td></tr>
        <tr><td class="k">Мясо</td><td>~{_cell(best_budget, "meat_estimate_pct", 0)}%</td><td class="winner"><strong>~{_cell(best_mid, "meat_estimate_pct", 0)}%</strong></td><td>~{_cell(best_premium, "meat_estimate_pct", 0)}%</td></tr>
        <tr><td class="k">Белок / жир</td><td>{_cell(best_budget, "protein_pct", "?")}% / {_cell(best_budget, "fat_pct", "?")}%</td><td class="winner"><strong>{_cell(best_mid, "protein_pct", "?")}% / {_cell(best_mid, "fat_pct", "?")}%</strong></td><td>{_cell(best_premium, "protein_pct", "?")}% / {_cell(best_premium, "fat_pct", "?")}%</td></tr>
        <tr><td class="k">Цена за кг</td><td>{_cell(best_budget, "price_per_kg", "?")} ₽</td><td class="winner"><strong>{_cell(best_mid, "price_per_kg", "?")} ₽</strong></td><td>{_cell(best_premium, "price_per_kg", "?")} ₽</td></tr>
      </tbody>
    </table>
  </div>'''

    # --- Profile rows ---
    condition_text = CONDITION_LABELS_DRY.get(dog.condition, dog.condition)
    condition_chip = ""
    if dog.condition == "chubby":
        condition_chip = '<span class="chip warn">перевес</span>'
    elif dog.condition == "obese":
        condition_chip = '<span class="chip bad">ожирение</span>'

    stop_chip = ""
    if dog.stop_products:
        stop_chip = '<span class="chip bad">аллергия</span>'

    # --- Full CSS (from original design, adapted for WeasyPrint) ---
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8" />
<title>Кусь · Подбор сухого корма · {dog.name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
<style>
:root {{
  --primary: #055ba9;
  --primary-dark: #04467f;
  --primary-soft: #e6f0fa;
  --primary-softer: #f3f8fd;
  --accent: #f59e0b;
  --accent-deep: #d97706;
  --accent-soft: #fef3c7;
  --accent-softer: #fffbeb;
  --ink: #0b1726;
  --ink-soft: #475569;
  --ink-light: #94a3b8;
  --border: #e2e8f0;
  --border-soft: #eef2f7;
  --bg: #ffffff;
  --bg-soft: #f7f9fc;
  --bg-warm: #fdfbf7;
  --green: #16a34a;
  --green-soft: #dcfce7;
  --red: #dc2626;
  --red-soft: #fee2e2;
  --amber: #d97706;
  --meat-from: #055ba9;
  --meat-to: #7cc2f0;
}}
* {{ box-sizing: border-box; }}
html, body {{
  margin: 0; padding: 0;
  background: #e6e9ef;
  font-family: "Golos Text", system-ui, sans-serif;
  color: var(--ink);
  font-size: 11pt;
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}}
.mono {{ font-family: "JetBrains Mono", ui-monospace, monospace; }}

/* Print toolbar */
.toolbar {{
  position: fixed;
  top: 16px; right: 16px;
  z-index: 100;
  display: flex; gap: 8px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 8px;
  box-shadow: 0 12px 30px -12px rgba(11,23,38,0.25);
}}
.toolbar button {{
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}}
.toolbar .hint {{
  font-size: 11px;
  color: var(--ink-light);
  align-self: center;
  padding: 0 6px;
}}

/* A4 page */
.page {{
  width: 210mm;
  min-height: 297mm;
  margin: 16px auto;
  background: #fff;
  position: relative;
  padding: 12mm 14mm 16mm;
  box-shadow: 0 12px 32px -16px rgba(11,23,38,0.25);
  page-break-after: always;
  break-after: page;
  zoom: var(--page-zoom, 1);
}}
.page:last-of-type {{ page-break-after: auto; }}

.page-foot {{
  position: absolute;
  left: 0; right: 0; bottom: 8mm;
  text-align: center;
  font-size: 8pt;
  color: var(--ink-light);
  letter-spacing: 0.05em;
}}
.page-foot strong {{ color: var(--ink-soft); font-weight: 600; }}

.page-head {{
  margin-bottom: 4mm;
  padding-bottom: 3mm;
  border-bottom: 1px solid var(--border-soft);
}}
.page-head .meta {{ float: right; }}
.page-head .logo {{ display: inline-block; }}
.page-head .logo .mark {{
  width: 26px; height: 26px;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  display: inline-block; text-align: center; line-height: 26px;
  vertical-align: middle; margin-right: 6px;
}}
.page-head .logo .mark svg {{ vertical-align: middle; }}
.page-head .logo .name {{
  font-weight: 800;
  font-size: 16px;
  color: var(--primary);
  letter-spacing: -0.02em;
  vertical-align: middle;
}}
.page-head .meta {{
  font-size: 9pt;
  color: var(--ink-light);
}}
.page-head .meta strong {{ color: var(--ink-soft); font-weight: 600; }}

/* Typography */
h1, h2, h3, h4 {{ margin: 0; letter-spacing: -0.02em; color: var(--ink); }}
h1 {{ font-size: 34pt; font-weight: 800; line-height: 1.02; letter-spacing: -0.035em; }}
h2 {{ font-size: 22pt; font-weight: 700; line-height: 1.1; }}
h3 {{ font-size: 14pt; font-weight: 700; }}
h4 {{ font-size: 11pt; font-weight: 700; }}
p {{ margin: 0; }}

.eyebrow {{
  display: inline-block;
  font-size: 9pt;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--primary);
  background: var(--primary-soft);
  padding: 5px 12px;
  border-radius: 100px;
}}
.section-title {{
  font-size: 16pt;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--ink);
  margin-bottom: 3mm;
}}
.section-sub {{
  font-size: 9.5pt;
  color: var(--ink-soft);
  margin-bottom: 5mm;
  max-width: 145mm;
}}

/* Cover */
.cover {{ padding: 0; }}
.cover .top-bar {{
  height: 6mm;
  background: linear-gradient(90deg, var(--primary) 0%, var(--primary) 55%, var(--accent) 100%);
}}
.cover-inner {{ padding: 14mm 16mm 14mm; }}
.cover-head {{
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 16mm;
}}
.cover-head .logo .name {{ font-size: 22px; }}
.cover-head .logo .mark {{ width: 34px; height: 34px; border-radius: 10px; }}
.cover-head .doc-id {{
  text-align: right;
  font-size: 9pt;
  color: var(--ink-light);
  line-height: 1.6;
}}
.cover-head .doc-id .label {{
  display: inline-block;
  font-size: 8pt;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--primary);
  background: var(--primary-soft);
  padding: 4px 10px;
  border-radius: 100px;
  margin-bottom: 6px;
}}
.cover-title-block {{ max-width: 140mm; }}
.cover-title-block .kicker {{
  font-size: 11pt;
  color: var(--ink-soft);
  font-weight: 500;
  margin-bottom: 6mm;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}}
.cover-title-block .kicker .dot {{
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--accent);
}}
.cover-title-block .dog-name {{
  font-size: 56pt;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 0.95;
  color: var(--primary);
  margin: 4mm 0 6mm;
}}
.cover-title-block .breed {{
  font-size: 14pt;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 4mm;
}}
.cover-stats {{
  display: inline-flex;
  align-items: center;
  gap: 10mm;
  font-size: 11pt;
  color: var(--ink-soft);
}}
.cover-stats .stat strong {{ font-size: 14pt; font-weight: 700; color: var(--ink); white-space: nowrap; }}
.cover-stats .stat div {{ white-space: nowrap; }}
.cover-stats .divider {{ width: 1px; height: 24px; background: var(--border); }}

.cover-badge {{
  display: inline-block;
  margin-top: 8mm;
  padding: 8px 16px;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
  font-size: 10pt;
  border-radius: 100px;
  letter-spacing: -0.005em;
  white-space: nowrap;
}}
.cover-badge .dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #fff; vertical-align: middle; margin-right: 6px; }}

/* Cover photo — WeasyPrint adapted */
.cover-photo {{
  margin-top: 10mm;
  border-radius: 14px;
  overflow: hidden;
  max-height: 60mm;
  background: linear-gradient(135deg, var(--primary-soft), var(--bg-warm));
  position: relative;
}}
.cover-photo img {{ width: 100%; height: auto; display: block; border-radius: 14px; }}
.float-card {{
  display: inline-block;
  margin-top: -12mm;
  margin-left: 8mm;
  position: relative;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 10px 14px;
  box-shadow: 0 4px 12px -4px rgba(11,23,38,0.15);
}}
.float-card .ico {{
  width: 32px; height: 32px;
  border-radius: 8px;
  background: var(--primary-soft);
  color: var(--primary);
  display: inline-block; text-align: center; line-height: 32px; vertical-align: middle; margin-right: 10px;
}}
.float-card .label {{ font-size: 8pt; color: var(--ink-soft); display: inline-block; vertical-align: middle; }}
.float-card .val {{ font-size: 11pt; font-weight: 700; color: var(--ink); display: inline-block; vertical-align: middle; margin-left: 4px; }}

.cover-footer {{
  position: absolute;
  left: 16mm; right: 16mm; bottom: 12mm;
  display: flex; justify-content: space-between; align-items: center;
  font-size: 8.5pt;
  color: var(--ink-light);
  border-top: 1px solid var(--border-soft);
  padding-top: 5mm;
}}

/* Profile — table wrapper for WeasyPrint */
.profile-grid-t {{ width: 100%; border-collapse: separate; border-spacing: 4mm 0; margin-bottom: 7mm; }}
.profile-grid-t td {{ width: 50%; vertical-align: top; }}
.profile-card {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  padding: 5mm 6mm;
}}
.profile-card-wide {{ margin-bottom: 4mm; }}
.profile-cols {{ width: 100%; border-collapse: collapse; }}
.profile-cols td {{ width: 50%; vertical-align: top; padding: 0 6mm; }}
.profile-cols td:first-child {{ border-right: 1px solid var(--border-soft); padding-left: 0; }}
.profile-card .hd {{
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 4mm;
  padding-bottom: 4mm;
  border-bottom: 1px solid var(--border-soft);
}}
.profile-card .hd .av {{
  width: 44px; height: 44px;
  border-radius: 12px;
  background: var(--primary-soft);
  color: var(--primary);
  display: inline-flex; align-items: center; justify-content: center;
}}
.profile-card .hd .nm {{ font-size: 14pt; font-weight: 800; letter-spacing: -0.02em; color: var(--ink); }}
.profile-card .hd .sub {{ font-size: 9pt; color: var(--ink-light); margin-top: 2px; }}
.profile-row {{
  padding: 6px 0;
  border-bottom: 1px dashed var(--border-soft);
  font-size: 10pt;
}}
.profile-row:last-child {{ border-bottom: none; }}
.profile-row .k {{ color: var(--ink-soft); }}
.profile-row .v {{ font-weight: 700; color: var(--ink); }}
.profile-row .v .chip {{
  display: inline-block;
  font-size: 8.5pt;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 100px;
  margin-left: 4px;
}}
.chip.warn {{ background: var(--accent-soft); color: var(--accent-deep); }}
.chip.bad {{ background: var(--red-soft); color: var(--red); }}
.chip.ok {{ background: var(--green-soft); color: var(--green); }}

.ai-quote {{
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: #fff;
  border-radius: 14px;
  padding: 6mm 7mm;
  position: relative;
  display: flex; flex-direction: column;
  gap: 4mm;
}}
.ai-quote::before {{
  content: "\u201C";
  position: absolute;
  top: -8mm; right: 6mm;
  font-size: 90pt;
  font-weight: 800;
  color: rgba(255,255,255,0.16);
  line-height: 1;
}}
.ai-quote .ai-tag {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 8pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  padding: 4px 10px;
  border-radius: 100px;
  background: rgba(255,255,255,0.18);
  align-self: flex-start;
}}
.ai-quote p {{
  font-size: 11pt;
  line-height: 1.55;
  font-weight: 500;
}}
.ai-quote .signoff {{
  font-size: 9pt;
  color: rgba(255,255,255,0.7);
  display: flex; align-items: center; gap: 8px;
}}
.ai-quote .signoff .dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--accent); }}

/* Steps — table wrapper for WeasyPrint */
.steps-grid {{
  gap: 4mm;
}}
.steps-grid-t {{ width: 100%; border-collapse: separate; border-spacing: 3mm 0; }}
.steps-grid-t td {{ width: 33%; vertical-align: top; }}
.step {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  padding: 5mm;
  position: relative;
}}
.step .num {{
  position: absolute;
  top: 4mm; right: 5mm;
  font-size: 22pt;
  font-weight: 800;
  color: var(--primary-soft);
  letter-spacing: -0.03em;
  line-height: 1;
}}
.step .ico {{
  width: 36px; height: 36px;
  border-radius: 10px;
  background: var(--primary-soft);
  color: var(--primary);
  display: inline-flex; align-items: center; justify-content: center;
  margin-bottom: 4mm;
}}
.step .ttl {{ font-size: 11pt; font-weight: 700; color: var(--ink); margin-bottom: 2mm; }}
.step .txt {{ font-size: 9.5pt; color: var(--ink-soft); line-height: 1.5; }}
.step .txt strong {{ color: var(--ink); font-weight: 700; }}

/* Cat strip — table wrapper for WeasyPrint */
.cat-strip {{
  margin-top: 6mm;
}}
.cat-strip-t {{ margin-top: 6mm; width: 100%; border-collapse: separate; border-spacing: 2mm 0; }}
.cat-strip-t td {{ vertical-align: top; }}
.cat-pill {{
  padding: 8px 10px;
  border-radius: 10px;
  font-size: 8.5pt;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
}}
.cat-pill.budget {{ background: #eef2f7; }}
.cat-pill.middle {{ background: var(--primary-soft); color: var(--primary-dark); }}
.cat-pill.premium {{ background: var(--accent-soft); color: var(--accent-deep); }}
.cat-pill .swatch {{
  display: inline-block;
  width: 8px; height: 8px; border-radius: 50%;
  vertical-align: middle;
  margin-right: 4px;
}}
.cat-pill.budget .swatch {{ background: #64748b; }}
.cat-pill.middle .swatch {{ background: var(--primary); }}
.cat-pill.premium .swatch {{ background: var(--accent); }}
.cat-pill .cnt {{ font-size: 8.5pt; font-weight: 600; opacity: 0.7; white-space: nowrap; }}

/* Category banner */
.cat-banner {{
  margin-bottom: 3mm;
  padding: 3mm 6mm;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: space-between;
  gap: 6mm;
}}
.cat-banner.budget {{ background: #eef2f7; }}
.cat-banner.middle {{ background: var(--primary-soft); }}
.cat-banner.premium {{ background: var(--accent-soft); }}

/* Заглушка для пустой категории */
.stub-card {{
  margin-top: 14mm;
  padding: 12mm 14mm;
  border: 1.5px dashed var(--border);
  border-radius: 14px;
  background: #fcfdfe;
  text-align: center;
}}
.stub-ico {{
  width: 44px; height: 44px; margin: 0 auto 6mm;
  color: var(--accent);
}}
.stub-ico svg {{ width: 44px; height: 44px; }}
.stub-title {{ font-size: 14pt; font-weight: 700; color: var(--ink); margin-bottom: 4mm; }}
.stub-text {{ font-size: 11pt; line-height: 1.6; color: var(--ink-soft); max-width: 130mm; margin: 0 auto 6mm; }}
.stub-hint {{
  display: inline-block;
  font-size: 10.5pt; font-weight: 600; color: var(--primary);
  background: var(--primary-soft);
  padding: 8px 16px; border-radius: 100px;
}}
.stub-cols {{ width: 100%; border-collapse: collapse; margin-top: 10mm; text-align: left; }}
.stub-cols td {{ width: 50%; vertical-align: top; padding: 0 5mm; }}
.stub-cols td:first-child {{ border-right: 1px solid var(--border-soft); }}
.stub-h {{ font-size: 10.5pt; font-weight: 700; color: var(--ink); margin-bottom: 3mm; }}
.stub-list {{ margin: 0; padding-left: 5mm; font-size: 10pt; line-height: 1.7; color: var(--ink-soft); }}
.stub-p {{ margin: 0; font-size: 10pt; line-height: 1.6; color: var(--ink-soft); }}
.cat-banner .left .eyebrow-line {{
  font-size: 8pt;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-soft);
  margin-bottom: 1.5mm;
}}
.cat-banner.budget .left .eyebrow-line {{ color: #475569; }}
.cat-banner.middle .left .eyebrow-line {{ color: var(--primary-dark); }}
.cat-banner.premium .left .eyebrow-line {{ color: var(--accent-deep); }}
.cat-banner .left .ttl {{
  font-size: 14pt;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--ink);
  line-height: 1;
}}
.cat-banner .left .sub {{
  font-size: 8pt;
  color: var(--ink-soft);
  margin-top: 1mm;
  max-width: 130mm;
  line-height: 1.4;
}}
.cat-banner .price {{
  text-align: right;
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-weight: 500;
}}
.cat-banner .price .big {{
  font-size: 13pt;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.02em;
}}
.cat-banner .price .sml {{ font-size: 8.5pt; color: var(--ink-soft); }}

/* Food card */
.foods {{ display: flex; flex-direction: column; gap: 2mm; }}
.food {{
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 2.5mm 4mm 3mm;
  page-break-inside: avoid;
  break-inside: avoid;
  position: relative;
}}
.food-layout {{ width: 100%; border-collapse: collapse; }}
.food-layout td {{ vertical-align: top; padding: 0 1.5mm; }}
.food-layout td:first-child {{ width: 9mm; }}
.food-layout td:nth-child(2) {{ width: 16mm; }}
.food .rank {{
  font-size: 22pt;
  font-weight: 800;
  color: var(--primary);
  letter-spacing: -0.05em;
  line-height: 0.9;
  font-feature-settings: "tnum";
}}
.food .rank .hash {{
  font-size: 11pt;
  font-weight: 700;
  color: var(--primary-soft);
  vertical-align: super;
  margin-right: -2px;
}}
.food .rank-meta {{
  font-size: 6.5pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ink-light);
  margin-top: 2mm;
  line-height: 1.2;
}}

/* Bag placeholder photo */
.bag-photo {{
  width: 16mm; height: 20mm;
  border-radius: 7px;
  background: linear-gradient(180deg, #f1f4f9 0%, #e2e8f0 100%);
  border: 1px solid var(--border);
  position: relative;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
  box-shadow: inset 0 -5mm 4mm -4mm rgba(11,23,38,0.06);
}}
.bag-photo::before {{
  content: "";
  position: absolute; inset: 0;
  background-image: repeating-linear-gradient(
    -45deg,
    transparent 0 6px,
    rgba(148,163,184,0.08) 6px 7px
  );
}}
.bag-photo svg {{ position: relative; z-index: 1; color: var(--ink-light); }}
.bag-photo img {{ border-radius: 6px; }}
.bag-photo .ph-label {{
  position: absolute;
  bottom: 0.5mm;
  left: 50%;
  transform: translateX(-50%);
  font-size: 5pt;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink-light);
  font-family: "JetBrains Mono", ui-monospace, monospace;
  white-space: nowrap;
}}

.food .body {{ min-width: 0; }}
.food .top {{
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 4mm;
  margin-bottom: 2mm;
}}
.food .brand {{
  font-size: 12.5pt;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--ink);
  line-height: 1.05;
}}
.food .formula {{
  font-size: 9pt;
  color: var(--ink-soft);
  font-weight: 500;
  margin-top: 0.5mm;
}}
.food .origin {{
  font-size: 8pt;
  color: var(--ink-light);
  margin-top: 1mm;
  display: flex; align-items: center; gap: 6px;
  font-feature-settings: "tnum";
}}
.food .origin .sep {{ width: 3px; height: 3px; border-radius: 50%; background: var(--ink-light); }}
.food .badges {{ display: flex; gap: 4px; flex-wrap: wrap; flex-shrink: 0; }}
.badge {{
  font-size: 7pt;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 100px;
  letter-spacing: 0.02em;
  white-space: nowrap;
}}
.badge.green {{ background: var(--green-soft); color: var(--green); }}
.badge.blue {{ background: var(--primary-soft); color: var(--primary); }}
.badge.amber {{ background: var(--accent-soft); color: var(--accent-deep); }}

/* Meat scale — table wrapper for WeasyPrint */
.meat-scale-t {{
  width: 100%;
  border-collapse: collapse;
  margin: 1.5mm 0;
}}
.meat-scale-t td {{ vertical-align: middle; padding: 0; }}
.meat-scale-t .meat-pct-cell {{ width: 30px; text-align: right; padding-left: 8px; }}
.meat-bar {{
  position: relative;
  height: 6mm;
  background: var(--bg-soft);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  overflow: hidden;
}}
.meat-fill {{
  position: absolute;
  left: 0; top: 0; bottom: 0;
  background: linear-gradient(90deg, var(--meat-from) 0%, var(--meat-to) 100%);
  border-radius: 6px 0 0 6px;
}}
.meat-fill::after {{
  content: "";
  position: absolute; right: 0; top: 0; bottom: 0;
  width: 3px;
  background: #fff;
  box-shadow: 1px 0 0 rgba(11,23,38,0.06);
}}
.meat-label {{
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 7pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #fff;
  /* Тёмная обводка-halo: лейбл читается и на синей заливке, и на светлой части
     полосы (при низком % мяса заливка короче лейбла), и поверх белого разделителя. */
  text-shadow:
    0 0 1px rgba(11,23,38,0.9),
    0 0 2px rgba(11,23,38,0.65),
    0 1px 1px rgba(11,23,38,0.55);
  z-index: 2;
}}
.meat-pct {{
  font-size: 14pt;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--primary);
  font-feature-settings: "tnum";
  line-height: 1;
}}
.meat-pct .small {{
  font-size: 9pt;
  font-weight: 600;
  color: var(--ink-light);
  letter-spacing: 0;
  margin-left: 2px;
}}

/* Nutrient line */
.nutri {{
  display: flex; flex-wrap: wrap;
  gap: 0;
  margin: 1mm 0 1.5mm;
  font-size: 8pt;
  color: var(--ink-soft);
}}
.nutri .n {{
  padding: 0 8px 0 0;
  margin-right: 8px;
  border-right: 1px solid var(--border);
  font-feature-settings: "tnum";
}}
.nutri .n:last-child {{ border-right: none; margin-right: 0; }}
.nutri .n strong {{
  display: inline-block;
  color: var(--ink);
  font-weight: 700;
  margin-left: 2px;
}}
.nutri .n .lbl {{ color: var(--ink-light); }}

.ingredients {{
  font-size: 7.5pt;
  color: var(--ink-soft);
  line-height: 1.4;
  font-style: italic;
  margin-bottom: 1.5mm;
  padding-left: 7px;
  border-left: 2px solid var(--border);
}}
.ingredients strong {{ font-style: normal; font-weight: 700; color: var(--ink); }}
.ingredients .pct {{ font-weight: 700; color: var(--primary); font-style: normal; }}

/* Proscons — table wrapper for 2-column grid */
.proscons {{ margin-bottom: 1.5mm; }}
.proscons-t {{ width: 100%; border-collapse: collapse; }}
.proscons-t td {{ vertical-align: top; padding: 0.25mm 2mm 0.25mm 0; }}
.pc {{
  display: flex; align-items: flex-start; gap: 5px;
  font-size: 7.5pt;
  line-height: 1.3;
  color: var(--ink);
}}
.pc .ic {{
  flex: 0 0 auto;
  width: 11px; height: 11px;
  border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  margin-top: 1px;
}}
.pc.pro .ic {{ background: var(--green-soft); color: var(--green); }}
.pc.con .ic {{ background: var(--accent-soft); color: var(--accent-deep); }}

.ai-block {{
  background: var(--primary-softer);
  border-left: 3px solid var(--primary);
  border-radius: 6px;
  padding: 2mm 3mm;
  font-size: 8pt;
  line-height: 1.35;
  color: var(--ink);
  margin-bottom: 2mm;
}}
.ai-block .ai-h {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 7pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--primary);
  margin-right: 6px;
  vertical-align: 1px;
}}
.ai-block .ai-h .ai-ico {{
  width: 11px; height: 11px;
  border-radius: 3px;
  background: var(--primary);
  color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
}}

.buy-row {{
  display: flex; gap: 5px;
  flex-wrap: wrap;
}}
.buy-btn {{
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 8pt;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 6px;
  text-decoration: none;
  letter-spacing: -0.005em;
  border: 1px solid var(--primary);
  color: var(--primary);
  background: #fff;
}}
.buy-btn.primary {{ background: var(--primary); color: #fff; }}
.buy-btn .arr {{ font-size: 10pt; line-height: 1; margin-left: 1px; transform: translateY(-1px); }}

/* Final recommendation */
.hero-rec {{
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: #fff;
  border-radius: 14px;
  padding: 6mm 7mm;
  position: relative;
  margin-bottom: 5mm;
  overflow: hidden;
}}
.hero-rec::before {{
  content: "";
  position: absolute;
  right: -30mm; top: -30mm;
  width: 100mm; height: 100mm;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(245,158,11,0.35), transparent 60%);
}}
.hero-rec .tag {{
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 8pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  padding: 4px 10px;
  border-radius: 100px;
  background: var(--accent);
  color: var(--ink);
  margin-bottom: 4mm;
}}
.hero-rec h3 {{
  color: #fff;
  font-size: 20pt;
  line-height: 1.1;
  margin-bottom: 3mm;
}}
.hero-rec p {{
  font-size: 10pt;
  line-height: 1.5;
  color: rgba(255,255,255,0.92);
  max-width: 140mm;
}}
.hero-rec p strong {{ color: #fff; font-weight: 700; }}

.compare-wrap {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  overflow: hidden;
}}
.compare {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin-top: 4mm;
  font-size: 10pt;
}}
.compare th, .compare td {{
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-soft);
}}
.compare thead th {{
  font-size: 9pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ink);
  background: var(--bg-soft);
}}
.compare thead th:first-child {{ border-top-left-radius: 10px; }}
.compare thead th:last-child {{ border-top-right-radius: 10px; }}
.compare tbody td.k {{
  color: var(--ink-soft);
  font-weight: 600;
  font-size: 9.5pt;
  background: var(--bg-soft);
}}
.compare tbody tr:last-child td {{ border-bottom: none; }}
.compare tbody td {{
  font-feature-settings: "tnum";
  color: var(--ink);
}}
.compare tbody td strong {{ font-weight: 700; }}
.compare .winner {{
  background: var(--primary-softer);
  position: relative;
}}
.compare .winner.head {{
  background: var(--primary);
  color: #fff !important;
  border-color: var(--primary) !important;
  text-shadow: 0 1px 0 rgba(0,0,0,0.1);
}}
.compare th.col {{
  font-feature-settings: "tnum";
  letter-spacing: -0.005em;
  text-transform: none;
  font-size: 11pt;
  font-weight: 800;
  color: var(--ink);
}}
.compare th.col .sub {{
  display: block;
  font-size: 8pt;
  font-weight: 600;
  color: var(--ink-light);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-top: 2px;
}}
.compare th.col.winner .sub {{ color: #fff; opacity: 0.85; }}
.compare .winner-tag {{
  display: inline-block;
  font-size: 7pt;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  padding: 2px 8px;
  border-radius: 100px;
  background: var(--accent);
  color: var(--ink);
  margin-top: 4px;
}}

/* Transition */
.transition-strip {{
  margin-bottom: 6mm;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 16px;
  padding: 6mm 7mm;
}}
.transition-track {{
  margin-bottom: 5mm;
}}
.transition-track-t {{ width: 100%; border-collapse: separate; border-spacing: 2mm 0; margin-bottom: 5mm; }}
.transition-track-t td {{ width: 25%; vertical-align: top; }}
.tr-step-bar {{
  display: flex; flex-direction: column;
  align-items: stretch;
  gap: 2mm;
}}
.tr-step-bar .days {{
  font-size: 9pt;
  font-weight: 700;
  color: var(--ink);
  display: flex; align-items: baseline; gap: 6px;
}}
.tr-step-bar .days .num {{
  font-size: 20pt;
  font-weight: 800;
  color: var(--primary);
  letter-spacing: -0.04em;
  line-height: 1;
  font-feature-settings: "tnum";
}}
.tr-step-bar .days .lbl {{
  font-size: 8.5pt;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ink-light);
}}
.tr-mix {{
  width: 100%;
  height: 12mm;
  border-collapse: collapse;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  table-layout: fixed;
}}
.tr-mix td {{
  text-align: center;
  vertical-align: middle;
  color: #fff;
  font-size: 9pt;
  font-weight: 700;
  padding: 0;
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
}}
.tr-mix .old {{
  background: #b8c4d4;
  text-shadow: 0 1px 0 rgba(11,23,38,0.2);
}}
.tr-mix .new {{
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
}}
.tr-legend {{
  display: flex; justify-content: center;
  gap: 5mm;
  font-size: 8.5pt;
  color: var(--ink-soft);
  margin-top: 4mm;
  padding-top: 4mm;
  border-top: 1px solid var(--border-soft);
}}
.tr-legend .sw {{
  display: inline-block;
  width: 14px; height: 10px;
  border-radius: 3px;
  margin-right: 6px;
  vertical-align: middle;
}}
.tr-legend .sw.old {{ background: #b8c4d4; }}
.tr-legend .sw.new {{ background: linear-gradient(135deg, var(--primary), var(--primary-dark)); }}

/* Tips — table wrapper for WeasyPrint */
.tips-grid-t {{ width: 100%; border-collapse: separate; border-spacing: 3mm; }}
.tips-grid-t td {{ vertical-align: top; }}
.tip {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 5mm 6mm;
  display: flex; gap: 12px; align-items: flex-start;
}}
.tip .ic {{
  flex: 0 0 auto;
  width: 34px; height: 34px;
  border-radius: 10px;
  background: var(--primary-soft);
  color: var(--primary);
  display: inline-flex; align-items: center; justify-content: center;
}}
.tip.warn .ic {{ background: var(--accent-soft); color: var(--accent-deep); }}
.tip h4 {{ font-size: 11pt; margin-bottom: 2mm; }}
.tip p {{ font-size: 9.5pt; color: var(--ink-soft); line-height: 1.5; }}
.tip p strong {{ color: var(--ink); font-weight: 700; }}

/* Last page */
.last-page {{ background: var(--bg-soft); }}
.disclaimer-card {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  padding: 8mm;
  margin-bottom: 6mm;
  position: relative;
}}
.disclaimer-card .quote {{
  position: absolute;
  top: -8px; left: 6mm;
  font-size: 36pt;
  font-weight: 800;
  color: var(--primary);
  line-height: 1;
}}
.disclaimer-card p {{
  font-size: 10.5pt;
  line-height: 1.6;
  color: var(--ink);
  font-style: italic;
  padding-left: 14mm;
}}

/* Contact grid — table wrapper for WeasyPrint */
.contact-grid-t {{ width: 100%; border-collapse: separate; border-spacing: 3mm 0; }}
.contact-grid-t td {{ vertical-align: top; }}
.contact-card {{
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 6mm;
  display: flex; flex-direction: column; gap: 4mm;
  align-items: flex-start;
}}
.contact-card .ico {{
  width: 44px; height: 44px;
  border-radius: 12px;
  background: var(--primary-soft);
  color: var(--primary);
  display: inline-flex; align-items: center; justify-content: center;
}}
.contact-card .label {{ font-size: 8.5pt; color: var(--ink-light); text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600; }}
.contact-card .val {{ font-size: 13pt; font-weight: 700; color: var(--ink); letter-spacing: -0.01em; }}

/* Support strip — table wrapper for WeasyPrint */
.support-strip {{
  margin-top: 6mm;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: #fff;
  border-radius: 16px;
  padding: 8mm 10mm;
}}
.support-strip h3 {{ color: #fff; font-size: 18pt; margin-bottom: 3mm; }}
.support-strip p {{ font-size: 11pt; line-height: 1.5; color: rgba(255,255,255,0.85); }}

.bye {{
  text-align: center;
  margin-top: 8mm;
  padding-top: 6mm;
  border-top: 1px solid var(--border-soft);
  font-size: 9pt;
  color: var(--ink-light);
}}
.bye .heart {{ color: var(--accent); }}

@media (max-width: 820px) {{
  body {{ background: #eef0f4; }}
  .page {{
    margin: 10px auto;
    box-shadow: 0 6px 18px -8px rgba(11,23,38,0.25);
  }}
  .toolbar {{
    top: auto; right: 12px; bottom: 12px;
    padding: 6px;
    border-radius: 10px;
  }}
  .toolbar .hint {{ display: none; }}
  .toolbar button {{ padding: 9px 13px; font-size: 12px; }}
}}
@page {{ size: A4 portrait; margin: 8mm; }}
@media print {{
  html, body {{ background: #fff; }}
  .toolbar {{ display: none !important; }}
  .page {{
    margin: 0;
    box-shadow: none;
    width: auto;
    min-height: auto;
    max-height: none;
    zoom: 1 !important;
    padding: 8mm 10mm 10mm;
    page-break-after: always;
    break-after: page;
  }}
  .page:last-of-type {{ page-break-after: auto; break-after: auto; }}
  .food {{ page-break-inside: avoid; break-inside: avoid; margin-bottom: 6mm; }}
  .cat-header {{ page-break-inside: avoid; break-inside: avoid; }}
  .cover-photo {{ print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
  .cat-banner, .hero-rec, .ai-quote, .support-strip, .transition-strip {{ print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
  .meat-fill {{ print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
  .tr-mix .old, .tr-mix .new {{ print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
  * {{ print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
}}
</style>
</head>
<body>

<div class="toolbar">
  <span class="hint">A4 · §TOT§ страниц</span>
  <button onclick="window.print()">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
    Печать / Сохранить PDF
  </button>
</div>

<script>
  (function () {{
    var PAGE_W_PX = 794;
    function fit() {{
      var vw = document.documentElement.clientWidth;
      var sidePad = 20;
      if (vw < PAGE_W_PX + sidePad * 2) {{
        var scale = Math.max(0.3, Math.min(1, (vw - sidePad) / PAGE_W_PX));
        document.documentElement.style.setProperty('--page-zoom', scale.toFixed(4));
      }} else {{
        document.documentElement.style.setProperty('--page-zoom', 1);
      }}
    }}
    fit();
    window.addEventListener('resize', fit);
    window.addEventListener('orientationchange', fit);
  }})();
</script>


<!-- PAGE 1 — COVER -->
<section class="page cover">
  <div class="top-bar"></div>
  <div class="cover-inner">
    <div class="cover-head">
      <div class="logo">
        <span class="mark">{_SVG_PAW_DRY.format(w=20)}</span>
        <span class="name">Кусь</span>
      </div>
      <div class="doc-id">
        <div class="label">{doc_id}</div>
        <div>составлен {today}</div>
      </div>
    </div>
    <div class="cover-title-block">
      <div class="kicker"><span class="dot"></span> Подбор сухого корма</div>
      <div class="dog-name">{dog.name}</div>
      <div class="breed">{dog.breed}</div>
      <div class="cover-stats">
        <div class="stat"><strong>{age_text}</strong><div style="font-size:9pt;color:var(--ink-light);">возраст</div></div>
        <div class="divider"></div>
        <div class="stat"><strong>{dog.weight_kg} кг</strong><div style="font-size:9pt;color:var(--ink-light);">текущий вес</div></div>
        <div class="divider"></div>
        <div class="stat"><strong>{ACTIVITY_LABELS_DRY.get(dog.activity, dog.activity)}</strong><div style="font-size:9pt;color:var(--ink-light);">активность</div></div>
        <div class="divider"></div>
        <div class="stat"><strong>{stop_text}</strong><div style="font-size:9pt;color:var(--ink-light);">стоп-продукт</div></div>
      </div>
      <div style="margin-top: 6mm;">
        <span class="cover-badge"><span class="dot"></span>{total_foods} лучших кормов · 3 ценовые категории</span>
      </div>
    </div>
    <div class="cover-photo">
      {'<img src="data:image/png;base64,' + getattr(result, 'cover_image_b64', '') + '" alt="' + name + '">' if getattr(result, 'cover_image_b64', '') else ''}
    </div>
    <div class="float-card">
      <div class="ico">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
      </div>
      <div style="display:inline-block;vertical-align:middle;">
        <div class="label">Отобрано из</div>
        <div class="val">{total_foods_in_db} кормов</div>
      </div>
    </div>
  </div>
  <div class="cover-footer">
    <div>kus.dogfine.ru · @doggifood_bot</div>
    <div>Кусь · Подбор сухого корма</div>
    <div>стр. §PG§ / §TOT§</div>
  </div>
</section>

<!-- PAGE 2 — PROFILE -->
<section class="page">
  {_dry_page_head(f"<strong>{dog.name}</strong> · {dog.breed}, {age_text}, {dog.weight_kg} кг · {doc_id}")}

  <div class="eyebrow">Профиль и метод подбора</div>
  <h2 class="section-title" style="margin-top: 4mm;">Почему именно эти корма для {name_g}</h2>
  <p class="section-sub">{getattr(result, 'ai_intro', '') or 'Мы не продаём корма — анализируем составы по открытым данным производителей и подбираем под параметры конкретной собаки. По реальным ингредиентам видно, за что вы платите.'}</p>

  <div class="profile-card profile-card-wide">
    <div class="hd">
      <div class="av">{_SVG_PAW_DRY.format(w=22)}</div>
      <div>
        <div class="nm">{dog.name}</div>
        <div class="sub">Профиль собаки</div>
      </div>
    </div>
    <table class="profile-cols"><tr>
      <td>
        <div class="profile-row"><span class="k">Порода</span><span class="v" style="float:right;">{dog.breed}</span></div>
        <div class="profile-row"><span class="k">Возраст</span><span class="v" style="float:right;">{age_text}</span></div>
        <div class="profile-row"><span class="k">Вес</span><span class="v" style="float:right;">{dog.weight_kg} кг</span></div>
      </td>
      <td>
        <div class="profile-row"><span class="k">Кондиция</span><span class="v" style="float:right;">{condition_text} {condition_chip}</span></div>
        <div class="profile-row"><span class="k">Активность</span><span class="v" style="float:right;">{ACTIVITY_LABELS_DRY.get(dog.activity, dog.activity)}</span></div>
        <div class="profile-row"><span class="k">Стоп-продукты</span><span class="v" style="float:right;">{stop_text} {stop_chip}</span></div>
      </td>
    </tr></table>
  </div>

  <h3 style="font-size: 12pt; margin: 6mm 0 4mm;">Как мы подбирали</h3>
  <table class="steps-grid-t">
    <tr><td><div class="step">
      <div class="num">01</div>
      <div class="ico"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 5h18l-7 9v6l-4-2v-4z"/></svg></div>
      <div class="ttl">Фильтр по параметрам</div>
      <div class="txt">Отсеяли корма по возрасту, весу, размеру породы и стоп-продуктам {name_g}.</div>
    </div></td>
    <td><div class="step">
      <div class="num">02</div>
      <div class="ico"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg></div>
      <div class="ttl">Разбор состава</div>
      <div class="txt">Считаем <strong>% реального мяса</strong>, оцениваем источники.</div>
    </div></td>
    <td><div class="step">
      <div class="num">03</div>
      <div class="ico"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 5.6L20 8l-4.2 4 1 5.8L12 15l-4.8 2.8 1-5.8L4 8l5.6-0.4z"/></svg></div>
      <div class="ttl">Лучшие в каждой категории</div>
      <div class="txt">По <strong>цене за кг</strong> разделили на бюджет, среднее и премиум.</div>
    </div></td>
    </tr>
  </table>

  <table class="cat-strip-t">
    <tr>
    <td><div class="cat-pill budget"><span class="swatch"></span> Честный бюджет · <span class="cnt">до 400 ₽/кг</span></div></td>
    <td><div class="cat-pill middle"><span class="swatch"></span> Золотая середина · <span class="cnt">400–800 ₽/кг</span></div></td>
    <td><div class="cat-pill premium"><span class="swatch"></span> Лучшее из лучшего · <span class="cnt">от 800 ₽/кг</span></div></td>
    </tr>
  </table>

  {_dry_page_foot(2, total_pages, doc_id)}
</section>

<!-- PAGE 3 — BUDGET -->
{category_page(result.budget, "budget", "budget", 3)}

<!-- PAGE 4 — MID -->
{category_page(result.mid, "mid", "middle", 4, best_overall_idx=0)}

<!-- PAGE 5 — PREMIUM -->
{category_page(result.premium, "premium", "premium", 5)}

<!-- PAGE 6 — RECOMMENDATION -->
<section class="page">
  {_dry_page_head("<strong>Итоговая рекомендация</strong>")}

  <div class="eyebrow">Если бы мы сами выбирали {name_d}</div>
  <h2 class="section-title" style="margin-top: 4mm;">Лучший выбор и альтернатива</h2>

  <div class="hero-rec">
    <span class="tag">{_SVG_STAR} Наш выбор</span>
    <h3>{_cell(best_overall, "brand", "—")}<br/>{_cell(best_overall, "name", "")}</h3>
    <p>{getattr(result, 'ai_conclusion', '') or f'{_cat_label} · ~{_cell(best_overall, "price_per_kg", "?")} ₽/кг. <strong>~{_cell(best_overall, "meat_estimate_pct", "?")}% мяса</strong>, жирность <strong>{_cell(best_overall, "fat_pct", "?")}%</strong>.{budget_alt}'}</p>
  </div>

  {'<h3 style="font-size: 12pt; margin-bottom: 3mm;">Лучшее из каждой категории — рядом</h3>' + compare_html if compare_html else ''}

  {_dry_page_foot(6, total_pages, doc_id)}
</section>

<!-- PAGE 7 — HOW TO CHOOSE -->
<section class="page">
  {_dry_page_head("<strong>Как выбирать сухой корм</strong> · памятка")}

  <div class="eyebrow">На будущее</div>
  <h2 class="section-title" style="margin-top: 4mm;">Как читать состав и не вестись на упаковку</h2>
  <p class="section-sub">Этой памятки хватит, чтобы оценить любой корм в магазине самостоятельно — без нас.</p>

  <table class="tips-grid-t">
    <tr><td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h16M4 18h10"/></svg></div>
      <div><h4>Читайте состав по порядку</h4><p>Ингредиенты идут по убыванию массы. На первых 2–3 местах должно стоять <strong>мясо с указанием вида и %</strong> («дегидрированная индейка 26%»), а не зерно.</p></div>
    </div></td>
    <td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg></div>
      <div><h4>Конкретика, а не «мука»</h4><p>«Дегидрированное мясо ягнёнка» — хорошо. «Мясо и продукты животного происхождения» без вида — плохо: непонятно, что внутри.</p></div>
    </div></td></tr>
    <tr><td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg></div>
      <div><h4>Цифры, на которые смотреть</h4><p>Зола <strong>≤ 8%</strong>, понятные консерванты (токоферолы — витамин E), без сахара и ароматизаторов. % мяса важнее громкого бренда.</p></div>
    </div></td>
    <td><div class="tip warn">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg></div>
      <div><h4>Красные флаги</h4><p>Кукуруза/пшеница на первых местах, сахар, целлюлоза, и «сплиттинг» — когда зерно дробят на 3–4 строчки, чтобы спрятать его реальную долю.</p></div>
    </div></td></tr>
    <tr><td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 14l3-3 3 3 4-5"/></svg></div>
      <div><h4>Гарантированный анализ</h4><p>На обороте ищите цифры: <strong>белок 26–32%</strong>, жир 12–18%, клетчатка ≤ 5%. Слишком мало белка — корм «разбавлен» зерном.</p></div>
    </div></td>
    <td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M2 12h20"/></svg></div>
      <div><h4>«Беззерновой» — не синоним «лучше»</h4><p>Grain-free часто просто меняет зерно на горох/картофель. Смотрите на <strong>долю мяса</strong>, а не на громкую надпись на лицевой стороне.</p></div>
    </div></td></tr>
    <tr><td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg></div>
      <div><h4>Калорийность = размер порции</h4><p>Смотрите <strong>ккал/100 г</strong>. Чем калорийнее корм, тем меньше порция — и наоборот. По этой цифре считается суточная норма, а не «на глаз».</p></div>
    </div></td>
    <td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></div>
      <div><h4>Срок и условия хранения</h4><p>Берите упаковку со <strong>свежей датой</strong> и закрывайте герметично. Прогорклый жир — частая причина отказа от еды и расстройства ЖКТ.</p></div>
    </div></td></tr>
  </table>

  {_dry_page_foot(7, total_pages, doc_id)}
</section>

<!-- PAGE 8 — HOW TO FEED -->
<section class="page">
  {_dry_page_head("<strong>Как кормить сухим кормом</strong> · правила")}

  <div class="eyebrow">Правила кормления</div>
  <h2 class="section-title" style="margin-top: 4mm;">Чтобы корм работал, а не просто стоял в миске</h2>
  <p class="section-sub">Даже идеальный корм можно испортить неправильным кормлением. Несколько простых правил.</p>

  <table class="tips-grid-t">
    <tr><td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h14l-2 16H7z"/><path d="M9 4V2h6v2"/></svg></div>
      <div><h4>Норма — по упаковке, по весу</h4><p>Берите норму для целевого веса и делите на <strong>2 кормления</strong>. Дальше корректируйте по кондиции: рёбра прощупываются, талия видна сверху.</p></div>
    </div></td>
    <td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2s7 8 7 13a7 7 0 01-14 0c0-5 7-13 7-13z"/></svg></div>
      <div><h4>Вода — всегда и много</h4><p>Сухой корм почти без влаги, поэтому воды нужно в <strong>2–3 раза больше</strong> объёма корма. Свежая миска, меняйте 2 раза в день.</p></div>
    </div></td></tr>
    <tr><td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 5.6L20 8l-4.2 4 1 5.8L12 15l-4.8 2.8 1-5.8L4 8l5.6-0.4z"/></svg></div>
      <div><h4>Лакомства — максимум 10%</h4><p>Угощения и добавки — не больше <strong>10% дневных калорий</strong>, иначе рацион разбалансируется. На этот объём уменьшайте порцию корма.</p></div>
    </div></td>
    <td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M4 7l1 13h14l1-13M9 7V4h6v3"/></svg></div>
      <div><h4>Не мешайте с натуралкой в одной миске</h4><p>Сухой корм и сырое/варёное перевариваются с разной скоростью. Хотите сочетать — давайте в <strong>разные кормления</strong>. Храните корм герметично, в сухом тёмном месте.</p></div>
    </div></td></tr>
    <tr><td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></div>
      <div><h4>Режим — по часам</h4><p>Кормите в <strong>одно и то же время</strong>, 2 раза в день. Миску не оставляйте больше чем на 15–20 минут: так проще следить за аппетитом и не перекармливать.</p></div>
    </div></td>
    <td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h18M3 6h18M3 18h18"/><path d="M18 4l2 2-2 2"/></svg></div>
      <div><h4>Не кормите со стола</h4><p>Человеческая еда сбивает рацион и приучает попрошайничать. Солёное, копчёное, сладкое и кости варёные — <strong>под запретом</strong>, даже «по чуть-чуть».</p></div>
    </div></td></tr>
    <tr><td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h7l-1 8 10-12h-7z"/></svg></div>
      <div><h4>Покой до и после еды</h4><p>Не нагружайте собаку <strong>час до и после</strong> кормления. Активные игры на полный желудок у крупных пород повышают риск заворота желудка.</p></div>
    </div></td>
    <td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 14l3-3 3 3 4-5"/></svg></div>
      <div><h4>Взвешивайте раз в 2 недели</h4><p>Корректируйте порцию по факту: рёбра прощупываются, талия видна сверху. <strong>±10%</strong> к норме с упаковки — это нормально, собаки разные.</p></div>
    </div></td></tr>
  </table>

  {_dry_page_foot(8, total_pages, doc_id)}
</section>

<!-- PAGE 9 — TRANSITION -->
<section class="page">
  {_dry_page_head(f"<strong>Переход на новый корм</strong> · 7+ дней")}

  <div class="eyebrow">Не меняйте корм за один день</div>
  <h2 class="section-title" style="margin-top: 4mm;">Как мягко перевести {name_a} на новый корм</h2>
  <p class="section-sub">Резкая смена → диарея и зуд на ровном месте. Идите по схеме — это всего одна неделя.</p>

  <div class="transition-strip">
    <table class="transition-track-t">
      <tr><td><div class="tr-step-bar">
        <div class="days"><span class="num">1–2</span><span class="lbl">дни</span></div>
        <table class="tr-mix"><tr><td class="old" style="width:75%;">75%</td><td class="new" style="width:25%;">25%</td></tr></table>
        <div style="font-size:8.5pt;color:var(--ink-soft);">Привыкание. Стул может стать мягче.</div>
      </div></td>
      <td><div class="tr-step-bar">
        <div class="days"><span class="num">3–4</span><span class="lbl">дни</span></div>
        <table class="tr-mix"><tr><td class="old" style="width:50%;">50%</td><td class="new" style="width:50%;">50%</td></tr></table>
        <div style="font-size:8.5pt;color:var(--ink-soft);">Половина на половину. Следите за стулом.</div>
      </div></td>
      <td><div class="tr-step-bar">
        <div class="days"><span class="num">5–6</span><span class="lbl">дни</span></div>
        <table class="tr-mix"><tr><td class="old" style="width:25%;">25%</td><td class="new" style="width:75%;">75%</td></tr></table>
        <div style="font-size:8.5pt;color:var(--ink-soft);">Новый корм — основа.</div>
      </div></td>
      <td><div class="tr-step-bar">
        <div class="days"><span class="num">7+</span><span class="lbl">дни</span></div>
        <table class="tr-mix"><tr><td class="new" style="width:100%;">100%</td></tr></table>
        <div style="font-size:8.5pt;color:var(--ink-soft);">Полный переход.</div>
      </div></td>
      </tr>
    </table>
    <div class="tr-legend">
      <span><span class="sw old"></span> Старый корм</span>
      <span><span class="sw new"></span> Новый корм</span>
    </div>
  </div>

  <table class="tips-grid-t">
    <tr><td><div class="tip warn">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg></div>
      <div><h4>Если диарея — вернитесь на шаг назад</h4><p>Уменьшите долю нового корма и задержитесь на 2–3 дня. Если стул не нормализовался <strong>за 48 часов</strong> — пишите в Telegram-бот.</p></div>
    </div></td>
    <td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></div>
      <div><h4>Как понять, что порция правильная</h4><p>Рёбра <strong>прощупываются, но не торчат</strong>. Талия видна сверху. Взвешивайте {name_a} раз в 2 недели.</p></div>
    </div></td></tr>
    <tr><td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></div>
      <div><h4>Кормите по графику</h4><p>Два раза в день в одно и то же время. Между кормлениями — только вода.</p></div>
    </div></td>
    <td><div class="tip">
      <div class="ic"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h14l-2 16H7z"/><path d="M9 4V2h6v2"/></svg></div>
      <div><h4>Свежая вода — всегда</h4><p>На каждые 100 г корма — <strong>200–300 мл воды</strong>. Меняйте воду 2 раза в день.</p></div>
    </div></td></tr>
  </table>

  {_dry_page_foot(9, total_pages, doc_id)}
</section>

<!-- PAGE 10 — DISCLAIMER -->
<section class="page last-page">
  {_dry_page_head("<strong>Дисклеймер и контакты</strong>")}

  <div class="eyebrow">Важно знать</div>
  <h2 class="section-title" style="margin-top: 4mm;">Несколько слов перед тем,<br/>как закроете PDF</h2>

  <div class="disclaimer-card">
    <div class="quote">«</div>
    <p>Подбор основан на анализе составов по открытым данным производителей. <strong>Мы не связаны ни с одним брендом</strong> и не получаем вознаграждения за рекомендации. При наличии хронических заболеваний обязательно согласуйте выбор корма с лечащим ветеринаром.</p>
  </div>

  <h3 style="font-size: 12pt; margin-bottom: 4mm;">Связь с нами</h3>
  <table class="contact-grid-t">
    <tr>
    <td><div class="contact-card">
      <div class="ico"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l18-7-3 16-7-3-3 4v-5l10-9-12 7-3-2z"/></svg></div>
      <div>
        <div class="label">Telegram-бот</div>
        <div class="val">@doggifood_bot</div>
      </div>
    </div></td>
    <td><div class="contact-card">
      <div class="ico"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18"/></svg></div>
      <div>
        <div class="label">Сайт</div>
        <div class="val">kus.dogfine.ru</div>
      </div>
    </div></td>
    </tr>
  </table>

  <div class="support-strip">
    <div>
      <h3>7 дней бесплатной поддержки</h3>
      <p>Корм не подошёл? {name} отказался? Напишите в Telegram-бот — ответим за 15 минут в рабочее время.</p>
    </div>
  </div>

  <div class="bye">
    Спасибо, что доверили нам выбор корма для {name_g} <span class="heart">♥</span><br/>
    © 2026 Кусь · Doggi · kus.dogfine.ru
  </div>

  {_dry_page_foot(10, total_pages, doc_id)}
</section>

</body>
</html>"""
    return _renumber_pages(html)


def generate_dry_food_pdf(result: DryFoodResult, output_path: str = None) -> str:
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(__file__), "output",
            f"dry_food_{result.dog.name}_{date.today().isoformat()}.pdf"
        )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    html = generate_dry_food_html(result)

    try:
        from weasyprint import HTML as WeasyprintHTML
        base = os.path.dirname(__file__)
        WeasyprintHTML(string=html, base_url=base).write_pdf(output_path)
    except (ImportError, OSError):
        html_path = output_path.replace(".pdf", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        return html_path
    return output_path


# ---------------------------------------------------------------------------
# Тест
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    selector = DryFoodSelector()

    dog = DogProfileDry(
        name="Барон",
        breed="Лабрадор-ретривер",
        age_months=36,
        sex="male",
        neutered=True,
        weight_kg=32,
        condition="chubby",
        activity="moderate",
        diagnoses=[],
        stool="good",
        stop_products=["курица"],
    )

    result = selector.select(dog)

    print(f"=== Подбор корма для {dog.name} ({dog.breed}, {dog.weight_kg}кг) ===")
    print(f"Стоп-продукты: {dog.stop_products}")
    print()

    for cat_name, foods in [("БЮДЖЕТ", result.budget), ("СРЕДНИЙ", result.mid), ("ПРЕМИУМ", result.premium)]:
        print(f"--- {cat_name} ---")
        for i, rec in enumerate(foods, 1):
            f = rec.food
            print(f"  {i}. {f['brand']} — {f['name']}")
            print(f"     Мясо: ~{f['meat_estimate_pct']}% | Б:{f['protein_pct']}% Ж:{f['fat_pct']}% | ~{f['price_per_kg']} руб/кг")
            print(f"     + {', '.join(rec.reasons_for[:3])}")
            if rec.reasons_against:
                print(f"     - {', '.join(rec.reasons_against[:2])}")
        print()

    path = generate_dry_food_pdf(result)
    print(f"PDF/HTML: {path}")
