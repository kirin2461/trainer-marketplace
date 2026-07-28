"""Real climbing gyms (скалодромы) seed data for ClimbConnect.

Data researched from public sources (gym websites, T-Journal city guide,
Zoon) in July 2026: names, addresses, wall types and heights are real.
Coordinates are approximate map pins for the Yandex map.
Compatible with Python 3.7.
"""

# Discipline keys reuse app.climbing.DISCIPLINES keys:
# bouldering | lead | speed | toprope | kids | training | ice

GYMS_DATA = [
    # ================= МОСКВА =================
    {
        "name": "Скала Сити",
        "city": "Москва",
        "address": "Кутузовский пр., 36, стр. 13/14",
        "metro": "Парк Победы",
        "lat": 55.7338, "lng": 37.5176,
        "disciplines": ["lead", "toprope", "kids", "training"],
        "wall_height": "12 м",
        "price_from": 850,
        "website": "https://skala-city.ru",
        "description": "Один из старейших скалодромов Москвы (с 2004 года). Около 100 трасс "
                       "на трудность, зона СФП и разминки с мунбордом, сауна. Выезды на "
                       "естественный рельеф.",
    },
    {
        "name": "LimeStone",
        "city": "Москва",
        "address": "ул. Доброслободская, 21",
        "metro": "Бауманская",
        "lat": 55.7808, "lng": 37.6829,
        "disciplines": ["bouldering", "training"],
        "wall_height": "4,5 м",
        "price_from": 700,
        "website": "https://lmstn.ru",
        "description": "Боулдеринговый зал с зонами разминки и кафе. Трассы для новичков и "
                       "опытных, еженедельная накрутка, тематические вечеринки и выезды на скалы.",
    },
    {
        "name": "Rock Zona",
        "city": "Москва",
        "address": "пр-т Андропова, 22",
        "metro": "Коломенская",
        "lat": 55.6769, "lng": 37.6566,
        "disciplines": ["bouldering", "kids", "training"],
        "wall_height": "4,5 м",
        "price_from": 700,
        "website": "https://rockzona.ru",
        "description": "Боулдеринг у метро Коломенская: трассы от 5а до 7с, еженедельное "
                       "обновление, кафе, разминочная зона, детская секция O'Skal.",
    },
    {
        "name": "BigWall Sport (Динамо)",
        "city": "Москва",
        "address": "Ленинградский пр., 36",
        "metro": "Динамо",
        "lat": 55.7912, "lng": 37.5587,
        "disciplines": ["bouldering", "training"],
        "wall_height": "4,8 м",
        "price_from": 690,
        "website": "https://bigwallsport.ru",
        "description": "Первый зал сети BigWall на стадионе «Динамо». Kilter Board 4,8x3,6 м "
                       "с 70 тысячами пролазов в приложении, ковровое покрытие против магнезийной пыли.",
    },
    {
        "name": "BigWall Sport (Ривьера)",
        "city": "Москва",
        "address": "ул. Автозаводская, 18, ТРЦ «Ривьера»",
        "metro": "Автозаводская",
        "lat": 55.7055, "lng": 37.6489,
        "disciplines": ["bouldering", "training"],
        "wall_height": "4,8 м",
        "price_from": 690,
        "website": "https://bigwallsport.ru",
        "description": "Самый большой зал сети: более 150 боулдеринговых трасс, еженедельно "
                       "обновляют 30 трасс. На берегу Москвы-реки.",
    },
    {
        "name": "Sportstation",
        "city": "Москва",
        "address": "ул. Новоостаповская, 5, стр. 2",
        "metro": "Дубровка",
        "lat": 55.7193, "lng": 37.6801,
        "disciplines": ["bouldering", "lead", "toprope", "kids", "training"],
        "wall_height": "12 м",
        "price_from": 1000,
        "website": "https://station.club",
        "description": "Полноценный скалолазный центр: трудность 12 м (45+ трасс), боулдеринг, "
                       "зона ОФП с кампусбордом и систембордом, автостраховки для новичков.",
    },
    {
        "name": "Атмосфера",
        "city": "Москва",
        "address": "Электролитный пр., 7Б, СК «Кант»",
        "metro": "Нагорная",
        "lat": 55.6768, "lng": 37.6148,
        "disciplines": ["bouldering", "lead", "toprope"],
        "wall_height": "9 м",
        "price_from": 700,
        "website": "https://atmosfera.club",
        "description": "Два боулдеринговых зала и зона трудности 9 м на территории СК «Кант». "
                       "Трассы от 5а до 8а, прокат снаряжения.",
    },
    {
        "name": "Центр скалолазания ЦСКА",
        "city": "Москва",
        "address": "3-я Песчаная ул., 2, стр. 1",
        "metro": "Сокол",
        "lat": 55.7944, "lng": 37.5132,
        "disciplines": ["lead", "toprope", "speed", "bouldering", "kids", "training"],
        "wall_height": "19 м",
        "price_from": 1000,
        "website": "https://climbingcska.ru",
        "description": "Четыре зала: трудность до 19 м, эталонная скорость 15 м, боулдеринг, "
                       "детский зал с автостраховками. Соревновательная зона международного уровня.",
    },
    {
        "name": "Red Point",
        "city": "Москва",
        "address": "ул. Вятская, 27, корп. 12",
        "metro": "Савёловская",
        "lat": 55.7951, "lng": 37.5881,
        "disciplines": ["lead", "toprope", "bouldering"],
        "wall_height": "12,5 м",
        "price_from": 700,
        "website": "https://redpoint.moscow",
        "description": "Трудность 12,5 м с вертикалью и нависаниями плюс двухэтажный "
                       "боулдеринговый зал внутри фитнес-клуба «Мегаполис».",
    },
    {
        "name": "X8",
        "city": "Москва",
        "address": "5-я Кабельная ул., 2, ТРК «СпортEX»",
        "metro": "Авиамоторная",
        "lat": 55.7527, "lng": 37.7172,
        "disciplines": ["lead", "toprope", "bouldering", "kids"],
        "wall_height": "8 м",
        "price_from": 600,
        "website": "http://x8climb.ru",
        "description": "Залы трудности и боулдеринга общей площадью ~500 м², верёвочный парк "
                       "«Пещера». Детские и взрослые секции, городской лагерь.",
    },
    {
        "name": "Скалодром.ру",
        "city": "Москва",
        "address": "Одинцово, ул. Транспортная, 2",
        "metro": "Одинцово",
        "lat": 55.6737, "lng": 37.2825,
        "disciplines": ["bouldering", "lead", "toprope", "speed", "kids"],
        "wall_height": "13,5 м",
        "price_from": 800,
        "website": "https://gym-skalodrom.ru",
        "description": "1000 м² и все три дисциплины: боулдеринг, трудность 13,5 м с "
                       "автостраховкой, эталонная скорость 15 м. Kilter Board и Luxov Gaming Board.",
    },
    {
        "name": "Tengu's (Мичуринский)",
        "city": "Москва",
        "address": "ул. Лобачевского, 114",
        "metro": "Мичуринский проспект",
        "lat": 55.6883, "lng": 37.4699,
        "disciplines": ["bouldering"],
        "wall_height": "4,5 м",
        "price_from": 1100,
        "website": "https://tengus.ru",
        "description": "Боулдеринг-кафе с коворкингом: еженедельная накрутка, трассы от "
                       "новичковых до опытных, тематические фестивали.",
    },
    # ================= САНКТ-ПЕТЕРБУРГ =================
    {
        "name": "Северная стена",
        "city": "Санкт-Петербург",
        "address": "Пискарёвский пр., 63, корп. 2",
        "metro": "Площадь Мужества",
        "lat": 59.9890, "lng": 30.4055,
        "disciplines": ["lead", "toprope", "speed", "bouldering", "training"],
        "wall_height": "15 м",
        "price_from": 600,
        "website": "",
        "description": "Один из крупнейших скалодромов Петербурга: высокие стены на трудность, "
                       "трасса скорости и боулдеринговый зал. База спортивных сборных.",
    },
    {
        "name": "AntClub",
        "city": "Санкт-Петербург",
        "address": "ул. Руставели, 13, корп. 1",
        "metro": "Гражданский проспект",
        "lat": 59.9771, "lng": 30.3734,
        "disciplines": ["bouldering", "training"],
        "wall_height": "4,5 м",
        "price_from": 550,
        "website": "",
        "description": "Камерный боулдеринговый зал на севере города: регулярная накрутка, "
                       "дружелюбное комьюнити, занятия для начинающих.",
    },
    # ================= ЕКАТЕРИНБУРГ =================
    {
        "name": "Rock and Wall",
        "city": "Екатеринбург",
        "address": "ул. Радищева, 55, ТЦ «На Московской горке»",
        "metro": "Геологическая",
        "lat": 56.8265, "lng": 60.6025,
        "disciplines": ["bouldering", "lead", "speed", "kids", "training"],
        "wall_height": "10 м",
        "price_from": 500,
        "website": "https://rockandwall.ru",
        "description": "Самый большой скалолазный центр Урала (2 филиала, 550+ м² стен): "
                       "боулдеринг, трудность и скорость. Тренируются члены сборной России.",
    },
    {
        "name": "Вертикаль (ДИВС)",
        "city": "Екатеринбург",
        "address": "Олимпийская наб., 3",
        "metro": "Динамо",
        "lat": 56.8445, "lng": 60.6508,
        "disciplines": ["lead", "speed", "toprope"],
        "wall_height": "15 м",
        "price_from": 400,
        "website": "",
        "description": "Трасса во Дворце игровых видов спорта: 550 м², высота 15 м, ширина 30 м. "
                       "Тренировочная база сборной Свердловской области.",
    },
    # ================= КАЗАНЬ =================
    {
        "name": "Скалалэнд",
        "city": "Казань",
        "address": "ул. Свободы, 13А",
        "metro": "",
        "lat": 55.7410, "lng": 49.1415,
        "disciplines": ["bouldering", "toprope", "kids"],
        "wall_height": "7 м",
        "price_from": 450,
        "website": "",
        "description": "Центр приключений со скалодромом: трассы для детей и взрослых, "
                       "инструкторы для первых шагов в скалолазании.",
    },
    # ================= СОЧИ =================
    {
        "name": "Скалодром МореМолл",
        "city": "Сочи",
        "address": "Новороссийское ш., 216, ТРЦ «МореМолл»",
        "metro": "",
        "lat": 43.5786, "lng": 39.7382,
        "disciplines": ["bouldering", "toprope", "kids"],
        "wall_height": "8 м",
        "price_from": 500,
        "website": "",
        "description": "Городской скалодром в ТРЦ «МореМолл» — разминка перед выходом "
                       "на сочинский известняк и Красную Поляну.",
    },
]

