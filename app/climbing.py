"""Climbing domain constants for ClimbConnect.

Single source of truth for disciplines, goals, formats, levels,
gear categories and product conditions used across the app.
Compatible with Python 3.7.
"""

# ============================================================
# CLIMBING DISCIPLINES (trainer specializations)
# ============================================================
DISCIPLINES = {
    "bouldering": {"name": "Боулдеринг", "icon": "icon-sport-bouldering"},
    "lead": {"name": "Трудность", "icon": "icon-sport-lead"},
    "speed": {"name": "Скорость", "icon": "icon-sport-speed"},
    "toprope": {"name": "Верхняя страховка", "icon": "icon-sport-toprope"},
    "trad": {"name": "Трад", "icon": "icon-sport-trad"},
    "multipitch": {"name": "Мультипитч", "icon": "icon-sport-multipitch"},
    "ice": {"name": "Лёд / Драйтулинг", "icon": "icon-sport-ice"},
    "training": {"name": "СФП / ОФП", "icon": "icon-sport-training"},
    "kids": {"name": "Детские занятия", "icon": "icon-sport-kids"},
}

DISCIPLINE_KEYS = list(DISCIPLINES.keys())

# ============================================================
# CLIENT GOALS (climbing-specific)
# ============================================================
GOALS = {
    "learn_basics": "Научиться с нуля",
    "improve_technique": "Улучшить технику",
    "grade_progression": "Рост по категориям",
    "competition_prep": "Подготовка к соревнованиям",
    "outdoor_transition": "Первый выход на скалы",
    "kids_coaching": "Занятия для ребёнка",
}

# ============================================================
# WORK FORMATS (where the trainer works)
# ============================================================
FORMATS = {
    "gym": "Скалодром",
    "outdoor": "Скалы",
    "online": "Онлайн",
}

# ============================================================
# STUDENT LEVELS the trainer works with
# ============================================================
LEVELS = {
    "beginner": "Новички",
    "intermediate": "Продолжающие",
    "advanced": "Опытные",
    "competition": "Спортсмены",
}

# ============================================================
# MARKETPLACE: GEAR CATEGORIES
# ============================================================
GEAR_CATEGORIES = {
    "shoes": "Скальные туфли",
    "harness": "Обвязки",
    "belay": "Страховочные устройства",
    "carabiners": "Карабины и оттяжки",
    "ropes": "Верёвки",
    "crashpads": "Крашпады",
    "chalk": "Магнезия и мешки",
    "helmets": "Каски",
    "trad_gear": "Закладки и френды",
    "ice_gear": "Лёд и драйтулинг",
    "training_gear": "Тренировочный инвентарь",
    "clothing": "Одежда",
    "packs": "Рюкзаки и сумки",
    "other": "Прочее",
}

# ============================================================
# MARKETPLACE: PRODUCT CONDITION
# ============================================================
CONDITIONS = {
    "new": "Новый",
    "like_new": "Как новый",
    "good": "Хорошее",
    "fair": "Удовлетворительное",
}

# ============================================================
# MARKETPLACE SETTINGS
# ============================================================
MARKET_FEE_RATE = 0.07  # 7% platform fee on released escrow

# Popular cities for filters / seeds
CITIES = ["Москва", "Санкт-Петербург", "Екатеринбург", "Красноярск", "Новосибирск", "Сочи", "Казань"]


def discipline_name(key):
    """Human readable discipline name, tolerant to unknown keys."""
    if not key:
        return ""
    item = DISCIPLINES.get(key)
    return item["name"] if item else key


def category_name(key):
    """Human readable gear category name, tolerant to unknown keys."""
    if not key:
        return ""
    return GEAR_CATEGORIES.get(key, key)


def condition_name(key):
    """Human readable condition name, tolerant to unknown keys."""
    if not key:
        return ""
    return CONDITIONS.get(key, key)
