"""
Склонение русских слов (кличек собак, продуктов).
Использует pymorphy3, с фоллбэком на правила для неизвестных слов.
"""

import pymorphy3

_morph = pymorphy3.MorphAnalyzer()

# Падежи: gent=родительный, datv=дательный, accs=винительный, ablt=творительный
CASES = ("gent", "datv", "accs", "ablt")


def _gender_tag(sex: str | None) -> str | None:
    """'female' -> 'femn', 'male' -> 'masc', иначе None."""
    if sex == "female":
        return "femn"
    if sex == "male":
        return "masc"
    return None


def _best_noun_parse(word: str, sex: str | None = None):
    """Найти лучший разбор слова как существительного/имени.

    Учитываем известный пол собаки: pymorphy для кличек часто предлагает
    разбор не того рода (напр. «Фрея» как родительный от мужского «Фрей»).
    Поэтому ранжируем: совпадение рода >> именительный падеж > ед.число >
    имя собственное > существительное > score pymorphy.
    """
    parses = _morph.parse(word)
    if not parses:
        return None
    want = _gender_tag(sex)

    def rank(p) -> float:
        tag = str(p.tag)
        s = 0.0
        if want:
            if want in p.tag:
                s += 100
            elif ("femn" in p.tag or "masc" in p.tag):
                s -= 100  # род не тот — почти наверняка неверный разбор
        if "nomn" in p.tag:
            s += 10      # слово дано в им.падеже — склонять есть от чего
        if "sing" in p.tag:
            s += 5       # ед.ч. (а не «Зефир» -> мн. «Зефирам»)
        elif "plur" in p.tag:
            s -= 50      # мн.ч. для клички почти всегда ошибка разбора
        if "anim" in p.tag:
            s += 4       # собака одушевлённая (важно для вин.падежа)
        if "Name" in p.tag:
            s += 3
        if "NOUN" in p.tag:
            s += 1
        # лемма совпадает с самим словом -> это и есть им.падеж клички
        if p.normal_form == word.lower():
            s += 20
        return s + p.score

    best = max(parses, key=rank)
    if ("NOUN" in best.tag or "Name" in best.tag) and "plur" not in best.tag:
        return best
    return None


def _fallback_decline(word: str, case: str, sex: str | None = None) -> str:
    """Склонение по базовым правилам, если pymorphy не справился."""
    if not word:
        return word

    low = word.lower()

    # Женские имена на -а, -я
    if low.endswith("а"):
        stems = {"gent": "ы", "datv": "е", "accs": "у", "ablt": "ой"}
        # жк/шк/чк → и вместо ы
        if len(low) >= 2 and low[-2] in "гкхжшщч":
            stems["gent"] = "и"
        return word[:-1] + stems.get(case, "а")

    if low.endswith("я"):
        stems = {"gent": "и", "datv": "е", "accs": "ю", "ablt": "ей"}
        return word[:-1] + stems.get(case, "я")

    # Имена на согласную: мужские склоняем, женские (Найт, Жасмин) — нет
    if low[-1] not in "аеёиоуыэюя":
        if sex == "female":
            return word  # женские имена на согласную не склоняются
        stems = {"gent": "а", "datv": "у", "accs": "а", "ablt": "ом"}
        return word + stems.get(case, "")

    # Имена на -й
    if low.endswith("й"):
        stems = {"gent": "я", "datv": "ю", "accs": "я", "ablt": "ем"}
        return word[:-1] + stems.get(case, "й")

    # Не склоняем (иностранные, оканчивающиеся на гласную кроме а/я)
    return word


def decline(word: str, case: str, sex: str | None = None) -> str:
    """
    Склоняет слово в нужный падеж.
    case: 'gent' (родительный), 'datv' (дательный), 'accs' (винительный), 'ablt' (творительный)
    sex: 'female'/'male'/None — пол собаки, помогает выбрать верный разбор клички.
    Сохраняет оригинальный регистр первой буквы.
    """
    if not word or case not in CASES:
        return word

    was_capitalized = word[0].isupper()
    want = _gender_tag(sex)

    # Собака одушевлённая: у мужских кличек на согласную винительный = родительный
    # (pymorphy часто видит неодушевлённое нарицательное: «зефир», «персик» -> accs=nomn).
    if case == "accs" and want == "masc" and word.lower()[-1] not in "аеёиоуыэюяй":
        return decline(word, "gent", sex)

    p = _best_noun_parse(word, sex)
    if p and ("NOUN" in p.tag or "Name" in p.tag):
        inflected = p.inflect({case})
        # Принимаем результат, только если род совпал с известным полом
        # (иначе pymorphy ошибся лексемой — идём в фоллбэк по правилам).
        if inflected and (not want or want in inflected.tag or
                          ("femn" not in inflected.tag and "masc" not in inflected.tag)):
            result = inflected.word
            if was_capitalized:
                result = result[0].upper() + result[1:]
            return result

    # Фоллбэк
    result = _fallback_decline(word, case, sex)
    if was_capitalized:
        result = result[0].upper() + result[1:]
    return result


def decline_name(name: str, case: str, sex: str | None = None) -> str:
    """Склоняет кличку (может быть из нескольких слов). sex — пол собаки."""
    if not name:
        return name
    # Для кличек из одного слова
    parts = name.split()
    if len(parts) == 1:
        return decline(parts[0], case, sex)
    # Для составных — склоняем последнее слово
    parts[-1] = decline(parts[-1], case, sex)
    return " ".join(parts)
