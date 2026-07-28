"""Database models for ClimbConnect (climbing trainer & gear marketplace)"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, JSON, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "trainer_marketplace.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20))
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), default="client")
    created_at = Column(DateTime, default=datetime.utcnow)
    fitness_goal = Column(String(50))
    experience_level = Column(String(20))
    preferred_sport = Column(String(50))
    location = Column(String(100))
    budget_min = Column(Integer, default=0)
    budget_max = Column(Integer, default=5000)
    bio = Column(Text)
    specialization = Column(String(50))
    experience_years = Column(Integer, default=0)
    certification = Column(String(200))
    hourly_rate = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    total_bookings = Column(Integer, default=0)
    verification_level = Column(Integer, default=0)
    status = Column(String(20), default="active")
    wallet_balance = Column(Numeric(10, 2), default=0.00)
    wallet_bonus = Column(Numeric(10, 2), default=0.00)
    sliding_commission_rate = Column(Float, default=0.20)
    total_earnings = Column(Numeric(10, 2), default=0.00)
    trust_score = Column(Integer, default=100)
    streak_weeks = Column(Integer, default=0)
    achievements = Column(JSON, default=list)
    loyalty_points = Column(Integer, default=0)
    client_level = Column(String(20), default="beginner")
    interests_vector = Column(JSON, default=dict)
    # --- Climbing showcase (trainer profile) ---
    disciplines = Column(JSON, default=list)        # ["bouldering", "lead", ...]
    work_formats = Column(JSON, default=list)       # ["gym", "outdoor", "online"]
    student_levels = Column(JSON, default=list)     # ["beginner", ...]
    gym = Column(String(150))                       # home climbing gym / wall
    personal_grade = Column(String(30))             # e.g. "7c+ / V9"
    achievements_text = Column(Text)                # comps, routes, medals
    showcase_image = Column(String(200))            # custom showcase photo path
    # --- Seller stats (marketplace) ---
    seller_rating = Column(Float, default=0.0)
    seller_reviews_total = Column(Integer, default=0)
    seller_sales = Column(Integer, default=0)

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"))
    trainer_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(20), default="pending")
    booking_type = Column(String(20), default="single")
    sessions_total = Column(Integer, default=1)
    sessions_used = Column(Integer, default=0)
    amount = Column(Numeric(10, 2), default=0.00)
    platform_fee = Column(Numeric(10, 2), default=0.00)
    scheduled_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    client_id = Column(Integer, ForeignKey("users.id"))
    trainer_id = Column(Integer, ForeignKey("users.id"))
    rating = Column(Integer, default=5)
    professionalism = Column(Integer, default=5)
    punctuality = Column(Integer, default=5)
    effectiveness = Column(Integer, default=5)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified = Column(Boolean, default=True)

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String(20))
    amount = Column(Numeric(10, 2))
    balance_after = Column(Numeric(10, 2))
    description = Column(String(200))
    reference_id = Column(Integer)
    status = Column(String(20), default="completed")
    created_at = Column(DateTime, default=datetime.utcnow)

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(50))
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text)
    has_contact_info = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# ============================================================
# MARKETPLACE MODELS
# ============================================================

class Product(Base):
    """A marketplace listing for climbing gear (Lolz-style lot)."""
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(150), nullable=False)
    category = Column(String(40), nullable=False)
    brand = Column(String(80))
    size = Column(String(40))
    condition = Column(String(20), default="good")
    price = Column(Numeric(10, 2), nullable=False)
    description = Column(Text)
    image = Column(String(200))            # /uploads/xxx.jpg (under static/)
    city = Column(String(100))
    status = Column(String(20), default="active")   # active | sold | archived
    views = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class MarketOrder(Base):
    """Escrow-style purchase: funds are held until the buyer confirms receipt."""
    __tablename__ = "market_orders"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    buyer_id = Column(Integer, ForeignKey("users.id"))
    seller_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Numeric(10, 2), nullable=False)
    fee = Column(Numeric(10, 2), default=0.00)
    status = Column(String(20), default="escrow")   # escrow | completed | refunded
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class MarketReview(Base):
    """Buyer feedback about a seller after a completed order."""
    __tablename__ = "market_reviews"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("market_orders.id"))
    buyer_id = Column(Integer, ForeignKey("users.id"))
    seller_id = Column(Integer, ForeignKey("users.id"))
    rating = Column(Integer, default=5)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
    migrate_db()

def migrate_db():
    """Lightweight SQLite migration: add missing columns to existing tables."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("users")}
    new_columns = {
        "disciplines": "JSON",
        "work_formats": "JSON",
        "student_levels": "JSON",
        "gym": "VARCHAR(150)",
        "personal_grade": "VARCHAR(30)",
        "achievements_text": "TEXT",
        "showcase_image": "VARCHAR(200)",
        "seller_rating": "FLOAT DEFAULT 0",
        "seller_reviews_total": "INTEGER DEFAULT 0",
        "seller_sales": "INTEGER DEFAULT 0",
    }
    with engine.connect() as conn:
        for col, coltype in new_columns.items():
            if col not in existing:
                conn.execute(text("ALTER TABLE users ADD COLUMN %s %s" % (col, coltype)))
        conn.commit()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
