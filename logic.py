# -*- coding: utf-8 -*-
"""Логика без Android: разбор фразы и подбор приложения."""
import re
from difflib import SequenceMatcher

from apps import ALIASES

WAKE_WORDS = ("запуск", "байт")
VERBS = ("запусти", "запустить", "запуск", "открой", "открыть",
         "включи", "включить")
FILLER = ("приложение", "программу", "программа", "пожалуйста")

_TR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def clean(text):
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def squash(text):
    """Без пробелов и без удвоенных букв: 'инстаграмм' == 'инстаграм'."""
    return re.sub(r"(.)\1+", r"\1", clean(text).replace(" ", ""))


def translit(text):
    return "".join(_TR.get(ch, ch) for ch in clean(text))


def is_wake(text):
    t = clean(text)
    return all(w in t for w in WAKE_WORDS)


def parse_command(text):
    """'запусти инстаграм' -> 'инстаграм'; не команда -> None."""
    words = clean(text).split()
    if len(words) < 2 or words[0] not in VERBS:
        return None
    rest = [w for w in words[1:] if w not in FILLER]
    return " ".join(rest) or None


def _sim(a, b):
    return SequenceMatcher(None, a, b).ratio()


def match_alias(name):
    """-> (оценка 0..1, пакет)"""
    n = squash(name)
    best = (0.0, None)
    for key, pkg in ALIASES.items():
        s = _sim(n, squash(key))
        if s > best[0]:
            best = (s, pkg)
    return best


def match_label(name, apps):
    """apps: список (название, пакет) -> (оценка, пакет, название)"""
    n = squash(name)
    nt = squash(translit(name))
    best = (0.0, None, None)
    for label, pkg in apps:
        l = squash(label)
        if not l:
            continue
        s = max(_sim(n, l), _sim(nt, l))
        if len(n) >= 4 and (n in l or l in n):
            s = max(s, 0.85)
        if len(nt) >= 4 and (nt in l or l in nt):
            s = max(s, 0.85)
        if s > best[0]:
            best = (s, pkg, label)
    return best
