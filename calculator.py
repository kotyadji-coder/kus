"""
Калькулятор натурального рациона для собак.
Основан на нормах NRC 2006, FEDIAF, AAFCO.
"""

import json
import math
import os
from dataclasses import dataclass, field
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load_json(filename: str):
    with open(os.path.join(DATA_DIR, filename), "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Стоп-продукты — единый источник правды
# ---------------------------------------------------------------------------
# Пользователь пишет "курица" -> в названии продукта ищем подстроку "кур".
# Этой же логикой фильтруются и подбор меню (_select_products), и тексты в PDF
# (примеры костей, советы по замене мяса). Не дублировать матчинг где-либо ещё.
STOP_SYNONYMS = {
    # Корень = ОБЩИЙ префикс всех форм И названий в products.json, иначе стоп
    # протекает: «говяж» не подстрока в «Говядина», «индей» — не в «Индюшачьи».
    "курица": "кур", "курятина": "кур", "куриный": "кур",
    "говядина": "говя", "говяжий": "говя",
    "свинина": "свин", "свиной": "свин",
    "баранина": "баран", "бараний": "баран",
    "утка": "ут", "утиный": "ут",
    "кролик": "кролик", "крольчатина": "кролик",
    "индейка": "инд", "индюшка": "инд", "индюшачий": "инд",
    "рыба": "рыб", "лосось": "лосос", "минтай": "минтай",
    "молоко": "молок", "творог": "творог", "кефир": "кефир",
    "яйцо": "яйц",
}


def stop_roots(stop_products: list[str]) -> set[str]:
    """Корни стоп-продуктов для подстрочного матча по названию продукта."""
    roots = set()
    for s in stop_products or []:
        s_stripped = s.strip().lower()
        if not s_stripped:
            continue
        if s_stripped in STOP_SYNONYMS:
            roots.add(STOP_SYNONYMS[s_stripped])
        else:
            roots.add(s_stripped[:4] if len(s_stripped) >= 4 else s_stripped)
    return roots


def is_stopped(name: str, roots: set[str]) -> bool:
    """Содержит ли название продукта/ингредиента стоп-корень."""
    n = name.lower()
    return any(r in n for r in roots)


# ---------------------------------------------------------------------------
# Входные данные (анкета)
# ---------------------------------------------------------------------------

@dataclass
class DogProfile:
    name: str                    # Кличка
    breed: str                   # Порода (из breeds.json)
    age_months: int              # Возраст в месяцах
    sex: str                     # "male" / "female"
    neutered: bool               # Кастрирован/стерилизована
    weight_kg: float             # Текущий вес
    current_food: str            # "dry" / "porridge" / "natural" / "table" / "mixed" / текст
    condition: str               # "thin" / "athletic" / "chubby" / "obese"
    activity: str                # "lazy" / "moderate" / "high" / "puppy"
    diagnoses: list[str] = field(default_factory=list)       # ["pancreatitis", "gastritis", ...]
    stool: str = "good"          # "good" / "loose" / "constipation" / "high_volume"
    diet_type: str = "barf"      # "barf" / "cooked"
    budget: str = "market"       # "supermarket" / "market" / "unlimited"
    stop_products: list[str] = field(default_factory=list)   # ["курица", "говядина", ...]
    season: str = "default"      # "winter" / "summer" / "default" (auto)
    pregnant: bool = False       # беременность
    lactating: bool = False      # лактация


# ---------------------------------------------------------------------------
# Результат расчёта
# ---------------------------------------------------------------------------

@dataclass
class MealPortion:
    product_id: str
    product_name: str
    grams: float
    group: str


@dataclass
class DayMenu:
    day_name: str
    morning: list[MealPortion]
    evening: list[MealPortion]
    midday: list[MealPortion] = field(default_factory=list)  # 3-е кормление (гиганты/гастрит)


@dataclass
class DietResult:
    dog: DogProfile
    ideal_weight_kg: float
    rer_kcal: float
    mer_kcal: float
    daily_grams: float
    meals_per_day: int
    distribution: dict          # группа -> граммы
    ca_total_mg: float
    p_total_mg: float
    ca_p_ratio: float
    weekly_menu: list[DayMenu]
    supplements: list[dict]
    transition_plan: list[dict]
    warnings: list[str]
    cost_per_day: float = 0.0       # руб/день
    cost_per_month: float = 0.0     # руб/месяц
    cooking_tips: list[str] = field(default_factory=list)  # советы по готовке (для cooked)
    meal_prep: dict = field(default_factory=dict)  # подсказка по заморозке/контейнерам
    puppy_next_recalc: str = ""     # когда пересчитать (для щенков)
    ca_p_ratio_effective: float = 0.0  # Ca:P ПОСЛЕ добавки кальция (реальный в миске)


# ---------------------------------------------------------------------------
# Основной калькулятор
# ---------------------------------------------------------------------------

class DietCalculator:

    def __init__(self):
        self.breeds = load_json("breeds.json")
        self.products_db = load_json("products.json")
        self._breed_map = {b["name"]: b for b in self.breeds}
        # Плоский список всех продуктов
        self._all_products = {}
        for group_products in self.products_db.values():
            for p in group_products:
                self._all_products[p["id"]] = p

    @staticmethod
    def _size_from_weight(w: float) -> str:
        if w < 5: return "mini"
        if w < 10: return "small"
        if w < 25: return "medium"
        if w < 45: return "large"
        return "giant"

    def _synthetic_breed_info(self, w: float) -> dict:
        """Для породы не из breeds.json: размер по весу, чтобы size-зависимая логика
        (суставы/заворот у гигантов, частота кормлений) не отваливалась. Помечен
        _synthetic — идеальный вес считаем по текущему, породный стандарт не выдумываем."""
        return {"size": self._size_from_weight(w), "weight_min": w, "weight_max": w, "_synthetic": True}

    def _get_breed_info(self, dog: DogProfile) -> dict:
        """Породный профиль из breeds.json, либо синтетический (размер по весу) для
        неизвестной породы — чтобы size-зависимая логика работала ВЕЗДЕ одинаково."""
        bi = self._breed_map.get(dog.breed)
        return bi if bi is not None else self._synthetic_breed_info(dog.weight_kg)

    def calculate(self, dog: DogProfile) -> DietResult:
        breed_info = self._get_breed_info(dog)
        ideal_weight = self._calc_ideal_weight(dog, breed_info)
        rer = self._calc_rer(ideal_weight)
        mer_coeff = self._calc_mer_coefficient(dog, breed_info)
        mer = rer * mer_coeff
        daily_grams = self._calc_daily_grams(dog, ideal_weight)
        meals_per_day = self._calc_meals_per_day(dog, breed_info)
        distribution = self._calc_distribution(dog, daily_grams)
        product_plan = self._select_products(dog, distribution)
        # Согласование: если стоп-лист/аллергия выкосили ВСЮ группу (напр. субпродукты
        # — в базе только говяжьи/куриные), её граммы нельзя терять. Переносим в мясо
        # и обнуляем в распределении, чтобы сводка-диаграмма и меню сходились.
        distribution, wiped_groups = self._reconcile_wiped_groups(distribution, product_plan)
        ca_total, p_total = self._calc_ca_p(product_plan)
        ca_p_ratio = ca_total / p_total if p_total > 0 else 0
        distribution, product_plan, ca_total, p_total, ca_p_ratio = self._balance_ca_p(
            dog, distribution, product_plan, ca_total, p_total, ca_p_ratio, daily_grams
        )
        supplements = self._calc_supplements(dog, ideal_weight, ca_p_ratio, ca_total, p_total)
        # Эффективный Ca:P — то, что реально в миске ПОСЛЕ добавки кальция (еда + цитрат).
        ca_added = sum(s.get("ca_elem_mg", 0) for s in supplements)
        ca_p_ratio_effective = (ca_total + ca_added) / p_total if p_total > 0 else ca_p_ratio
        transition = self._calc_transition(dog)
        warnings = self._generate_warnings(dog, breed_info, ca_p_ratio)
        weekly_menu = self._generate_weekly_menu(dog, product_plan, meals_per_day, distribution)
        cost_day = self._calc_cost(product_plan)
        cooking_tips = self._calc_cooking_tips(dog, product_plan) if dog.diet_type == "cooked" else []
        meal_prep = self._calc_meal_prep(dog, daily_grams, meals_per_day)
        puppy_note = self._calc_puppy_recalc(dog, breed_info)

        # Восполнение питательного пробела от выпавших стоп-листом групп.
        # Субпродукты (печень/сердце) — ключевой источник вит. A, B12, меди, таурина;
        # если их вырезал стоп-лист, предупреждаем и рекомендуем замену/добавку.
        if "organs" in wiped_groups:
            warnings.append(
                "Субпродукты (печень, сердце) исключены: в базе они только говяжьи и "
                "куриные, а оба попали в стоп-лист. Их доля перенесена в мясо, но печень — "
                "главный источник витамина A, B12, меди и таурина. Добавьте субпродукты "
                "ДРУГОГО животного (индейка, кролик, баранина — не из стоп-листа) 1–2 раза "
                "в неделю ИЛИ витаминный комплекс с A и B12."
            )
            supplements.append({
                "name": "Замена субпродуктов (вит. A + B12)",
                "dosage": "субпродукты др. животного 1–2 раза/нед или комплекс по инструкции",
                "frequency": "1–2 раза в неделю",
                "notes": "Печень/сердце убраны стоп-листом. Источник витамина A, B12, меди и "
                         "таурина: печень индейки/кролика/баранины (не из стоп-листа) либо "
                         "аптечный витаминный комплекс с A и группой B.",
            })
        elif wiped_groups:
            labels = {"vegetables": "овощи", "dairy": "кисломолочка", "muscle_meat": "мясо",
                      "raw_meaty_bones": "кости", "eggs": "яйца"}
            names = ", ".join(labels.get(g, g) for g in wiped_groups)
            warnings.append(
                f"Группа «{names}» исключена стоп-листом целиком — её доля перенесена в мясо. "
                f"Подберите альтернативный источник вне стоп-листа, чтобы рацион оставался разнообразным."
            )

        # Беременность/лактация — дополнительные предупреждения
        if dog.pregnant:
            warnings.append("Беременность: порции увеличены на 25%. В последние 2 недели перед родами аппетит может снизиться — кормите чаще и меньшими порциями.")
        if dog.lactating:
            warnings.append("Лактация: потребность в калориях удвоена. Обеспечьте постоянный доступ к воде. При большом помёте может потребоваться ещё больше еды.")
        if dog.condition in ("chubby", "obese") and dog.weight_kg > 0 and ideal_weight >= dog.weight_kg - 0.01:
            warnings.append("Вес уже на уровне породной нормы или ниже, хотя кондиция отмечена как избыточная — перепроверьте оценку (прощупайте рёбра, оцените талию сверху). Цель оставлена на текущем весе, без снижения.")

        return DietResult(
            dog=dog,
            ideal_weight_kg=round(ideal_weight, 1),
            rer_kcal=round(rer, 0),
            mer_kcal=round(mer, 0),
            daily_grams=round(daily_grams / 5) * 5,
            meals_per_day=meals_per_day,
            distribution=distribution,
            ca_total_mg=round(ca_total, 0),
            p_total_mg=round(p_total, 0),
            ca_p_ratio=round(ca_p_ratio, 2),
            ca_p_ratio_effective=round(ca_p_ratio_effective, 2),
            weekly_menu=weekly_menu,
            supplements=supplements,
            transition_plan=transition,
            warnings=warnings,
            cost_per_day=round(cost_day, 0),
            cost_per_month=round(cost_day * 30, 0),
            cooking_tips=cooking_tips,
            meal_prep=meal_prep,
            puppy_next_recalc=puppy_note,
        )

    # --- Идеальный вес ---

    def _calc_ideal_weight(self, dog: DogProfile, breed_info: Optional[dict]) -> float:
        condition_adj = {
            "thin": 1.10,       # нужно набрать ~10%
            "athletic": 1.0,    # вес ок
            "chubby": 0.88,     # скинуть ~12%
            "obese": 0.80,      # скинуть ~20%
        }
        adj = condition_adj.get(dog.condition, 1.0)

        # У метиса/беспородной нет породного эталона веса — нельзя выдавать
        # середину широкого бакета за «идеал» (это давало фантомный недовес).
        # Ориентир только на текущий вес с поправкой на кондицию тела.
        is_mixed = "метис" in (dog.breed or "").lower()
        # Метис/беспородная/неизвестная (синтетический breed_info) — без породного
        # эталона веса, ориентир только на текущий вес с поправкой на кондицию.
        if is_mixed or not breed_info or breed_info.get("_synthetic"):
            return dog.weight_kg * adj

        breed_avg = (breed_info["weight_min"] + breed_info["weight_max"]) / 2

        if dog.condition == "athletic":
            return dog.weight_kg
        elif dog.condition == "thin":
            return dog.weight_kg * adj
        else:
            # Для полных ориентируемся на стандарт породы
            target = breed_avg * 1.0 if dog.condition == "chubby" else breed_avg * 0.95
            # Но не меньше чем текущий * коэффициент
            ideal = min(dog.weight_kg * adj, target) if target < dog.weight_kg else target
            # Перевес → цель НИКОГДА не выше текущего: обжоре не назначаем набор веса.
            # Бывает при конфликте: мелкая собака на нижней границе породы (вес=мин),
            # но помеченная chubby/obese — тогда цель = текущий (поддержание).
            return min(ideal, dog.weight_kg)

    # --- RER ---

    def _calc_rer(self, weight_kg: float) -> float:
        """Resting Energy Requirement (kcal/day)"""
        if weight_kg <= 0:
            return 0
        return 70 * (weight_kg ** 0.75)

    # --- MER коэффициент ---

    def _calc_mer_coefficient(self, dog: DogProfile, breed_info: Optional[dict]) -> float:
        # Базовый коэффициент по активности и кастрации
        if dog.age_months < 4:
            return 3.0
        elif dog.age_months < 6:
            return 2.5
        elif dog.age_months < 12:
            return 2.0
        elif dog.age_months < 18 and breed_info and breed_info.get("size") in ("large", "giant"):
            return 1.8

        # Взрослая собака
        base = {
            ("lazy", True): 1.2,
            ("lazy", False): 1.4,
            ("moderate", True): 1.4,
            ("moderate", False): 1.6,
            ("high", True): 1.6,
            ("high", False): 1.8,
            ("puppy", True): 2.0,
            ("puppy", False): 2.0,
        }
        coeff = base.get((dog.activity, dog.neutered), 1.4)

        # Пожилая собака
        senior_age = 8
        if breed_info:
            senior_age = breed_info.get("senior_years", 8)
        if dog.age_months >= senior_age * 12:
            coeff *= 0.85

        # Корректировка по кондиции
        if dog.condition in ("chubby", "obese"):
            coeff *= 0.8
        elif dog.condition == "thin":
            coeff *= 1.2

        # Беременность / лактация
        if dog.pregnant:
            coeff *= 1.25  # +25% в последний триместр
        elif dog.lactating:
            coeff *= 2.0   # до x2 при лактации (зависит от количества щенков)

        # Сезонная корректировка
        season = dog.season
        if season == "default":
            from datetime import date
            month = date.today().month
            season = "winter" if month in (11, 12, 1, 2, 3) else "summer" if month in (6, 7, 8) else "default"
        if season == "winter":
            coeff *= 1.1   # +10% зимой
        elif season == "summer":
            coeff *= 0.95  # -5% летом (аппетит падает)

        return coeff

    # --- Суточный объём в граммах ---

    def _calc_daily_grams(self, dog: DogProfile, ideal_weight: float) -> float:
        # Процент от массы тела
        pct_map = {
            "lazy": 0.022,
            "moderate": 0.027,
            "high": 0.035,
            "puppy": 0.05,
        }
        base_pct = pct_map.get(dog.activity, 0.027)

        # Щенки
        if dog.age_months < 4:
            base_pct = 0.07
        elif dog.age_months < 6:
            base_pct = 0.05
        elif dog.age_months < 12:
            base_pct = 0.035

        # Кондиция
        if dog.condition in ("chubby", "obese"):
            base_pct = 0.02  # от целевого веса
            return ideal_weight * 1000 * base_pct
        elif dog.condition == "thin":
            base_pct += 0.008

        # Кастрация немного снижает
        if dog.neutered and dog.age_months >= 12:
            base_pct *= 0.92

        return dog.weight_kg * 1000 * base_pct

    # --- Количество кормлений ---

    def _calc_meals_per_day(self, dog: DogProfile, breed_info: Optional[dict] = None) -> int:
        if dog.age_months < 4:
            return 4
        elif dog.age_months < 6:
            return 3
        elif dog.age_months < 12:
            return 2
        else:
            if "gastritis" in self._normalize_diagnoses(dog.diagnoses):
                return 3
            # Крупные/гигантские породы — глубокая грудь, повышенный риск заворота
            # желудка (GDV). Дробим на 3 приёма меньшего объёма вместо 2 больших.
            if breed_info and breed_info.get("size") in ("large", "giant"):
                return 3
            return 2

    # --- Распределение по группам ---

    def _calc_distribution(self, dog: DogProfile, daily_grams: float) -> dict:
        if dog.diet_type == "barf":
            dist = {
                "muscle_meat": 0.45,       # основа рациона
                "raw_meaty_bones": 0.12,   # источник кальция
                "organs": 0.12,            # витамины A, B12, железо
                "vegetables": 0.15,        # клетчатка
                "dairy": 0.10,             # кисломолочка
                "eggs": 0.04,              # полноценный белок
                "fish": 0.0,               # рыба 2 раза/нед заменяет мясо
                "oils_supplements": 0.02,  # масла
            }  # = 1.00
        else:  # cooked
            dist = {
                "muscle_meat": 0.55,       # больше мяса (нет костей)
                "raw_meaty_bones": 0.0,    # нет костей при варке!
                "organs": 0.12,            # субпродукты
                "vegetables": 0.15,        # овощи
                "dairy": 0.10,             # кисломолочка
                "eggs": 0.04,              # яйца
                "fish": 0.0,               # рыбные дни
                "oils_supplements": 0.04,  # масла + костная мука
            }  # = 1.00

        # Корректировка при диагнозах. ВАЖНО: диагнозы хранятся по-русски
        # («панкреатит»), поэтому сверяемся с нормализованными англ-ключами,
        # а не с сырым dog.diagnoses (иначе условие молча не срабатывает).
        diag = self._normalize_diagnoses(dog.diagnoses)
        if "pancreatitis" in diag:
            # Меньше жиров, больше нежирного мяса
            dist["muscle_meat"] = 0.50
            dist["organs"] = 0.08
            dist["dairy"] = 0.05

        if "gastritis" in diag:
            # Без костей, мягкая пища
            dist["raw_meaty_bones"] = 0.0
            dist["muscle_meat"] = 0.50
            dist["vegetables"] = 0.18

        result = {k: self._round_g(v * daily_grams) for k, v in dist.items()}
        # Компенсируем потери от округления — корректируем мясо
        rounded_total = sum(result.values())
        target = self._round_g(daily_grams)
        diff = target - rounded_total
        if diff != 0 and result.get("muscle_meat", 0) > 0:
            result["muscle_meat"] += diff
        return result

    # --- Подбор конкретных продуктов ---

    def _select_products(self, dog: DogProfile, distribution: dict) -> dict[str, list]:
        """Для каждой группы подбирает конкретные продукты с граммовками."""
        result = {}
        roots = stop_roots(dog.stop_products)

        for group, grams in distribution.items():
            if grams <= 0:
                continue

            available = self.products_db.get(group, [])
            # Фильтруем по бюджету
            budget_levels = {
                "supermarket": ["supermarket"],
                "market": ["supermarket", "market"],
                "unlimited": ["supermarket", "market", "unlimited"],
            }
            allowed_avail = budget_levels.get(dog.budget, ["supermarket", "market", "unlimited"])
            candidates = [
                p for p in available
                if p.get("availability", "supermarket") in allowed_avail
                and not p.get("rare", False)  # редкое/труднодоступное (конина, оленина) не предлагаем
            ]

            # Фильтруем стоп-продукты (матчинг — модульный stop_roots/is_stopped)
            filtered = [p for p in candidates if not is_stopped(p["name"], roots)]
            if filtered:
                candidates = filtered
            elif roots:
                # Все продукты в группе содержат стоп-продукт — пропускаем группу
                continue

            # Фильтруем по аллергенности (если собака аллергик — убираем common_allergen)
            if dog.diagnoses and any("аллерг" in d.lower() for d in dog.diagnoses):
                non_allergenic = [p for p in candidates if not p.get("common_allergen", False)]
                if non_allergenic:
                    candidates = non_allergenic

            # Фильтруем по противопоказаниям
            diag_keys = self._normalize_diagnoses(dog.diagnoses)
            candidates = [
                p for p in candidates
                if not any(c in diag_keys for c in p.get("contraindications", []))
            ]

            if not candidates:
                # Если ничего не осталось — берём всё из группы (лучше что-то, чем ничего)
                candidates = available

            # Распределяем граммы между продуктами группы
            selected = self._distribute_within_group(candidates, grams, group)
            result[group] = selected

        return result

    def _distribute_within_group(self, candidates: list, total_grams: float, group: str) -> list[dict]:
        """Собирает все доступные продукты для группы (для ротации по дням)."""
        if not candidates:
            return []

        # Берём все доступные продукты — ротация будет в недельном меню
        if group == "muscle_meat":
            n = min(4, len(candidates))
        elif group == "organs":
            n = min(3, len(candidates))
        elif group == "raw_meaty_bones":
            n = min(2, len(candidates))
        elif group == "vegetables":
            n = min(4, len(candidates))
        elif group == "dairy":
            n = min(2, len(candidates))
        else:
            n = min(2, len(candidates))

        selected = candidates[:n]
        per_item = total_grams / n

        return [
            {
                "product_id": p["id"],
                "product_name": p["name"],
                "grams": round(per_item, 0),
                "group": group,
                "ca_mg": p.get("ca_mg", 0),
                "p_mg": p.get("p_mg", 0),
            }
            for p in selected
        ]

    # --- Баланс Ca:P ---

    def _calc_ca_p(self, product_plan: dict) -> tuple[float, float]:
        total_ca = 0.0
        total_p = 0.0
        for group, items in product_plan.items():
            for item in items:
                g = item["grams"]
                total_ca += item.get("ca_mg", 0) * g / 100
                total_p += item.get("p_mg", 0) * g / 100
        return total_ca, total_p

    def _balance_ca_p(self, dog, distribution, product_plan, ca, p, ratio, daily_grams):
        """Если Ca:P вне нормы (1.1-1.6), корректируем."""
        if 1.1 <= ratio <= 1.6:
            return distribution, product_plan, ca, p, ratio

        # Ca слишком мало — нужно добавить кости (BARF) или костную муку (варка)
        # Это будет учтено в supplements
        # Помечаем в warnings
        return distribution, product_plan, ca, p, ratio

    # --- Витамины и добавки ---

    @staticmethod
    def _round_practical(value: float, step: float = 0.5) -> float:
        """Округляет до практичных значений (до 0.5, 1, 5, 10)."""
        if value <= 0:
            return 0
        if value < 1:
            return round(value * 4) / 4  # до 0.25
        if value < 5:
            return round(value * 2) / 2  # до 0.5
        if value < 20:
            return round(value)  # до 1
        return round(value / 5) * 5  # до 5

    @staticmethod
    def _fmt_num(value: float) -> str:
        """Печатает число без лишнего '.0' и с дробями для половин/четвертей."""
        fractions = {0.25: "¼", 0.5: "½", 0.75: "¾"}
        whole = int(value)
        frac = round(value - whole, 2)
        frac_str = fractions.get(frac)
        if whole == 0 and frac_str:
            return frac_str
        if frac_str:
            return f"{whole}{frac_str}"
        if value == whole:
            return str(whole)
        return f"{value:g}"

    def _calc_supplements(self, dog: DogProfile, ideal_weight: float, ca_p_ratio: float,
                          ca_total: float = 0.0, p_total: float = 0.0) -> list[dict]:
        supps = []

        # Рыбий жир — всегда
        # 1 ч.л. ≈ 5 мл, 1 капсула ≈ 1 мл (1000 мг). Доза ~0.2 мл/кг.
        fish_oil_ml = ideal_weight / 5
        caps_per_day = fish_oil_ml  # 1 капсула ≈ 1 мл
        if caps_per_day >= 2:
            # Крупная собака — удобнее мерить чайными ложками
            fish_oil_tsp = self._round_practical(fish_oil_ml / 5)
            if fish_oil_tsp >= 1:
                dosage_text = f"{self._fmt_num(fish_oil_tsp)} ч.л. в день"
                measure_hint = f"≈ {round(fish_oil_ml)} мл или {round(caps_per_day)} капсул по 1000 мг"
            else:
                dosage_text = f"{round(caps_per_day)} капсулы в день"
                measure_hint = f"≈ {round(fish_oil_ml)} мл, с едой"
            frequency = "Ежедневно"
        elif caps_per_day >= 0.85:
            dosage_text = "1 капсула в день"
            measure_hint = "1000 мг, с едой"
            frequency = "Ежедневно"
        else:
            # Меньше капсулы в день — даём долю или удобную альтернативу через день
            dosage_text = "½ капсулы в день"
            measure_hint = "или 1 капсула (1000 мг) через день — так не нужно делить"
            frequency = "Ежедневно"
        supps.append({
            "name": "Рыбий жир (Омега-3)",
            "dosage": dosage_text,
            "frequency": frequency,
            "notes": f"С едой. Лососёвое масло или капсулы ({measure_hint}).",
        })

        # Кальций — при варке или плохом Ca:P.
        if dog.diet_type == "cooked" or ca_p_ratio < 1.1:
            # Дозируем кальций РОВНО под дефицит до целевого Ca:P, а не плоско по
            # весу: плоская доза (50 мг/кг, пол 200) при малом объёме еды у мелких
            # перебивала баланс — Ca:P улетал до 2.2-2.8 (выше потолка 2.0). Под
            # дефицит каждая собака приходит к ~1.4 независимо от размера.
            TARGET_CA_P = 1.4
            ca_deficit_mg = TARGET_CA_P * p_total - ca_total
            ca_mg_day = max(0, int(round(ca_deficit_mg / 25.0)) * 25)  # шаг 25 мг
            if ca_mg_day > 0:
                # Хинт в таблетках по 200 мг кальция (элемент) — типичный цитрат.
                TAB_CA_MG = 200
                tabs = max(0.25, round(ca_mg_day / TAB_CA_MG * 4) / 4)  # до ¼ табл.
                citrate_dose = f"{self._fmt_num(tabs)} табл. в день (по {TAB_CA_MG} мг кальция в таблетке)"
                if dog.diet_type == "cooked":
                    why = ("Домашний варёный рацион беден кальцием — костей в нём нет, "
                           "поэтому добавка обязательна. Сырые кости в варёный рацион не вводят. ")
                else:
                    why = ("Костей в рационе недостаточно для баланса Ca:P — добавьте "
                           "кальций по этой дозе ИЛИ увеличьте долю сырых мясных костей. ")
                supps.append({
                    "name": "Кальция цитрат",
                    "dosage": f"{ca_mg_day} мг кальция в день",
                    "ca_elem_mg": ca_mg_day,  # элементарный кальций — для эффективного Ca:P
                    "frequency": "Ежедневно, разделить на кормления",
                    "notes": (
                        f"{why}"
                        f"Аптека: кальция цитрат — {citrate_dose}, усваивается на 40-50%, "
                        f"можно с едой и без. Точнее всего дозируется молотая яичная скорлупа "
                        f"(½ ч.л. ≈ 1000 мг кальция — берите долю под норму). "
                        f"Ветеринарные добавки: Canina Calcium Citrate, 8in1 Excel Calcium, "
                        f"Wolmar Pro Bio Calcium — содержат кальций + витамин D3 для усвоения."
                    ),
                })

        # Ламинария
        # Дозировка: ~0.25 ч.л. на 10 кг, через день
        kelp_raw = ideal_weight / 10 * 0.25
        if kelp_raw < 0.5:
            kelp_text = "¼ ч.л."
        elif kelp_raw < 0.75:
            kelp_text = "½ ч.л."
        elif kelp_raw < 1.25:
            kelp_text = "1 ч.л."
        else:
            kelp_text = f"{self._round_practical(kelp_raw)} ч.л."
        supps.append({
            "name": "Ламинария (морская капуста сушёная)",
            "dosage": f"{kelp_text} через день",
            "frequency": "Через день",
            "notes": "Сухая молотая, добавлять в миску. Источник йода и микроэлементов.",
        })

        # Витамин E — при BARF
        if dog.diet_type == "barf":
            # Округляем до ближайших 50 МЕ (капсулы обычно 100, 200, 400 МЕ)
            vit_e_raw = ideal_weight * 2
            vit_e = round(vit_e_raw / 50) * 50
            if vit_e < 50:
                vit_e = 50
            supps.append({
                "name": "Витамин E",
                "dosage": f"{vit_e} МЕ в день",
                "frequency": "Ежедневно",
                "notes": f"1 капсула «Аевит» или токоферол. Особенно важен при сыром кормлении.",
            })

        # Пробиотик — при проблемах со стулом (доза по весу)
        if dog.stool in ("loose", "high_volume"):
            if ideal_weight < 5:
                prob_dose = "½ капсулы (или ½ саше) в день"
            elif ideal_weight < 15:
                prob_dose = "1 капсула (саше) в день"
            else:
                prob_dose = "1-2 капсулы (саше) в день"
            supps.append({
                "name": "Пробиотик для собак",
                "dosage": prob_dose,
                "frequency": "Курсами — 14 дней в месяц",
                "notes": "FortiFlora, Ветом 1.1, Pro-Kolin или аптечный Линекс. "
                         "Для мелких собак уточните точную дозу по инструкции к препарату.",
            })

        # --- Определяем breed_info для дальнейших проверок ---
        breed_info = self._get_breed_info(dog)
        size = breed_info.get("size", "medium") if breed_info else "medium"
        is_large = size in ("large", "giant")
        senior_age = (breed_info.get("senior_years", 8) if breed_info else 8) * 12
        is_senior = dog.age_months >= senior_age
        is_puppy = dog.age_months < 18

        # Глюкозамин + Хондроитин — для крупных пород (взрослые), пожилых, при проблемах с суставами
        needs_joints = is_senior or (is_large and dog.age_months >= 12)
        if "суставы" in " ".join(dog.diagnoses).lower() or "артрит" in " ".join(dog.diagnoses).lower() or "дисплазия" in " ".join(dog.diagnoses).lower():
            needs_joints = True
        if breed_info and breed_info.get("obesity_prone") and dog.condition in ("chubby", "obese"):
            needs_joints = True  # Лишний вес = нагрузка на суставы

        if needs_joints:
            # Дозировки: глюкозамин ~20 мг/кг, хондроитин ~15 мг/кг
            gluc_mg = round(ideal_weight * 20 / 50) * 50  # округлить до 50
            chond_mg = round(ideal_weight * 15 / 50) * 50
            if gluc_mg < 250:
                gluc_mg = 250
            if chond_mg < 200:
                chond_mg = 200
            reason = "Поддержка суставов"
            if is_senior:
                reason = "Защита суставов в пожилом возрасте"
            elif is_large:
                reason = "Профилактика для крупной породы"
            supps.append({
                "name": "Глюкозамин + Хондроитин",
                "dosage": f"{gluc_mg} + {chond_mg} мг/день",
                "frequency": "Ежедневно, курсами по 2-3 месяца",
                "notes": f"{reason}. Canina Petvital GAG, 8in1 Excel Glucosamine или аптечный «Артра».",
            })

        # Витамин C — щенки крупных пород (профилактика HOD), пожилые
        if (is_puppy and is_large) or is_senior:
            vit_c_mg = round(ideal_weight * 10 / 50) * 50
            if vit_c_mg < 100:
                vit_c_mg = 100
            if vit_c_mg > 1000:
                vit_c_mg = 1000
            note = "Профилактика гипертрофической остеодистрофии (HOD) у щенков крупных пород." if is_puppy else "Антиоксидантная поддержка в пожилом возрасте."
            supps.append({
                "name": "Витамин C (аскорбиновая кислота)",
                "dosage": f"{vit_c_mg} мг/день",
                "frequency": "Ежедневно, с едой",
                "notes": f"{note} Аптечная аскорбинка в порошке или таблетках.",
            })

        # Кальций дополнительный — щенки крупных пород на BARF (если Ca:P < 1.2)
        if is_puppy and is_large and ca_p_ratio < 1.2 and dog.diet_type == "barf":
            supps.append({
                "name": "Кальций (цитрат или карбонат)",
                "dosage": f"{round(ideal_weight * 50 / 100) * 100} мг/день",
                "frequency": "Ежедневно, разделить на кормления",
                "notes": "Щенку крупной породы критично не допустить дефицит кальция. Кальция цитрат усваивается лучше.",
            })

        # Цинк — крупные породы (часто дефицит), при проблемах с кожей/шерстью
        if is_large or "дерматит" in " ".join(dog.diagnoses).lower() or "шерсть" in " ".join(dog.diagnoses).lower():
            zn_mg = round(ideal_weight * 1)  # ~1 мг/кг
            if zn_mg < 10:
                zn_mg = 10
            supps.append({
                "name": "Цинк (хелат или пиколинат)",
                "dosage": f"{zn_mg} мг/день",
                "frequency": "Ежедневно, с едой",
                "notes": "Крупные породы склонны к дефициту цинка. Улучшает кожу и шерсть. Аптечный цинк в хелатной форме.",
            })

        return supps

    # --- Схема перевода ---

    def _calc_transition(self, dog: DogProfile) -> list[dict]:
        if dog.current_food == "natural":
            return [{"note": "Собака уже на натуралке — схема перевода не требуется. Просто скорректируйте рацион по нашим рекомендациям."}]

        if dog.current_food == "dry":
            return [
                {"days": "1-3", "title": "Разгрузка", "desc": "Уменьшите порцию сухого корма на 25%. Добавьте тёплый бульон к корму."},
                {"days": "4-7", "title": "Мягкое введение", "desc": "Утро — варёная индейка (50г на 10 кг веса) + кабачок. Вечер — сухой корм (половина обычной порции)."},
                {"days": "8-10", "title": "Расширение", "desc": "Оба кормления — натуралка. Вводите по одному новому продукту каждые 2 дня. Начните с мяса и овощей."},
                {"days": "11-14", "title": "Полный рацион", "desc": "Добавляйте субпродукты, кисломолочку, кости (если BARF). Следите за стулом."},
                {"days": "14+", "title": "Стабилизация", "desc": "Рацион по нашему PDF. Если стул стабильный 3+ дня — всё отлично."},
            ]

        if dog.current_food in ("porridge", "table", "mixed"):
            return [
                {"days": "1-3", "title": "Убираем лишнее", "desc": "Убираем каши, хлеб, макароны, солёное, жареное. Оставляем только мясо + овощи."},
                {"days": "4-7", "title": "Формируем базу", "desc": "Переходим на правильные пропорции: 60-70% мясо/субпродукты + 15% овощи + 10% кисломолочка."},
                {"days": "8-10", "title": "Полный рацион", "desc": "Рацион по нашему PDF. Добавляем масла, яйца, рыбу по расписанию."},
            ]

        return [
            {"days": "1-7", "title": "Постепенный переход", "desc": "Вводите натуральные продукты постепенно, по одному новому в 2 дня. Следите за стулом."},
        ]

    # --- Предупреждения ---

    def _generate_warnings(self, dog: DogProfile, breed_info: Optional[dict], ca_p_ratio: float) -> list[str]:
        warnings = []

        if ca_p_ratio < 1.1:
            if dog.diet_type == "cooked":
                warnings.append("Ca:P ниже нормы — это ожидаемо для варёного рациона (костей в нём нет). "
                                "Добавляйте кальций по дозировке из таблицы добавок. Сырые кости в варёный рацион не вводят.")
            else:
                warnings.append("Ca:P в самой еде ниже нормы — это типично для сырого рациона. "
                                "Добавка кальция из таблицы (или увеличенная доля сырых мясных костей) выравнивает баланс.")
        if ca_p_ratio > 1.8:
            warnings.append("Соотношение Ca:P выше нормы. Уменьшите количество костей в рационе.")

        if dog.diagnoses:
            warnings.append("У собаки есть диагнозы — рекомендуем согласовать рацион с ветеринаром.")

        if dog.age_months < 6 and breed_info and breed_info.get("size") in ("large", "giant"):
            warnings.append("Щенок крупной породы — избегайте избытка кальция. Кости осторожно, лучше костная мука в строгой дозировке.")

        if dog.age_months >= 12 and breed_info and breed_info.get("size") in ("large", "giant"):
            warnings.append("Крупная порода — повышенный риск заворота желудка. Кормите 2-3 раза в день небольшими порциями, "
                            "не давайте пить залпом и не нагружайте собаку 1-1.5 часа до и после еды. Удобна миска на подставке.")

        if breed_info and breed_info.get("obesity_prone") and dog.condition in ("chubby", "obese"):
            warnings.append(f"Порода {dog.breed} склонна к ожирению. Строго следите за порциями и не давайте лакомства сверх нормы.")

        if "gastritis" in self._normalize_diagnoses(dog.diagnoses) and dog.diet_type == "barf":
            warnings.append("При гастрите сырые кости могут раздражать ЖКТ. Рекомендуем перейти на варёный рацион и кальций из костной муки.")

        return warnings

    # --- Недельное меню ---

    def _reconcile_wiped_groups(self, distribution: dict, product_plan: dict) -> tuple[dict, list]:
        """Группы, у которых в распределении есть граммы, но стоп-лист/фильтры не
        оставили ни одного продукта (product_plan пуст), нельзя молча терять: иначе
        круговая диаграмма показывает группу, а в меню и списке покупок её нет
        (тихий недокорм + врущая диаграмма). Переносим их граммы в мясо (основу
        рациона) и обнуляем группу — так сводка и меню снова сходятся.

        Возвращает (согласованное_распределение, список_выпавших_групп)."""
        wiped = [g for g, grams in distribution.items()
                 if grams > 0 and not product_plan.get(g)]
        if not wiped:
            return distribution, []

        moved = sum(distribution[g] for g in wiped)
        dist = dict(distribution)
        for g in wiped:
            dist[g] = 0
        # Переносим в мясо; если мяса нет — в первую непустую группу.
        sink = "muscle_meat" if product_plan.get("muscle_meat") else \
            next((g for g in dist if product_plan.get(g)), None)
        if sink:
            dist[sink] = self._round_g(dist[sink] + moved)
        return dist, wiped

    def _generate_weekly_menu(self, dog: DogProfile, product_plan: dict, meals_per_day: int,
                              distribution: dict) -> list[DayMenu]:
        """Генерирует 7-дневное меню.

        Принципы:
        - ОДИН белок на приём (не смешиваем говядину с индейкой в одной миске)
        - ОДИН овощ на приём (не салат из 3 овощей)
        - Баланс достигается за НЕДЕЛЮ, не за день
        - Граммовки округлены до 5-10г (практично)
        - Среда и суббота — рыбные дни
        - Субпродукты — не каждый день, а 3-4 раза в неделю
        - Кисломолочка — утром, через день
        - Яйца — 3 раза в неделю
        """
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

        # Доступные продукты по группам
        meats = product_plan.get("muscle_meat", [])
        bones = product_plan.get("raw_meaty_bones", [])
        organs = product_plan.get("organs", [])
        vegs = product_plan.get("vegetables", [])
        dairy = product_plan.get("dairy", [])
        eggs = product_plan.get("eggs", [])
        oils = product_plan.get("oils_supplements", [])
        fish_db = self.products_db.get("fish", [])

        # Суточные нормы по группам — берём УЖЕ согласованное распределение
        # (то же, что в круговой диаграмме и Ca:P), а не пересчитываем заново:
        # независимый пересчёт давал дрейф (сезон/беременность) и расхождение
        # сводки с меню. Сюда оно приходит после _reconcile_wiped_groups, поэтому
        # выпавшие стоп-листом группы (organs) уже перенесены в мясо.
        dist = distribution

        meat_daily = self._round_g(dist.get("muscle_meat", 0))
        bones_daily = self._round_g(dist.get("raw_meaty_bones", 0))
        organs_daily = self._round_g(dist.get("organs", 0))
        veg_daily = self._round_g(dist.get("vegetables", 0))
        dairy_daily = self._round_g(dist.get("dairy", 0))

        # Яйца — раскладываем НЕДЕЛЬНЫЙ бюджет (из distribution) по дням, а не
        # хардкодим 15/30 г: иначе крохе 2 кг достаётся ~4× нормы яйца за неделю
        # (целое яйцо ≈ дневная калорийность), а гиганту, наоборот, мало. Дни
        # яйца и размер порции выводим из бюджета — так меню сходится со сводкой.
        EGG_PIECE_G = 60.0  # вес куриного яйца (ср. pdf_generator.EGG_PIECE_GRAMS)
        egg_weekly = dist.get("eggs", 0) * 7
        if egg_weekly > 0:
            # минимум четверть яйца за подачу, максимум 4 дня (пн/ср/пт/вс)
            n_egg_days = min(4, max(1, int(egg_weekly / (EGG_PIECE_G * 0.25))))
            egg_days = set([0, 2, 4, 6][:n_egg_days])
            egg_serving = round(egg_weekly / n_egg_days)
        else:
            egg_days, egg_serving = set(), 0

        menu = []
        for i, day_name in enumerate(days):
            morning = []
            evening = []

            # --- УТРО ---

            # Мясо (утро) — один вид, ротация по дням
            if meats:
                m = meats[i % len(meats)]
                morning.append(MealPortion(m["product_id"], m["product_name"],
                    self._round_g(meat_daily / 2), "muscle_meat"))

            # Кости — утром (не каждый день при варке)
            if bones and dog.diet_type == "barf" and bones_daily > 0:
                b = bones[i % len(bones)]
                morning.append(MealPortion(b["product_id"], b["product_name"],
                    self._round_g(bones_daily), "raw_meaty_bones"))

            # Овощ (утро) — один, ротация
            if vegs:
                v = vegs[i % len(vegs)]
                morning.append(MealPortion(v["product_id"], v["product_name"],
                    self._round_g(veg_daily / 2), "vegetables"))

            # Кисломолочка — утром, через день (пн, ср, пт, вс)
            if dairy and i % 2 == 0:
                d = dairy[0]
                morning.append(MealPortion(d["product_id"], d["product_name"],
                    self._round_g(dairy_daily), "dairy"))

            # Рыбий жир и масла — это добавки, не продукты.
            # Они указаны на странице "Витамины и добавки", в меню не включаем.

            # --- ВЕЧЕР ---

            is_fish_day = day_name in ("Среда", "Суббота")

            if is_fish_day and fish_db:
                # Рыбный день — рыба вместо мяса
                available_fish = [f for f in fish_db if f.get("availability", "") != "unlimited" or dog.budget == "unlimited"]
                if not available_fish:
                    available_fish = fish_db
                fish = available_fish[i % len(available_fish)]
                evening.append(MealPortion(fish["id"], fish["name"],
                    self._round_g(meat_daily / 2), "fish"))
            else:
                # Обычный день — другое мясо, чем утром
                if meats:
                    m_idx = (i + 1) % len(meats)  # Следующий в ротации
                    if len(meats) > 1:
                        m_idx = (i + 1) % len(meats)
                    else:
                        m_idx = 0
                    m = meats[m_idx]
                    evening.append(MealPortion(m["product_id"], m["product_name"],
                        self._round_g(meat_daily / 2), "muscle_meat"))

            # Субпродукты — вечером, каждый день (ротация по видам)
            if organs:
                org = organs[i % len(organs)]
                evening.append(MealPortion(org["product_id"], org["product_name"],
                    self._round_g(organs_daily), "organs"))

            # Овощ (вечер) — другой, чем утром
            if vegs:
                v_idx = (i + 1) % len(vegs) if len(vegs) > 1 else 0
                v = vegs[v_idx]
                evening.append(MealPortion(v["product_id"], v["product_name"],
                    self._round_g(veg_daily / 2), "vegetables"))

            # Яйца — вечером, по недельному бюджету (egg_days / egg_serving выше)
            if eggs and i in egg_days and egg_serving > 0:
                e = eggs[0]
                evening.append(MealPortion(e["product_id"], e["product_name"],
                    egg_serving, "eggs"))

            # Кисломолочка — вечером, когда не было утром (вт, чт, сб) + воскресенье
            if dairy and len(dairy) > 1 and (i % 2 == 1 or i == 6):
                d = dairy[1] if len(dairy) > 1 else dairy[0]
                evening.append(MealPortion(d["product_id"], d["product_name"],
                    self._round_g(dairy_daily), "dairy"))

            # 3 кормления (крупные/гигантские породы — риск заворота; гастрит):
            # дробим вечерний приём на «День» + «Вечер» меньшего объёма (утро не
            # трогаем). Так в миске за раз меньше еды. Для 2-разовых midday пуст.
            midday = []
            if meals_per_day >= 3 and evening:
                midday = [MealPortion(p.product_id, p.product_name,
                                      self._round_g(p.grams / 2), p.group) for p in evening]
                evening = [MealPortion(p.product_id, p.product_name,
                                       max(1, round(p.grams - self._round_g(p.grams / 2))), p.group)
                           for p in evening]
            menu.append(DayMenu(day_name=day_name, morning=morning, evening=evening, midday=midday))

        return menu

    @staticmethod
    def _round_g(grams: float) -> float:
        """Округляет граммы до практичных значений: до 5г (мелкие), до 10г (крупные).

        Мелкие собаки: порция <2.5г раньше округлялась /5 в 0 (round(0.5)=0) —
        овощи 5г/день ÷ 2 приёма исчезали из меню. Положительная величина не
        должна стать нулём, поэтому для крошечных порций — шаг 1г, минимум 1г.
        """
        if grams <= 0:
            return 0
        if grams < 5:
            return max(1, round(grams))  # 1..4 г: точный шаг, никогда не 0
        if grams < 30:
            return round(grams / 5) * 5  # до 5г: 5, 10, 15, 20, 25
        return round(grams / 10) * 10    # до 10г: 30, 40, 50, 60...

    # --- Стоимость рациона ---

    def _calc_cost(self, product_plan: dict) -> float:
        """Стоимость рациона в рублях в день."""
        total = 0.0
        for group, products in product_plan.items():
            for p in products:
                product_info = self._all_products.get(p["product_id"])
                if product_info and "price_per_kg" in product_info:
                    total += p["grams"] / 1000 * product_info["price_per_kg"]
        return total

    # --- Рецепты для варёного рациона ---

    def _calc_cooking_tips(self, dog: DogProfile, product_plan: dict) -> list[str]:
        """Советы по приготовлению для варёного рациона."""
        tips = []
        tips.append("Мясо и субпродукты варите 20-30 минут на слабом огне. Не солите.")
        tips.append("Овощи добавляйте в последние 5-7 минут или давайте сырыми, натёртыми на тёрке.")
        tips.append("Бульон можно добавлять к порции — в нём остаются полезные вещества.")
        tips.append("Печень варите отдельно, не более 15 минут — она быстро становится жёсткой.")
        if any(p["product_id"].startswith("fish") or p.get("group") == "fish" for group in product_plan.values() for p in group):
            tips.append("Рыбу варите 10-15 минут. Проверьте на кости перед подачей.")
        tips.append("Готовую еду храните в холодильнике до 3 дней или замораживайте порционно.")
        return tips

    # --- Meal prep / контейнеры ---

    def _calc_meal_prep(self, dog: DogProfile, daily_grams: float, meals_per_day: int) -> dict:
        """Подсказка по заморозке и порционированию."""
        portion_g = round(daily_grams / meals_per_day / 10) * 10
        weekly_kg = round(daily_grams * 7 / 1000, 1)
        containers = meals_per_day * 7
        return {
            "portion_grams": portion_g,
            "containers_per_week": containers,
            "weekly_total_kg": weekly_kg,
            "tip": (
                f"Разложите еду на неделю в {containers} контейнеров по ~{portion_g} г. "
                f"Заморозьте. Размораживайте порцию в холодильнике за 12 часов до кормления."
            ),
        }

    # --- Пересчёт для щенков ---

    def _calc_puppy_recalc(self, dog: DogProfile, breed_info: Optional[dict]) -> str:
        """Для щенков: когда пересчитать рацион."""
        if dog.age_months >= 18:
            return ""
        if dog.age_months < 4:
            return "Пересчитайте рацион через 2-3 недели — щенок быстро растёт."
        elif dog.age_months < 6:
            return "Пересчитайте рацион через месяц или при изменении веса на 1+ кг."
        elif dog.age_months < 12:
            adult_months = breed_info.get("adult_months", 12) if breed_info else 12
            remaining = adult_months - dog.age_months
            if remaining > 0:
                return f"Пересчитайте через {remaining} мес., когда {dog.name} станет взрослой."
            return "Пересчитайте рацион через 2-3 месяца — рост ещё продолжается."
        else:
            return "Собака почти взрослая. Пересчитайте при стабилизации веса."

    # --- Утилиты ---

    def _normalize_diagnoses(self, diagnoses: list[str]) -> set[str]:
        """Превращает текстовые диагнозы в ключи для фильтрации."""
        mapping = {
            "панкреатит": "pancreatitis",
            "гастрит": "gastritis",
            "мкб": "kidney_disease",
            "мочекаменная": "kidney_disease",
            "печень": "liver_disease",
            "почки": "kidney_disease",
            "щитовидка": "thyroid_disease",
            "щитовидная": "thyroid_disease",
            "лактоза": "lactose_intolerance",
            "непереносимость молока": "lactose_intolerance",
        }
        result = set()
        for d in diagnoses:
            d_lower = d.lower()
            for key, val in mapping.items():
                if key in d_lower:
                    result.add(val)
        return result


# ---------------------------------------------------------------------------
# Быстрый тест
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    calc = DietCalculator()

    # Тестовый профиль
    dog = DogProfile(
        name="Барон",
        breed="Лабрадор-ретривер",
        age_months=36,
        sex="male",
        neutered=True,
        weight_kg=32,
        current_food="dry",
        condition="chubby",
        activity="moderate",
        diagnoses=[],
        stool="good",
        diet_type="barf",
        budget="market",
        stop_products=["курица"],
    )

    result = calc.calculate(dog)

    print(f"Собака: {result.dog.name} ({result.dog.breed})")
    print(f"Идеальный вес: {result.ideal_weight_kg} кг")
    print(f"RER: {result.rer_kcal} ккал | MER: {result.mer_kcal} ккал")
    print(f"Суточный объём: {result.daily_grams} г")
    print(f"Кормлений в день: {result.meals_per_day}")
    print(f"Ca:P = {result.ca_p_ratio}")
    print(f"\nРаспределение по группам:")
    for group, grams in result.distribution.items():
        print(f"  {group}: {grams} г")
    print(f"\nДобавки:")
    for s in result.supplements:
        print(f"  {s['name']}: {s['dosage']}")
    print(f"\nПредупреждения:")
    for w in result.warnings:
        print(f"  ⚠ {w}")
    print(f"\nМеню на понедельник:")
    day = result.weekly_menu[0]
    print(f"  Утро:")
    for p in day.morning:
        print(f"    {p.product_name}: {p.grams} г")
    print(f"  Вечер:")
    for p in day.evening:
        print(f"    {p.product_name}: {p.grams} г")
