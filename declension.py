"""
Склонение русских слов (кличек собак, продуктов).
Использует pymorphy3, с фоллбэком на правила для неизвестных слов.
"""

import pymorphy3

_morph = pymorphy3.MorphAnalyzer()

# Падежи: gent=родительный, datv=дательный, accs=винительный, ablt=творительный
CASES = ("gent", "datv", "accs", "ablt")


def _best_noun_parse(word: str):
    """Найти лучший разбор слова как существительного/имени."""
    parses = _morph.parse(word)
    # Сначала ищем имя собственное (Name)
    for p in parses:
        if "Name" in p.tag:
            return p
    # Потом существительное
    for p in parses:
        if "NOUN" in p.tag:
            return p
    # Если ничего — первый разбор
    return parses[0] if parses else None


def _fallback_decline(word: str, case: str) -> str:
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

    # Мужские имена на согласную
    if low[-1] not in "аеёиоуыэюя":
        stems = {"gent": "а", "datv": "у", "accs": "а", "ablt": "ом"}
        return word + stems.get(case, "")

    # Имена на -й
    if low.endswith("й"):
        stems = {"gent": "я", "datv": "ю", "accs": "я", "ablt": "ем"}
        return word[:-1] + stems.get(case, "й")

    # Не склоняем (иностранные, оканчивающиеся на гласную кроме а/я)
    return word


def decline(word: str, case: str) -> str:
    """
    Склоняет слово в нужный падеж.
    case: 'gent' (родительный), 'datv' (дательный), 'accs' (винительный), 'ablt' (творительный)
    Сохраняет оригинальный регистр первой буквы.
    """
    if not word or case not in CASES:
        return word

    was_capitalized = word[0].isupper()

    p = _best_noun_parse(word)
    if p and ("NOUN" in p.tag or "Name" in p.tag):
        inflected = p.inflect({case})
        if inflected:
            result = inflected.word
            if was_capitalized:
                result = result[0].upper() + result[1:]
            return result

    # Фоллбэк
    result = _fallback_decline(word, case)
    if was_capitalized:
        result = result[0].upper() + result[1:]
    return result


def decline_name(name: str, case: str) -> str:
    """Склоняет кличку (может быть из нескольких слов)."""
    if not name:
        return name
    # Для кличек из одного слова
    parts = name.split()
    if len(parts) == 1:
        return decline(parts[0], case)
    # Для составных — склоняем последнее слово
    parts[-1] = decline(parts[-1], case)
    return " ".join(parts)
