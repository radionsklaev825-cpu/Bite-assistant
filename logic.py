# -*- coding: utf-8 -*-
"""Логика без Android: разбор фразы и подбор приложения."""
import re
from difflib import SequenceMatcher

from apps import ALIASES

WAKE_WORDS = ("запуск", "байт")
VERBS = ("запусти", "запустить", "запуск", "открой", "открыть",
         "включи", "включить", "зайди", "зайти", "перейди", "перейти")
FILLER = ("приложение", "программу", "программа", "пожалуйста", "в", "на")

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
    """'запусти инстаграм' -> 'инстаграм'. Глагол ищем в любом месте фразы;
    если глагола нет, но фраза короткая (1-3 слова), считаем её названием приложения."""
    words = clean(text).split()
    if not words:
        return None
    start = None
    for k, w in enumerate(words):
        if w in VERBS:
            start = k + 1
            break
    if start is None:
        if len(words) > 3:
            return None
        start = 0
    rest = [w for w in words[start:] if w not in FILLER and w not in VERBS]
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


# ---- названия приложений для голосовой грамматики -------------------------------
_LAT_PAIRS = (("sch", "щ"), ("tch", "ч"), ("sh", "ш"), ("ch", "ч"), ("zh", "ж"),
              ("th", "т"), ("ph", "ф"), ("ck", "к"), ("kh", "х"), ("ee", "и"),
              ("oo", "у"), ("ou", "ау"), ("ya", "я"), ("yu", "ю"), ("ts", "ц"),
              ("qu", "кв"))
_LAT_ONE = {
    "a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф", "g": "г",
    "h": "х", "i": "и", "j": "дж", "k": "к", "l": "л", "m": "м", "n": "н",
    "o": "о", "p": "п", "q": "к", "r": "р", "s": "с", "t": "т", "u": "у",
    "v": "в", "w": "в", "x": "кс", "y": "и", "z": "з",
}


def _lat_word(w, c_soft=False, y_j=False):
    out = ""
    i = 0
    while i < len(w):
        for pat, rep in _LAT_PAIRS:
            if w.startswith(pat, i):
                out += rep
                i += len(pat)
                break
        else:
            ch = w[i]
            if ch == "c" and c_soft:
                rep = "с"
            elif ch == "y" and y_j:
                rep = "й"
            else:
                rep = _LAT_ONE.get(ch, "")
            out += rep
            i += 1
    return re.sub(r"(.)\1+", r"\1", out)


def spoken_variants(label):
    """Как название приложения можно произнести по-русски.
    Русские названия берём как есть, английские переводим в русские буквы."""
    t = clean(label)
    if not t:
        return []
    if re.fullmatch(r"[а-я ]+", t):
        return [t] if len(t) >= 3 else []
    if re.fullmatch(r"[a-z ]+", t):
        words = t.split()
        res = {" ".join(_lat_word(w) for w in words)}
        if len(words) == 1:
            res.add(_lat_word(words[0], c_soft=True))
            res.add(_lat_word(words[0], y_j=True))
            res.add(_lat_word(words[0], c_soft=True, y_j=True))
        return [r for r in res if len(r) >= 3]
    return []


def spoken_names(labels, aliases, vocab=None):
    """Все названия, которые Байт будет ждать в команде. Если известен словарь
    модели (vocab), оставляем только слова, которые она умеет распознавать."""
    names = set(aliases)
    for lab in labels:
        names.update(spoken_variants(lab))
    if vocab:
        names = {n for n in names if all(w in vocab for w in n.split())}
    return sorted(names)