# Demo trainers -> gym names they are attached to (matched with seeded trainers)
DEMO_TRAINER_GYMS = {
    "dmitry@trainer.ru": ["Скала Сити"],
    "anton@trainer.ru": ["BigWall Sport (Динамо)", "BigWall Sport (Ривьера)"],
    "vika@trainer.ru": ["Северная стена"],
    "olga@trainer.ru": ["LimeStone"],
    "olgad@trainer.ru": ["Rock Zona"],
    "marina@trainer.ru": ["Северная стена", "AntClub"],
    "ruslan@trainer.ru": ["Скалалэнд"],
}


def seed_climbing_gyms(db):
    """Insert gyms if the table is empty and attach demo trainers. Idempotent."""
    from app.database import ClimbingGym, User, trainer_gyms

    if db.query(ClimbingGym).count() == 0:
        for gd in GYMS_DATA:
            db.add(ClimbingGym(**gd))
        db.commit()

    link_demo_trainers(db)


def link_demo_trainers(db):
    """Attach seeded demo trainers to their gyms (only when not attached yet)."""
    from app.database import ClimbingGym, User, trainer_gyms

    gyms_by_name = {g.name: g for g in db.query(ClimbingGym).all()}
    for email, gym_names in DEMO_TRAINER_GYMS.items():
        trainer = db.query(User).filter(User.email == email).first()
        if not trainer:
            continue
        existing = {row.gym_id for row in db.execute(
            trainer_gyms.select().where(trainer_gyms.c.trainer_id == trainer.id))}
        for name in gym_names:
            gym = gyms_by_name.get(name)
            if gym and gym.id not in existing:
                db.execute(trainer_gyms.insert().values(trainer_id=trainer.id, gym_id=gym.id))
    db.commit()


