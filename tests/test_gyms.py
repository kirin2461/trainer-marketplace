"""Tests for climbing gyms: seeding, map pages, JSON API,
trainer<->gym linking and booking with a chosen gym."""

import pytest

from app.database import ClimbingGym, Booking  # noqa: E402
from app.gyms_data import (  # noqa: E402
    GYMS_DATA, seed_climbing_gyms, get_trainer_gyms, set_trainer_gyms,
)


def _auth(client, user_id):
    client.cookies.set("user_id", str(user_id))


@pytest.fixture
def gyms(db):
    """Seed gyms into the test DB."""
    seed_climbing_gyms(db)
    return db.query(ClimbingGym).order_by(ClimbingGym.id).all()


# ------------------------- seeding & API -------------------------

def test_gyms_seeded(db, gyms):
    assert len(gyms) == len(GYMS_DATA)
    g = gyms[0]
    assert g.name and g.city and g.address
    assert isinstance(g.lat, float) and isinstance(g.lng, float)


def test_gyms_seed_idempotent(db, gyms):
    seed_climbing_gyms(db)  # second run must not duplicate
    assert db.query(ClimbingGym).count() == len(GYMS_DATA)


def test_api_gyms_list(client, gyms):
    res = client.get("/api/gyms")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == len(GYMS_DATA)
    for field in ("id", "name", "city", "address", "lat", "lng",
                  "disciplines", "disc_names", "trainers_count"):
        assert field in data[0]


def test_api_gyms_city_filter(client, gyms):
    res = client.get("/api/gyms", params={"city": "Москва"})
    assert res.status_code == 200
    data = res.json()
    assert 0 < len(data) < len(GYMS_DATA)
    assert all(g["city"] == "Москва" for g in data)


# ------------------------- pages -------------------------

def test_gyms_page_renders_map(client, gyms):
    res = client.get("/gyms")
    assert res.status_code == 200
    assert 'id="gymsMap"' in res.text
    assert "api-maps.yandex.ru" in res.text
    assert "Скала Сити" in res.text


def test_gyms_page_city_filter(client, gyms):
    res = client.get("/gyms", params={"city": "Екатеринбург"})
    assert res.status_code == 200
    assert "Rock and Wall" in res.text
    assert "Скала Сити" not in res.text


def test_gym_detail_page(client, gyms):
    gym = gyms[0]
    res = client.get("/gyms/%d" % gym.id)
    assert res.status_code == 200
    assert gym.name in res.text
    assert 'id="gymMap"' in res.text


def test_gym_detail_404(client, gyms):
    res = client.get("/gyms/99999")
    assert res.status_code == 404


# ------------------------- trainer <-> gym linking -------------------------

def test_showcase_link_gyms(client, db, test_trainer, gyms):
    _auth(client, test_trainer.id)
    gym_ids = [gyms[0].id, gyms[1].id]
    res = client.post("/api/showcase", data={
        "disciplines": ["bouldering"],
        "gym_ids": [str(g) for g in gym_ids],
    })
    assert res.status_code == 200
    linked = get_trainer_gyms(db, test_trainer.id)
    assert {g.id for g in linked} == set(gym_ids)


def test_showcase_unlink_all_gyms(client, db, test_trainer, gyms):
    set_trainer_gyms(db, test_trainer.id, [gyms[0].id])
    _auth(client, test_trainer.id)
    res = client.post("/api/showcase", data={"disciplines": ["bouldering"]})
    assert res.status_code == 200
    assert get_trainer_gyms(db, test_trainer.id) == []


def test_showcase_link_unknown_gym(client, db, test_trainer, gyms):
    _auth(client, test_trainer.id)
    res = client.post("/api/showcase", data={"gym_ids": ["99999"]})
    assert res.status_code == 422


def test_showcase_link_gyms_forbidden_for_client(client, test_client_user, gyms):
    _auth(client, test_client_user.id)
    res = client.post("/api/showcase", data={"gym_ids": [str(gyms[0].id)]})
    assert res.status_code == 403


