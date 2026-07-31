"""Comprehensive tests for ClimbConnect (climbing trainers + gear marketplace).

Covers:
- Authentication (register, login, logout, rate limiting)
- Trainer browsing and climbing-specific filters
- Trainer showcase (витрина/анкета)
- Booking creation and completion
- Wallet deposits and viewing
- Chat messaging
- Reviews
- Recommendations
- Marketplace: listings, filters, direct buy with progressive commission, seller reviews
- Static pages
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import pytest

from tests.conftest import _authenticate_client


# ============================================================
# AUTH TESTS
# ============================================================

class TestAuth:
    """Tests for /api/auth/* endpoints."""

    def test_register_success(self, client: TestClient, db: Session) -> None:
        response = client.post(
            "/api/auth/register",
            data={
                "name": "New User",
                "email": "newuser@example.com",
                "password": "securepass123",
                "role": "client",
                "phone": "+71234567890",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert isinstance(body["user_id"], int)

    def test_register_trainer_with_disciplines(self, client: TestClient, db: Session) -> None:
        """Trainer registration stores climbing disciplines/formats/levels."""
        response = client.post(
            "/api/auth/register",
            data={
                "name": "Coach",
                "email": "coach@example.com",
                "password": "securepass123",
                "role": "trainer",
                "disciplines": ["bouldering", "lead"],
                "work_formats": ["gym", "outdoor"],
                "student_levels": ["beginner"],
                "hourly_rate": 1500,
                "gym": "Скала Сити",
                "personal_grade": "7c+",
            },
        )
        assert response.status_code == 200
        from app.database import User
        u = db.query(User).filter(User.email == "coach@example.com").first()
        assert u is not None
        assert u.disciplines == ["bouldering", "lead"]
        assert u.work_formats == ["gym", "outdoor"]
        assert u.specialization == "bouldering"
        assert u.gym == "Скала Сити"
        assert u.personal_grade == "7c+"

    def test_register_duplicate_email(self, client: TestClient, test_client_user) -> None:
        response = client.post(
            "/api/auth/register",
            data={
                "name": "Another User",
                "email": test_client_user.email,
                "password": "securepass123",
                "role": "client",
            },
        )
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    def test_register_invalid_email(self, client: TestClient, db: Session) -> None:
        response = client.post(
            "/api/auth/register",
            data={
                "name": "Bad Email User",
                "email": "not-an-email",
                "password": "securepass123",
                "role": "client",
            },
        )
        assert response.status_code == 422

    def test_register_short_password(self, client: TestClient, db: Session) -> None:
        response = client.post(
            "/api/auth/register",
            data={
                "name": "Short Pass User",
                "email": "shortpass@example.com",
                "password": "12",
                "role": "client",
            },
        )
        assert response.status_code == 422

    def test_login_success(self, client: TestClient, test_client_user) -> None:
        response = client.post(
            "/api/auth/login",
            data={"email": test_client_user.email, "password": "password123"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["user"]["id"] == test_client_user.id
        assert body["user"]["role"] == "client"

    def test_forged_session_cookie_rejected(self, client: TestClient, test_client_user) -> None:
        """Plain or tampered user_id cookies must not authenticate anyone."""
        for forged in (str(test_client_user.id), "%d:badsignature" % test_client_user.id, "1:0000"):
            client.cookies.set("user_id", forged)
            response = client.get("/api/profile")
            assert response.status_code == 403

    def test_signed_session_cookie_accepted(self, client: TestClient, test_client_user) -> None:
        import app.main as app_main
        client.cookies.set("user_id", app_main.make_session_cookie(test_client_user.id))
        response = client.get("/api/profile")
        assert response.status_code == 200
        assert response.json()["id"] == test_client_user.id

    def test_login_wrong_password(self, client: TestClient, test_client_user) -> None:
        response = client.post(
            "/api/auth/login",
            data={"email": test_client_user.email, "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

    def test_login_rate_limit(self, client: TestClient, test_client_user) -> None:
        """6 rapid login attempts should trip the 5/min rate limit."""
        codes = []
        for _ in range(6):
            r = client.post("/api/auth/login", data={"email": test_client_user.email, "password": "password123"})
            codes.append(r.status_code)
        assert 429 in codes

    def test_logout(self, client: TestClient, test_client_user) -> None:
        response = client.post("/api/auth/logout")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_logout_get_page(self, client: TestClient) -> None:
        """The navbar /logout link must work via GET and redirect home."""
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 302


# ============================================================
# TRAINER TESTS
# ============================================================

class TestTrainer:
    """Tests for trainer browsing, filters and detail endpoints."""

    def test_trainer_list(self, client: TestClient, test_trainer) -> None:
        response = client.get("/trainers")
        assert response.status_code == 200
        assert test_trainer.name in response.text

    def test_trainer_list_filter_discipline(self, client: TestClient, test_trainer) -> None:
        response = client.get("/trainers?discipline=bouldering")
        assert response.status_code == 200
        assert test_trainer.name in response.text

        response = client.get("/trainers?discipline=speed")
        assert response.status_code == 200
        assert test_trainer.name not in response.text

    def test_trainer_list_filter_price(self, client: TestClient, test_trainer) -> None:
        # trainer hourly_rate = 100
        response = client.get("/trainers?price_min=50&price_max=150")
        assert test_trainer.name in response.text
        response = client.get("/trainers?price_min=200")
        assert test_trainer.name not in response.text

    def test_trainer_list_filter_format_and_level(self, client: TestClient, test_trainer) -> None:
        response = client.get("/trainers?format=gym")
        assert test_trainer.name in response.text
        response = client.get("/trainers?format=outdoor")
        assert test_trainer.name not in response.text
        response = client.get("/trainers?level=beginner")
        assert test_trainer.name in response.text
        response = client.get("/trainers?level=competition")
        assert test_trainer.name not in response.text

    def test_trainer_list_search(self, client: TestClient, test_trainer) -> None:
        response = client.get("/trainers?q=bouldering")
        assert test_trainer.name in response.text
        response = client.get("/trainers?q=nonexistentquery")
        assert test_trainer.name not in response.text

    def test_trainer_detail(self, client: TestClient, test_trainer) -> None:
        response = client.get(f"/trainer/{test_trainer.id}")
        assert response.status_code == 200
        assert test_trainer.name in response.text
        assert "Боулдеринг" in response.text  # discipline label rendered

    def test_trainer_detail_404(self, client: TestClient) -> None:
        response = client.get("/trainer/99999")
        assert response.status_code == 404


# ============================================================
# SHOWCASE TESTS
# ============================================================

class TestShowcase:
    """Tests for the trainer showcase (витрина/анкета) editing."""

    def test_showcase_page_requires_trainer(self, client: TestClient, test_client_user) -> None:
        _authenticate_client(client, test_client_user.id)
        response = client.get("/showcase", follow_redirects=False)
        assert response.status_code == 302  # clients are redirected away

    def test_showcase_page_trainer(self, client: TestClient, test_trainer) -> None:
        _authenticate_client(client, test_trainer.id)
        response = client.get("/showcase")
        assert response.status_code == 200
        assert "Моя анкета" in response.text

    def test_update_showcase(self, client: TestClient, test_trainer, db: Session) -> None:
        _authenticate_client(client, test_trainer.id)
        response = client.post(
            "/api/showcase",
            data={
                "name": "Updated Coach",
                "bio": "Новый био",
                "disciplines": ["trad", "multipitch"],
                "work_formats": ["outdoor"],
                "student_levels": ["advanced"],
                "personal_grade": "8a",
                "gym": "BigWall",
                "achievements_text": "Первопроход 8a",
                "hourly_rate": 2500,
            },
        )
        assert response.status_code == 200
        db.refresh(test_trainer)
        assert test_trainer.name == "Updated Coach"
        assert test_trainer.disciplines == ["trad", "multipitch"]
        assert test_trainer.specialization == "trad"
        assert test_trainer.personal_grade == "8a"
        assert test_trainer.hourly_rate == 2500

    def test_update_showcase_forbidden_for_client(self, client: TestClient, test_client_user) -> None:
        _authenticate_client(client, test_client_user.id)
        response = client.post("/api/showcase", data={"bio": "hack"})
        assert response.status_code == 403


# ============================================================
# BOOKING TESTS
# ============================================================

class TestBooking:
    """Tests for booking creation and completion."""

    def test_create_booking(self, client: TestClient, test_client_user, test_trainer, db: Session) -> None:
        _authenticate_client(client, test_client_user.id)
        response = client.post(
            "/api/bookings",
            data={
                "trainer_id": test_trainer.id,
                "booking_type": "single",
                "scheduled_at": "2026-08-01T10:00:00",
                "notes": "Test booking",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert isinstance(body["booking_id"], int)
        assert body["amount"] > 0
        # Cashback must be credited (regression: py3.7 fromisocalendar crash
        # used to 500 after the wallet charge)
        assert body["cashback"] > 0

    def test_create_booking_insufficient_funds(
        self, client: TestClient, test_client_user, test_trainer, db: Session
    ) -> None:
        test_client_user.wallet_balance = 0.00
        test_client_user.wallet_bonus = 0.00
        db.commit()
        _authenticate_client(client, test_client_user.id)
        response = client.post(
            "/api/bookings",
            data={
                "trainer_id": test_trainer.id,
                "booking_type": "single",
                "scheduled_at": "2026-08-01T10:00:00",
                "notes": "Should fail",
            },
        )
        assert response.status_code == 400
        assert "insufficient" in response.json()["detail"].lower()

    def test_complete_booking(self, client: TestClient, test_client_user, test_trainer, db: Session) -> None:
        _authenticate_client(client, test_client_user.id)
        from datetime import datetime
        from app.database import Booking

        booking = Booking(
            client_id=test_client_user.id,
            trainer_id=test_trainer.id,
            status="confirmed",
            booking_type="single",
            sessions_total=1,
            sessions_used=0,
            amount=100.00,
            platform_fee=20.00,
            scheduled_at=datetime(2026, 8, 1, 10, 0, 0),
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        trainer_balance_before = float(test_trainer.wallet_balance)

        response = client.post(f"/api/bookings/{booking.id}/complete")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["trainer_amount"] == 80.00

        db.refresh(test_trainer)
        assert float(test_trainer.wallet_balance) == trainer_balance_before + 80.00

    def test_booking_has_zero_fee(self, client: TestClient, test_client_user, test_trainer, db: Session) -> None:
        """No commission on trainer services: new bookings always have platform_fee = 0."""
        _authenticate_client(client, test_client_user.id)
        response = client.post(
            "/api/bookings",
            data={
                "trainer_id": test_trainer.id,
                "booking_type": "single",
                "scheduled_at": "2026-08-01T10:00:00",
            },
        )
        assert response.status_code == 200
        from app.database import Booking
        b = db.query(Booking).filter(Booking.id == response.json()["booking_id"]).first()
        assert float(b.platform_fee) == 0.0

    def test_booking_blocked_without_placement(self, client: TestClient, test_client_user, test_trainer, db: Session) -> None:
        test_trainer.showcase_until = None
        db.commit()
        _authenticate_client(client, test_client_user.id)
        response = client.post(
            "/api/bookings",
            data={
                "trainer_id": test_trainer.id,
                "booking_type": "single",
                "scheduled_at": "2026-08-01T10:00:00",
            },
        )
        assert response.status_code == 400

    def test_trainer_hidden_without_placement(self, client: TestClient, test_trainer, db: Session) -> None:
        # Fixture trainer has an active placement and is listed
        assert "Test Trainer" in client.get("/trainers").text
        test_trainer.showcase_until = None
        db.commit()
        assert "Test Trainer" not in client.get("/trainers").text

    def test_buy_placement(self, client: TestClient, test_trainer, db: Session) -> None:
        from datetime import datetime
        test_trainer.showcase_until = None
        test_trainer.wallet_balance = 1000.00
        db.commit()
        _authenticate_client(client, test_trainer.id)
        response = client.post("/api/showcase/placement")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["price"] == 990.0

        db.refresh(test_trainer)
        assert test_trainer.showcase_until is not None
        assert test_trainer.showcase_until > datetime.utcnow()
        assert float(test_trainer.wallet_balance) == 10.00  # 1000 - 990
        # Trainer is back in the catalog
        assert "Test Trainer" in client.get("/trainers").text

    def test_buy_placement_insufficient_funds(self, client: TestClient, test_trainer, db: Session) -> None:
        test_trainer.wallet_balance = 100.00
        test_trainer.wallet_bonus = 0.00
        db.commit()
        _authenticate_client(client, test_trainer.id)
        response = client.post("/api/showcase/placement")
        assert response.status_code == 400

    def test_buy_placement_extends_existing(self, client: TestClient, test_trainer, db: Session) -> None:
        # Fixture placement is +30 days; buying again must extend it, not reset
        test_trainer.wallet_balance = 1000.00
        db.commit()
        _authenticate_client(client, test_trainer.id)
        before = test_trainer.showcase_until
        response = client.post("/api/showcase/placement")
        assert response.status_code == 200
        db.refresh(test_trainer)
        assert test_trainer.showcase_until > before

    def test_autorenew_toggle(self, client: TestClient, test_trainer, db: Session) -> None:
        _authenticate_client(client, test_trainer.id)
        response = client.post("/api/showcase/autorenew")
        assert response.status_code == 200
        assert response.json()["autorenew"] is True
        db.refresh(test_trainer)
        assert test_trainer.showcase_autorenew is True

        response = client.post("/api/showcase/autorenew")
        assert response.json()["autorenew"] is False
        db.refresh(test_trainer)
        assert test_trainer.showcase_autorenew is False

    def test_autorenew_lazy_renewal(self, client: TestClient, test_trainer, db: Session) -> None:
        """Opted-in trainer with a lapsed placement is auto-charged on dashboard visit."""
        test_trainer.showcase_until = None
        test_trainer.showcase_autorenew = True
        test_trainer.wallet_balance = 2000.00
        db.commit()
        _authenticate_client(client, test_trainer.id)
        response = client.get("/dashboard")
        assert response.status_code == 200

        db.refresh(test_trainer)
        assert test_trainer.showcase_until is not None
        assert float(test_trainer.wallet_balance) == 2000.00 - 990.0
        # Back in the catalog
        assert "Test Trainer" in client.get("/trainers").text

    def test_autorenew_lazy_renewal_no_funds(self, client: TestClient, test_trainer, db: Session) -> None:
        """Auto-renewal silently skips when the wallet cannot cover the price."""
        test_trainer.showcase_until = None
        test_trainer.showcase_autorenew = True
        test_trainer.wallet_balance = 10.00
        test_trainer.wallet_bonus = 0.00
        db.commit()
        _authenticate_client(client, test_trainer.id)
        response = client.get("/dashboard")
        assert response.status_code == 200

        db.refresh(test_trainer)
        assert test_trainer.showcase_until is None
        assert float(test_trainer.wallet_balance) == 10.00

    def test_expiring_soon_banner(self, client: TestClient, test_trainer, db: Session) -> None:
        from datetime import datetime, timedelta
        test_trainer.showcase_until = datetime.utcnow() + timedelta(days=2)
        db.commit()
        _authenticate_client(client, test_trainer.id)
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "истекает через" in response.text


# ============================================================
# WALLET TESTS
# ============================================================

class TestWallet:
    """Tests for wallet operations."""

    def test_deposit(self, client: TestClient, test_client_user, db: Session) -> None:
        _authenticate_client(client, test_client_user.id)
        initial_balance = float(test_client_user.wallet_balance)
        response = client.post("/api/wallet/deposit", data={"amount": 250.00})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["new_balance"] == initial_balance + 250.00

    def test_wallet_page(self, client: TestClient, test_client_user) -> None:
        _authenticate_client(client, test_client_user.id)
        response = client.get("/wallet")
        assert response.status_code == 200
        assert "Мой кошелек" in response.text
        assert "500" in response.text


# ============================================================
# CHAT TESTS
# ============================================================

class TestChat:
    """Tests for messaging endpoints."""

    def test_send_message(self, client: TestClient, test_client_user, test_trainer, db: Session) -> None:
        _authenticate_client(client, test_client_user.id)
        response = client.post(
            "/api/messages",
            data={"receiver_id": test_trainer.id, "content": "Hello, когда ближайшая тренировка?"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "warning" not in body

    def test_send_message_with_contact(self, client: TestClient, test_client_user, test_trainer, db: Session) -> None:
        _authenticate_client(client, test_client_user.id)
        response = client.post(
            "/api/messages",
            data={"receiver_id": test_trainer.id, "content": "Call me at +79161234567"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "warning" in body

    def test_get_messages(self, client: TestClient, test_client_user, test_trainer, db: Session) -> None:
        from app.database import Message
        msg = Message(
            sender_id=test_client_user.id,
            receiver_id=test_trainer.id,
            content="Test message content",
            has_contact_info=False,
        )
        db.add(msg)
        db.commit()
        _authenticate_client(client, test_client_user.id)
        response = client.get(f"/api/messages/{test_trainer.id}")
        assert response.status_code == 200
        messages = response.json()
        assert isinstance(messages, list)
        assert len(messages) >= 1
        assert messages[0]["content"] == "Test message content"


# ============================================================
# REVIEW TESTS
# ============================================================

class TestReview:
    """Tests for review creation."""

    def test_post_review(self, client: TestClient, test_client_user, test_trainer, db: Session) -> None:
        from datetime import datetime
        from app.database import Booking

        booking = Booking(
            client_id=test_client_user.id,
            trainer_id=test_trainer.id,
            status="confirmed",
            booking_type="single",
            sessions_total=1,
            sessions_used=0,
            amount=100.00,
            platform_fee=20.00,
            scheduled_at=datetime(2026, 8, 1, 10, 0, 0),
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        _authenticate_client(client, test_client_user.id)
        response = client.post(
            "/api/reviews",
            data={
                "booking_id": booking.id,
                "rating": 5,
                "professionalism": 5,
                "punctuality": 5,
                "effectiveness": 5,
                "comment": "Отличная тренировка по боулдерингу!",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert isinstance(body["review_id"], int)


# ============================================================
# RECOMMENDATION TESTS
# ============================================================

class TestRecommendations:
    """Tests for the recommendation engine endpoint."""

    def test_recommendations(self, client: TestClient, test_trainer) -> None:
        response = client.get("/api/recommendations")
        assert response.status_code == 200
        trainers = response.json()
        assert isinstance(trainers, list)
        assert len(trainers) > 0
        for t in trainers:
            assert "id" in t
            assert "name" in t
            assert "specialization" in t
            assert "hourly_rate" in t
            assert "rating" in t
            assert "disciplines" in t

    def test_recommendations_match_preferred_discipline(
        self, client: TestClient, test_client_user, test_trainer
    ) -> None:
        """Client prefers bouldering; the bouldering trainer should surface."""
        _authenticate_client(client, test_client_user.id)
        response = client.get("/api/recommendations")
        assert response.status_code == 200
        trainers = response.json()
        assert len(trainers) > 0
        assert trainers[0]["id"] == test_trainer.id
        assert "bouldering" in trainers[0]["disciplines"]


# ============================================================
# MARKETPLACE TESTS
# ============================================================

class TestMarket:
    """Tests for the gear marketplace (Lolz-style lots, direct deals, progressive fee)."""

    def test_market_page(self, client: TestClient, test_product) -> None:
        response = client.get("/market")
        assert response.status_code == 200
        assert test_product.title in response.text

    def test_market_filter_category(self, client: TestClient, test_product) -> None:
        response = client.get("/market?category=shoes")
        assert test_product.title in response.text
        response = client.get("/market?category=ropes")
        assert test_product.title not in response.text

    def test_market_filter_price_and_search(self, client: TestClient, test_product) -> None:
        response = client.get("/market?price_min=50&price_max=150")
        assert test_product.title in response.text
        response = client.get("/market?price_min=200")
        assert test_product.title not in response.text
        response = client.get("/market?q=Sportiva")
        assert test_product.title in response.text
        response = client.get("/market?q=zzzznothing")
        assert test_product.title not in response.text

    def test_create_product(self, client: TestClient, test_client_user, db: Session) -> None:
        _authenticate_client(client, test_client_user.id)
        response = client.post(
            "/api/market/products",
            data={
                "title": "Крашпад тестовый",
                "category": "crashpads",
                "condition": "like_new",
                "price": 9000,
                "brand": "Ocun",
                "city": "Москва",
                "description": "Почти новый мат",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        from app.database import Product
        p = db.query(Product).filter(Product.id == body["product_id"]).first()
        assert p is not None
        assert p.status == "active"
        assert p.seller_id == test_client_user.id

    def test_create_product_with_image(self, client: TestClient, test_client_user, db: Session) -> None:
        _authenticate_client(client, test_client_user.id)
        response = client.post(
            "/api/market/products",
            data={
                "title": "Верёвка тестовая 60м",
                "category": "ropes",
                "condition": "good",
                "price": 5000,
            },
            files={"image": ("rope.jpg", b"\xff\xd8\xff\xe0" + b"0" * 100, "image/jpeg")},
        )
        assert response.status_code == 200
        from app.database import Product
        p = db.query(Product).filter(Product.id == response.json()["product_id"]).first()
        assert p.image.startswith("uploads/")

    def test_create_product_validation(self, client: TestClient, test_client_user) -> None:
        _authenticate_client(client, test_client_user.id)
        # Bad category
        response = client.post(
            "/api/market/products",
            data={"title": "Невалид", "category": "nope", "price": 100},
        )
        assert response.status_code == 422
        # Negative price
        response = client.post(
            "/api/market/products",
            data={"title": "Невалид", "category": "shoes", "price": -5},
        )
        assert response.status_code == 422
        # Unauthenticated
    def test_create_product_unauthenticated(self, client: TestClient) -> None:
        response = client.post(
            "/api/market/products",
            data={"title": "Без авторизации", "category": "shoes", "price": 100},
        )
        assert response.status_code == 403

    def test_product_detail_and_views(self, client: TestClient, test_product, db: Session) -> None:
        views_before = test_product.views or 0
        response = client.get(f"/market/{test_product.id}")
        assert response.status_code == 200
        assert test_product.title in response.text
        db.refresh(test_product)
        assert test_product.views == views_before + 1

    def test_product_detail_404(self, client: TestClient) -> None:
        response = client.get("/market/99999")
        assert response.status_code == 404

    def test_buy_completes_directly(self, client: TestClient, test_client_user, test_trainer, test_product, db: Session) -> None:
        _authenticate_client(client, test_client_user.id)
        balance_before = float(test_client_user.wallet_balance)
        seller_before = float(test_trainer.wallet_balance)
        response = client.post(f"/api/market/products/{test_product.id}/buy")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

        db.refresh(test_client_user)
        db.refresh(test_product)
        db.refresh(test_trainer)
        assert float(test_client_user.wallet_balance) == balance_before - 100.00
        assert test_product.status == "sold"
        # Promo: the seller's first sales are commission-free — full amount credited
        assert float(test_trainer.wallet_balance) == seller_before + 100.00
        assert test_trainer.seller_sales == 1

        from app.database import MarketOrder
        order = db.query(MarketOrder).filter(MarketOrder.id == body["order_id"]).first()
        assert order.status == "completed"
        assert float(order.fee) == 0.00

    def test_buy_progressive_fee(self, client: TestClient, test_client_user, test_trainer, test_product, db: Session) -> None:
        # 10 completed sales -> 6% commission tier
        test_trainer.seller_sales = 10
        db.commit()
        _authenticate_client(client, test_client_user.id)
        seller_before = float(test_trainer.wallet_balance)
        response = client.post(f"/api/market/products/{test_product.id}/buy")
        assert response.status_code == 200
        body = response.json()
        assert body["fee"] == 6.00
        assert body["seller_amount"] == 94.00

        db.refresh(test_trainer)
        assert float(test_trainer.wallet_balance) == seller_before + 94.00
        assert test_trainer.seller_sales == 11

    def test_market_fee_rate_tiers(self) -> None:
        from app.climbing import market_fee_rate
        assert market_fee_rate(0) == 0.0  # promo: first 3 sales are free
        assert market_fee_rate(2) == 0.0
        assert market_fee_rate(3) == 0.08
        assert market_fee_rate(9) == 0.08
        assert market_fee_rate(10) == 0.06
        assert market_fee_rate(29) == 0.06
        assert market_fee_rate(30) == 0.05
        assert market_fee_rate(99) == 0.05
        assert market_fee_rate(100) == 0.04
        assert market_fee_rate(500) == 0.04

    def test_buy_own_product_forbidden(self, client: TestClient, test_trainer, test_product) -> None:
        _authenticate_client(client, test_trainer.id)
        response = client.post(f"/api/market/products/{test_product.id}/buy")
        assert response.status_code == 400

    def test_buy_insufficient_funds(self, client: TestClient, test_client_user, test_product, db: Session) -> None:
        test_client_user.wallet_balance = 10.00
        test_client_user.wallet_bonus = 0.00
        db.commit()
        _authenticate_client(client, test_client_user.id)
        response = client.post(f"/api/market/products/{test_product.id}/buy")
        assert response.status_code == 400

    def _make_direct_order(self, client, test_client_user, test_product, db):
        _authenticate_client(client, test_client_user.id)
        response = client.post(f"/api/market/products/{test_product.id}/buy")
        assert response.status_code == 200
        return response.json()["order_id"]

    def test_confirm_not_needed_for_direct_order(self, client: TestClient, test_client_user, test_product, db: Session) -> None:
        order_id = self._make_direct_order(client, test_client_user, test_product, db)
        # Money is transferred at purchase time — there is nothing to confirm
        response = client.post(f"/api/market/orders/{order_id}/confirm")
        assert response.status_code == 400

    def test_cancel_not_possible_for_direct_order(self, client: TestClient, test_client_user, test_product, db: Session) -> None:
        order_id = self._make_direct_order(client, test_client_user, test_product, db)
        response = client.post(f"/api/market/orders/{order_id}/cancel")
        assert response.status_code == 400

        db.refresh(test_product)
        assert test_product.status == "sold"  # lot stays sold

    def test_seller_review_flow(self, client: TestClient, test_client_user, test_trainer, test_product, db: Session) -> None:
        order_id = self._make_direct_order(client, test_client_user, test_product, db)

        response = client.post(f"/api/market/orders/{order_id}/review", data={"rating": 5, "comment": "Всё отлично!"})
        assert response.status_code == 200

        db.refresh(test_trainer)
        assert test_trainer.seller_rating == 5.0
        assert test_trainer.seller_reviews_total == 1

        # Duplicate review is rejected
        response = client.post(f"/api/market/orders/{order_id}/review", data={"rating": 1})
        assert response.status_code == 409

    def test_review_before_complete_rejected(self, client: TestClient, test_client_user, test_trainer, test_product, db: Session) -> None:
        # Legacy escrow-style order that is not completed yet cannot be reviewed
        from app.database import MarketOrder
        order = MarketOrder(
            product_id=test_product.id, buyer_id=test_client_user.id,
            seller_id=test_trainer.id, amount=100, fee=0, status="escrow",
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        _authenticate_client(client, test_client_user.id)
        response = client.post(f"/api/market/orders/{order.id}/review", data={"rating": 5})
        assert response.status_code == 400

    def test_archive_product(self, client: TestClient, test_trainer, test_product, db: Session) -> None:
        _authenticate_client(client, test_trainer.id)
        response = client.post(f"/api/market/products/{test_product.id}/archive")
        assert response.status_code == 200
        db.refresh(test_product)
        assert test_product.status == "archived"
        # Archived lot is hidden from the catalog
        response = client.get("/market")
        assert test_product.title not in response.text

    def test_archive_not_own_product(self, client: TestClient, test_client_user, test_product) -> None:
        _authenticate_client(client, test_client_user.id)
        response = client.post(f"/api/market/products/{test_product.id}/archive")
        assert response.status_code == 403

    def test_seller_page(self, client: TestClient, test_trainer, test_product) -> None:
        response = client.get(f"/seller/{test_trainer.id}")
        assert response.status_code == 200
        assert test_trainer.name in response.text
        assert test_product.title in response.text

    def test_market_new_page(self, client: TestClient, test_client_user) -> None:
        _authenticate_client(client, test_client_user.id)
        response = client.get("/market/new")
        assert response.status_code == 200
        assert "Разместить лот" in response.text


# ============================================================
# STATIC PAGE TESTS
# ============================================================

class TestPages:
    """All public pages should render."""

    def test_home(self, client: TestClient, test_trainer) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "ClimbConnect" in response.text

    def test_about(self, client: TestClient) -> None:
        response = client.get("/about")
        assert response.status_code == 200
        assert "прямые сделки" in response.text

    def test_support(self, client: TestClient) -> None:
        response = client.get("/support")
        assert response.status_code == 200

    def test_register_page(self, client: TestClient) -> None:
        response = client.get("/register")
        assert response.status_code == 200
        assert "Боулдеринг" in response.text

    def test_login_page(self, client: TestClient) -> None:
        response = client.get("/login")
        assert response.status_code == 200

    def test_stats(self, client: TestClient, test_trainer, test_product) -> None:
        response = client.get("/api/stats")
        assert response.status_code == 200
        body = response.json()
        assert "total_trainers" in body
        assert "total_products" in body
        assert body["total_products"] >= 1