def get_trainer_gyms(db, trainer_id):
    """Gyms the trainer is attached to, ordered by city/name."""
    from app.database import ClimbingGym, trainer_gyms
    rows = db.execute(
        trainer_gyms.select().where(trainer_gyms.c.trainer_id == trainer_id))
    gym_ids = [r.gym_id for r in rows]
    if not gym_ids:
        return []
    return db.query(ClimbingGym).filter(ClimbingGym.id.in_(gym_ids)).order_by(
        ClimbingGym.city, ClimbingGym.name).all()


def set_trainer_gyms(db, trainer_id, gym_ids):
    """Replace trainer's gym attachments. Returns attached gyms."""
    from app.database import ClimbingGym, trainer_gyms
    db.execute(trainer_gyms.delete().where(trainer_gyms.c.trainer_id == trainer_id))
    gyms = []
    if gym_ids:
        gyms = db.query(ClimbingGym).filter(ClimbingGym.id.in_(gym_ids)).all()
        for g in gyms:
            db.execute(trainer_gyms.insert().values(trainer_id=trainer_id, gym_id=g.id))
    db.commit()
    return gyms


def get_gym_trainers(db, gym_id):
    """Active trainers attached to the gym."""
    from app.database import User, trainer_gyms
    rows = db.execute(trainer_gyms.select().where(trainer_gyms.c.gym_id == gym_id))
    trainer_ids = [r.trainer_id for r in rows]
    if not trainer_ids:
        return []
    return db.query(User).filter(
        User.id.in_(trainer_ids), User.role == "trainer", User.status == "active"
    ).order_by(User.rating.desc()).all()
