"""Pytest configuration and shared fixtures for ClimbConnect tests."""

import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Ensure the app package is importable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.database import Base, get_db, User, Booking, Review, WalletTransaction, Message, ActivityLog, Product, MarketOrder, MarketReview  # noqa: E402
from app.main import app  # noqa: E402
import app.main as app_main  # noqa: E402

# File-based SQLite so endpoints and test code share the same DB
TEST_DB_FILE = "/tmp/test_trainer_marketplace.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _reset_database():
    """Drop all tables and recreate them."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


# Initialize once at import time
_reset_database()


def _override_get_db():
    """Yield a fresh session per request, then close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Replace the app's DB dependency with our test DB
app.dependency_overrides[get_db] = _override_get_db


def _authenticate_client(client: TestClient, user_id: int) -> None:
    """Set the user_id cookie directly on the TestClient."""
    client.cookies.set("user_id", str(user_id))


@pytest.fixture(scope="function")
def db():
    """Provide a database session with a clean DB for each test."""
    _reset_database()
    # Reset the in-memory rate limiter so auth endpoints stay usable in tests
    app_main._rate_limit_store.clear()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient that shares the same database session."""
    def _get_db_override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override

    with TestClient(app) as c:
        yield c

    app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def test_trainer(db):
    """Create and return a climbing trainer in the test database."""
    from passlib.hash import pbkdf2_sha256
    trainer = User(
        name="Test Trainer",
        email="trainer@test.com",
        password_hash=pbkdf2_sha256.hash("password123"),
        role="trainer",
        specialization="bouldering",
        disciplines=["bouldering", "lead"],
        work_formats=["gym"],
        student_levels=["beginner", "intermediate"],
        hourly_rate=100,
        experience_years=5,
        rating=4.5,
        total_reviews=10,
        verification_level=2,
        bio="Experienced bouldering coach",
        location="Москва",
        gym="Скала Сити",
        personal_grade="V8",
        status="active",
        wallet_balance=0.00,
        sliding_commission_rate=0.20,
    )
    db.add(trainer)
    db.commit()
    db.refresh(trainer)
    return trainer


@pytest.fixture
def test_client_user(db):
    """Create and return a client user in the test database."""
    from passlib.hash import pbkdf2_sha256
    user = User(
        name="Test Client",
        email="client@test.com",
        password_hash=pbkdf2_sha256.hash("password123"),
        role="client",
        wallet_balance=500.00,
        wallet_bonus=0.00,
        preferred_sport="bouldering",
        fitness_goal="learn_basics",
        experience_level="beginner",
        budget_max=5000,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_product(db, test_trainer):
    """Create and return an active marketplace listing sold by test_trainer."""
    product = Product(
        seller_id=test_trainer.id,
        title="Скальные туфли Test, 42",
        category="shoes",
        brand="La Sportiva",
        size="EU 42",
        condition="good",
        price=100.00,
        description="Test listing",
        city="Москва",
        status="active",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product
