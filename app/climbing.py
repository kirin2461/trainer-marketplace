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
# Progressive marketplace commission: the more sales a seller has, the lower the fee.
MARKET_PROMO_FREE_SALES = 3  # every seller's first N sales are commission-free
MARKET_FEE_TIERS = [  # (min completed sales, fee rate) — checked from the top
    (100, 0.04),
    (30, 0.05),
    (10, 0.06),
    (0, 0.08),
]


def market_fee_rate(sales_count: int) -> float:
    """Commission rate for the seller's NEXT sale given their completed sales so far.
    The first MARKET_PROMO_FREE_SALES sales are free; then a progressive tier applies."""
    if sales_count < MARKET_PROMO_FREE_SALES:
        return 0.0
    for threshold, rate in MARKET_FEE_TIERS:
        if sales_count >= threshold:
            return rate
    return MARKET_FEE_TIERS[-1][1]

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