def test_trainer_detail_shows_gyms(client, db, test_trainer, gyms):
    set_trainer_gyms(db, test_trainer.id, [gyms[0].id])
    res = client.get("/trainer/%d" % test_trainer.id)
    assert res.status_code == 200
    assert gyms[0].name in res.text
    assert "/gyms/%d" % gyms[0].id in res.text


def test_gym_page_shows_trainers(client, db, test_trainer, gyms):
    set_trainer_gyms(db, test_trainer.id, [gyms[0].id])
    res = client.get("/gyms/%d" % gyms[0].id)
    assert res.status_code == 200
    assert test_trainer.name in res.text


def test_api_gyms_trainers_count(client, db, test_trainer, gyms):
    set_trainer_gyms(db, test_trainer.id, [gyms[0].id])
    res = client.get("/api/gyms")
    data = {g["id"]: g for g in res.json()}
    assert data[gyms[0].id]["trainers_count"] == 1


# ------------------------- booking with gym -------------------------

def _rich_client(db, user):
    user.wallet_balance = 100000
    db.commit()


def test_book_page_has_gym_select(client, db, test_trainer, test_client_user, gyms):
    set_trainer_gyms(db, test_trainer.id, [gyms[0].id])
    _auth(client, test_client_user.id)
    res = client.get("/book/%d" % test_trainer.id)
    assert res.status_code == 200
    assert 'name="gym_id"' in res.text
    assert "Залы тренера" in res.text


def test_booking_with_gym(client, db, test_trainer, test_client_user, gyms):
    _auth(client, test_client_user.id)
    _rich_client(db, test_client_user)
    res = client.post("/api/bookings", data={
        "trainer_id": str(test_trainer.id),
        "booking_type": "single",
        "scheduled_at": "2026-08-01T10:00",
        "gym_id": str(gyms[0].id),
        "notes": "тест зала",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["gym"] == gyms[0].name
    booking = db.query(Booking).filter(Booking.id == data["booking_id"]).first()
    assert booking.gym_id == gyms[0].id


def test_booking_with_empty_gym(client, db, test_trainer, test_client_user, gyms):
    """Empty select value ('' = договориться в чате) must be accepted."""
    _auth(client, test_client_user.id)
    _rich_client(db, test_client_user)
    res = client.post("/api/bookings", data={
        "trainer_id": str(test_trainer.id),
        "booking_type": "single",
        "scheduled_at": "2026-08-01T10:00",
        "gym_id": "",
    })
    assert res.status_code == 200
    assert res.json()["gym"] is None


def test_booking_without_gym_param(client, db, test_trainer, test_client_user, gyms):
    _auth(client, test_client_user.id)
    _rich_client(db, test_client_user)
    res = client.post("/api/bookings", data={
        "trainer_id": str(test_trainer.id),
        "booking_type": "single",
        "scheduled_at": "2026-08-01T10:00",
    })
    assert res.status_code == 200
    assert res.json()["gym"] is None


def test_booking_unknown_gym(client, db, test_trainer, test_client_user, gyms):
    _auth(client, test_client_user.id)
    _rich_client(db, test_client_user)
    res = client.post("/api/bookings", data={
        "trainer_id": str(test_trainer.id),
        "booking_type": "single",
        "scheduled_at": "2026-08-01T10:00",
        "gym_id": "99999",
    })
    assert res.status_code == 404


def test_booking_invalid_gym_id(client, db, test_trainer, test_client_user, gyms):
    _auth(client, test_client_user.id)
    _rich_client(db, test_client_user)
    res = client.post("/api/bookings", data={
        "trainer_id": str(test_trainer.id),
        "booking_type": "single",
        "scheduled_at": "2026-08-01T10:00",
        "gym_id": "abc",
    })
    assert res.status_code == 422
