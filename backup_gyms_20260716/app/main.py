"""ClimbConnect — climbing trainers & gear marketplace. FastAPI backend."""
from fastapi import FastAPI, Depends, HTTPException, Request, Form, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from passlib.hash import pbkdf2_sha256
from datetime import datetime, timedelta, date
from functools import wraps
import os
import re
import html
import uuid
from typing import Dict, List, Tuple, Optional

from app.database import (
    init_db, get_db, User, Booking, Review, WalletTransaction,
    ActivityLog, Message, Product, MarketOrder, MarketReview,
)
from app.recommendation import get_recommendation_engine
from app.climbing import (
    DISCIPLINES, DISCIPLINE_KEYS, GOALS, FORMATS, LEVELS,
    GEAR_CATEGORIES, CONDITIONS, MARKET_FEE_RATE, CITIES,
    discipline_name, category_name, condition_name,
)

# ============================================================
# CONSTANTS & VALIDATION
# ============================================================

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
MIN_PASSWORD_LENGTH = 6
MAX_NAME_LENGTH = 100
RATE_LIMIT_WINDOW = 60  # seconds
MAX_REQUESTS_PER_WINDOW = 5
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE = 8 * 1024 * 1024  # 8 MB

# In-memory rate limit store: {ip_address: [(timestamp, count), ...]}
_rate_limit_store: Dict[str, List[Tuple[float, int]]] = {}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "..", "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="ClimbConnect", version="2.0.0")

# Static & Templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "..", "templates"))

# Jinja globals/filters for climbing domain
templates.env.globals["DISCIPLINES"] = DISCIPLINES
templates.env.globals["GOALS"] = GOALS
templates.env.globals["FORMATS"] = FORMATS
templates.env.globals["LEVELS"] = LEVELS
templates.env.globals["GEAR_CATEGORIES"] = GEAR_CATEGORIES
templates.env.globals["CONDITIONS"] = CONDITIONS
templates.env.globals["CITIES"] = CITIES
templates.env.globals["discipline_name"] = discipline_name
templates.env.globals["category_name"] = category_name
templates.env.globals["condition_name"] = condition_name

# Init DB
init_db()

# ============================================================
# AUTH
# ============================================================

def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)

def verify_password(password: str, hash: str) -> bool:
    return pbkdf2_sha256.verify(password, hash)

def validate_email(email: str) -> bool:
    """Validate email format using regex."""
    return bool(EMAIL_REGEX.match(email))

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS attacks."""
    if not text:
        return ""
    return html.escape(text.strip())

def rate_limit(max_requests: int = MAX_REQUESTS_PER_WINDOW, window: int = RATE_LIMIT_WINDOW):
    """Rate limiting decorator: limit requests per IP within a time window."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Optional[Request] = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                for v in kwargs.values():
                    if isinstance(v, Request):
                        request = v
                        break

            if request is not None:
                client_ip = request.client.host if request.client else "unknown"
                now = datetime.utcnow().timestamp()

                _rate_limit_store[client_ip] = [
                    (ts, cnt) for ts, cnt in _rate_limit_store.get(client_ip, [])
                    if now - ts < window
                ]

                request_count = sum(cnt for _, cnt in _rate_limit_store.get(client_ip, []))
                if request_count >= max_requests:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. Try again in {window} seconds."
                    )

                _rate_limit_store.setdefault(client_ip, []).append((now, 1))

            return await func(*args, **kwargs)
        return wrapper
    return decorator

def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Get the current authenticated user from cookies, or None if not authenticated."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        return None
    try:
        return db.query(User).filter(User.id == user_id_int).first()
    except SQLAlchemyError:
        return None

def _trainer_primary_discipline(trainer: User) -> str:
    """Primary discipline key used for imagery: explicit specialization wins,
    otherwise the first of the trainer's disciplines list."""
    if trainer.specialization and trainer.specialization in DISCIPLINES:
        return trainer.specialization
    discs = trainer.disciplines or []
    for d in discs:
        if d in DISCIPLINES:
            return d
    return "bouldering"

templates.env.globals["primary_discipline"] = _trainer_primary_discipline

# ============================================================
# PAGES
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    trainers = db.query(User).filter(User.role == "trainer", User.status == "active").order_by(User.rating.desc()).limit(8).all()
    latest_products = db.query(Product).filter(Product.status == "active").order_by(Product.created_at.desc()).limit(6).all()
    total_clients = db.query(User).filter(User.role == "client").count()
    total_bookings = db.query(Booking).count()
    total_products = db.query(Product).filter(Product.status == "active").count()

    rec_trainers = []
    if user and user.role == "client":
        engine = get_recommendation_engine(db)
        rec_trainers = engine.get_recommendations_for_user(user.id, limit=4)

    return templates.TemplateResponse("index.html", {
        "request": request, "user": user, "trainers": trainers,
        "rec_trainers": rec_trainers, "latest_products": latest_products,
        "total_clients": total_clients, "total_bookings": total_bookings,
        "total_products": total_products,
    })

@app.get("/trainers", response_class=HTMLResponse)
async def trainer_list(
    request: Request,
    discipline: str = None, format: str = None, level: str = None,
    city: str = None, price_min: int = None, price_max: int = None,
    exp_min: int = None, rating_min: float = None,
    q: str = None, sort: str = "rating",
    db: Session = Depends(get_db),
):
    """Trainer catalog with rich climbing-specific filters."""
    user = get_current_user(request, db)
    query = db.query(User).filter(User.role == "trainer", User.status == "active")

    if price_min is not None:
        query = query.filter(User.hourly_rate >= price_min)
    if price_max is not None:
        query = query.filter(User.hourly_rate <= price_max)
    if exp_min is not None:
        query = query.filter(User.experience_years >= exp_min)
    if rating_min is not None:
        query = query.filter(User.rating >= rating_min)
    if city:
        query = query.filter(User.location.ilike(f"%{city}%"))
    if q:
        query = query.filter(or_(User.name.ilike(f"%{q}%"), User.bio.ilike(f"%{q}%")))

    trainers = query.all()

    # JSON-array filters (disciplines / formats / levels) in Python — small tables
    if discipline:
        trainers = [t for t in trainers if discipline in (t.disciplines or []) or t.specialization == discipline]
    if format:
        trainers = [t for t in trainers if format in (t.work_formats or [])]
    if level:
        trainers = [t for t in trainers if level in (t.student_levels or [])]

    if sort == "price_asc":
        trainers.sort(key=lambda t: (t.hourly_rate or 0))
    elif sort == "price_desc":
        trainers.sort(key=lambda t: -(t.hourly_rate or 0))
    elif sort == "experience":
        trainers.sort(key=lambda t: -(t.experience_years or 0))
    else:
        trainers.sort(key=lambda t: -(t.rating or 0))

    filters = {
        "discipline": discipline, "format": format, "level": level, "city": city,
        "price_min": price_min, "price_max": price_max, "exp_min": exp_min,
        "rating_min": rating_min, "q": q, "sort": sort,
    }
    return templates.TemplateResponse("trainers.html", {
        "request": request, "user": user, "trainers": trainers, "filters": filters,
    })

@app.get("/trainer/{trainer_id}", response_class=HTMLResponse)
async def trainer_detail(trainer_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    trainer = db.query(User).filter(User.id == trainer_id, User.role == "trainer").first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    reviews = db.query(Review).filter(Review.trainer_id == trainer_id).order_by(Review.created_at.desc()).all()
    listings = db.query(Product).filter(Product.seller_id == trainer_id, Product.status == "active").order_by(Product.created_at.desc()).limit(4).all()
    return templates.TemplateResponse("trainer_detail.html", {
        "request": request, "user": user, "trainer": trainer, "reviews": reviews, "listings": listings,
    })

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/logout")
async def logout_page():
    """GET logout used by the navbar link — clears the cookie and redirects home."""
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("user_id")
    return response

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse("about.html", {"request": request, "user": user})

@app.get("/support", response_class=HTMLResponse)
async def support_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse("support.html", {"request": request, "user": user})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    my_listings = db.query(Product).filter(Product.seller_id == user.id).order_by(Product.created_at.desc()).all()
    my_purchases = db.query(MarketOrder, Product).join(Product, MarketOrder.product_id == Product.id).filter(
        MarketOrder.buyer_id == user.id).order_by(MarketOrder.created_at.desc()).all()
    my_sales = db.query(MarketOrder, Product).join(Product, MarketOrder.product_id == Product.id).filter(
        MarketOrder.seller_id == user.id).order_by(MarketOrder.created_at.desc()).all()

    if user.role == "trainer":
        bookings = db.query(Booking, User).join(User, Booking.client_id == User.id).filter(Booking.trainer_id == user.id).order_by(Booking.created_at.desc()).all()
        total_earnings = db.query(func.sum(Booking.amount)).filter(Booking.trainer_id == user.id, Booking.status == "completed").scalar() or 0
        return templates.TemplateResponse("dashboard_trainer.html", {
            "request": request, "user": user, "bookings": bookings, "total_earnings": total_earnings,
            "my_listings": my_listings, "my_sales": my_sales,
        })
    else:
        bookings = db.query(Booking, User).join(User, Booking.trainer_id == User.id).filter(Booking.client_id == user.id).order_by(Booking.created_at.desc()).all()
        transactions = db.query(WalletTransaction).filter(WalletTransaction.user_id == user.id).order_by(WalletTransaction.created_at.desc()).limit(10).all()

        engine = get_recommendation_engine(db)
        rec_trainers = engine.get_recommendations_for_user(user.id, limit=6)

        return templates.TemplateResponse("dashboard_client.html", {
            "request": request, "user": user, "bookings": bookings,
            "transactions": transactions, "rec_trainers": rec_trainers,
            "my_listings": my_listings, "my_purchases": my_purchases, "my_sales": my_sales,
        })

@app.get("/wallet", response_class=HTMLResponse)
async def wallet_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    transactions = db.query(WalletTransaction).filter(WalletTransaction.user_id == user.id).order_by(WalletTransaction.created_at.desc()).all()
    return templates.TemplateResponse("wallet.html", {"request": request, "user": user, "transactions": transactions})

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})

@app.get("/showcase", response_class=HTMLResponse)
async def showcase_page(request: Request, db: Session = Depends(get_db)):
    """Trainer's own showcase (витрина/анкета) editor."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user.role != "trainer":
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("showcase.html", {"request": request, "user": user})

@app.get("/book/{trainer_id}", response_class=HTMLResponse)
async def book_page(trainer_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "client":
        return RedirectResponse("/login", status_code=302)
    trainer = db.query(User).filter(User.id == trainer_id, User.role == "trainer").first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    return templates.TemplateResponse("book.html", {"request": request, "user": user, "trainer": trainer})

@app.get("/chat/{trainer_id}", response_class=HTMLResponse)
async def chat_page(trainer_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    try:
        trainer = db.query(User).filter(User.id == trainer_id).first()
        if not trainer:
            raise HTTPException(status_code=404, detail="User not found")
        messages = db.query(Message).filter(
            ((Message.sender_id == user.id) & (Message.receiver_id == trainer_id)) |
            ((Message.sender_id == trainer_id) & (Message.receiver_id == user.id))
        ).order_by(Message.created_at.asc()).all()
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error loading chat")
    return templates.TemplateResponse("chat.html", {"request": request, "user": user, "trainer": trainer, "messages": messages})

@app.get("/chat", response_class=HTMLResponse)
async def chat_redirect(request: Request, db: Session = Depends(get_db)):
    """Redirect /chat (without trainer_id) to the user's most recent conversation or trainer list."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    try:
        most_recent_message = db.query(Message).filter(
            (Message.sender_id == user.id) | (Message.receiver_id == user.id)
        ).order_by(Message.created_at.desc()).first()
    except SQLAlchemyError:
        most_recent_message = None

    if most_recent_message:
        other_user_id = most_recent_message.receiver_id if most_recent_message.sender_id == user.id else most_recent_message.sender_id
        return RedirectResponse(f"/chat/{other_user_id}", status_code=302)
    return RedirectResponse("/trainers", status_code=302)

# ============================================================
# MARKETPLACE PAGES
# ============================================================

@app.get("/market", response_class=HTMLResponse)
async def market_page(
    request: Request,
    category: str = None, condition: str = None, city: str = None,
    price_min: int = None, price_max: int = None,
    q: str = None, sort: str = "new",
    db: Session = Depends(get_db),
):
    """Gear marketplace catalog with Lolz-style filters."""
    user = get_current_user(request, db)
    query = db.query(Product).filter(Product.status == "active")

    if category:
        query = query.filter(Product.category == category)
    if condition:
        query = query.filter(Product.condition == condition)
    if city:
        query = query.filter(Product.city.ilike(f"%{city}%"))
    if price_min is not None:
        query = query.filter(Product.price >= price_min)
    if price_max is not None:
        query = query.filter(Product.price <= price_max)
    if q:
        query = query.filter(or_(
            Product.title.ilike(f"%{q}%"),
            Product.brand.ilike(f"%{q}%"),
            Product.description.ilike(f"%{q}%"),
        ))

    products = query.all()
    if sort == "price_asc":
        products.sort(key=lambda p: float(p.price or 0))
    elif sort == "price_desc":
        products.sort(key=lambda p: -float(p.price or 0))
    elif sort == "popular":
        products.sort(key=lambda p: -(p.views or 0))
    else:
        products.sort(key=lambda p: p.created_at or datetime.min, reverse=True)

    sellers = {p.seller_id: db.query(User).filter(User.id == p.seller_id).first() for p in products}

    filters = {
        "category": category, "condition": condition, "city": city,
        "price_min": price_min, "price_max": price_max, "q": q, "sort": sort,
    }
    return templates.TemplateResponse("market.html", {
        "request": request, "user": user, "products": products,
        "sellers": sellers, "filters": filters,
    })

@app.get("/market/new", response_class=HTMLResponse)
async def market_new_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("product_new.html", {"request": request, "user": user})

@app.get("/market/{product_id}", response_class=HTMLResponse)
async def product_detail(product_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # View counter (not for the seller's own views)
    try:
        if not user or user.id != product.seller_id:
            product.views = (product.views or 0) + 1
            db.commit()
    except SQLAlchemyError:
        db.rollback()

    seller = db.query(User).filter(User.id == product.seller_id).first()
    seller_reviews = db.query(MarketReview).filter(MarketReview.seller_id == product.seller_id).order_by(MarketReview.created_at.desc()).limit(10).all()
    reviewers = {r.buyer_id: db.query(User).filter(User.id == r.buyer_id).first() for r in seller_reviews}
    other_products = db.query(Product).filter(
        Product.seller_id == product.seller_id, Product.status == "active",
        Product.id != product.id).limit(4).all()

    # Check if current user has an escrow order for this product
    active_order = None
    completed_order_unreviewed = None
    if user:
        active_order = db.query(MarketOrder).filter(
            MarketOrder.product_id == product.id,
            MarketOrder.buyer_id == user.id,
            MarketOrder.status == "escrow").first()
        completed_order_unreviewed = db.query(MarketOrder).filter(
            MarketOrder.product_id == product.id,
            MarketOrder.buyer_id == user.id,
            MarketOrder.status == "completed").filter(
            ~MarketOrder.id.in_(db.query(MarketReview.order_id))).first()

    return templates.TemplateResponse("product.html", {
        "request": request, "user": user, "product": product, "seller": seller,
        "seller_reviews": seller_reviews, "reviewers": reviewers,
        "other_products": other_products, "active_order": active_order,
        "completed_order_unreviewed": completed_order_unreviewed,
        "market_fee_rate": MARKET_FEE_RATE,
    })

@app.get("/seller/{seller_id}", response_class=HTMLResponse)
async def seller_page(seller_id: int, request: Request, db: Session = Depends(get_db)):
    """Public seller profile: rating, active lots, feedback."""
    user = get_current_user(request, db)
    seller = db.query(User).filter(User.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    products = db.query(Product).filter(Product.seller_id == seller_id, Product.status == "active").order_by(Product.created_at.desc()).all()
    reviews = db.query(MarketReview).filter(MarketReview.seller_id == seller_id).order_by(MarketReview.created_at.desc()).all()
    reviewers = {r.buyer_id: db.query(User).filter(User.id == r.buyer_id).first() for r in reviews}
    return templates.TemplateResponse("seller.html", {
        "request": request, "user": user, "seller": seller,
        "products": products, "reviews": reviews, "reviewers": reviewers,
    })

# ============================================================
# API: AUTH
# ============================================================

@app.post("/api/auth/register")
@rate_limit(max_requests=5, window=60)
async def api_register(
    request: Request,
    name: str = Form(...), email: str = Form(...), password: str = Form(...),
    phone: str = Form(""), role: str = Form("client"), specialization: str = Form(""),
    hourly_rate: int = Form(0), experience_years: int = Form(0), bio: str = Form(""),
    fitness_goal: str = Form(""), experience_level: str = Form("beginner"),
    preferred_sport: str = Form(""), budget_max: int = Form(5000),
    location: str = Form(""), certification: str = Form(""),
    disciplines: List[str] = Form([]), work_formats: List[str] = Form([]),
    student_levels: List[str] = Form([]), gym: str = Form(""),
    personal_grade: str = Form(""),
    db: Session = Depends(get_db)
):
    # Input validation
    name = name.strip()
    email = email.strip().lower()
    if not name or len(name) < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required")
    if len(name) > MAX_NAME_LENGTH:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Name must be less than {MAX_NAME_LENGTH} characters")
    if not validate_email(email):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid email format")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if role not in ("client", "trainer"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Role must be 'client' or 'trainer'")

    try:
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error during email check")

    # Keep only known domain values
    disciplines = [d for d in disciplines if d in DISCIPLINES]
    work_formats = [f for f in work_formats if f in FORMATS]
    student_levels = [l for l in student_levels if l in LEVELS]
    if specialization not in DISCIPLINES:
        specialization = disciplines[0] if disciplines else ""
    if not disciplines and specialization:
        disciplines = [specialization]

    user = User(
        name=sanitize_input(name), email=email, password_hash=hash_password(password), phone=phone,
        role=role, specialization=specialization, hourly_rate=hourly_rate,
        experience_years=experience_years, bio=sanitize_input(bio), fitness_goal=fitness_goal,
        experience_level=experience_level, preferred_sport=preferred_sport,
        budget_max=budget_max, location=sanitize_input(location), certification=sanitize_input(certification),
        disciplines=disciplines, work_formats=work_formats, student_levels=student_levels,
        gym=sanitize_input(gym), personal_grade=sanitize_input(personal_grade),
        wallet_balance=0.00 if role == "trainer" else 500.00  # Welcome bonus for clients
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)

        db.add(ActivityLog(user_id=user.id, action="registered", extra_data={"role": role}))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")

    response = JSONResponse({"success": True, "user_id": user.id})
    response.set_cookie(key="user_id", value=str(user.id), httponly=True, secure=False, samesite="lax")
    return response

@app.post("/api/auth/login")
@rate_limit(max_requests=5, window=60)
async def api_login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    email = email.strip().lower()
    if not validate_email(email):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid email format")
    try:
        user = db.query(User).filter(User.email == email).first()
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error")
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    response = JSONResponse({"success": True, "user": {"id": user.id, "name": user.name, "role": user.role}})
    response.set_cookie(key="user_id", value=str(user.id), httponly=True, secure=False, samesite="lax")
    return response

@app.post("/api/auth/logout")
async def api_logout():
    response = JSONResponse({"success": True})
    response.delete_cookie("user_id")
    return response

# ============================================================
# API: SHOWCASE (trainer's own profile / витрина)
# ============================================================

@app.post("/api/showcase")
async def api_update_showcase(
    request: Request,
    name: str = Form(None), bio: str = Form(None), location: str = Form(None),
    specialization: str = Form(None), hourly_rate: int = Form(None),
    experience_years: int = Form(None), certification: str = Form(None),
    gym: str = Form(None), personal_grade: str = Form(None),
    achievements_text: str = Form(None),
    disciplines: List[str] = Form([]), work_formats: List[str] = Form([]),
    student_levels: List[str] = Form([]),
    db: Session = Depends(get_db),
):
    """Update the trainer's public showcase (анкета/витрина)."""
    user = get_current_user(request, db)
    if not user or user.role != "trainer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only trainers can edit a showcase")
    try:
        if name and name.strip():
            if len(name.strip()) > MAX_NAME_LENGTH:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name too long")
            user.name = sanitize_input(name.strip())
        if bio is not None: user.bio = sanitize_input(bio.strip())
        if location is not None: user.location = sanitize_input(location.strip())
        if hourly_rate is not None:
            if hourly_rate < 0:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rate must be non-negative")
            user.hourly_rate = hourly_rate
        if experience_years is not None:
            if experience_years < 0:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Experience must be non-negative")
            user.experience_years = experience_years
        if certification is not None: user.certification = sanitize_input(certification.strip())
        if gym is not None: user.gym = sanitize_input(gym.strip())
        if personal_grade is not None: user.personal_grade = sanitize_input(personal_grade.strip())
        if achievements_text is not None: user.achievements_text = sanitize_input(achievements_text.strip())

        disciplines = [d for d in disciplines if d in DISCIPLINES]
        work_formats = [f for f in work_formats if f in FORMATS]
        student_levels = [l for l in student_levels if l in LEVELS]
        user.disciplines = disciplines
        user.work_formats = work_formats
        user.student_levels = student_levels
        if specialization in DISCIPLINES:
            user.specialization = specialization
        elif disciplines:
            user.specialization = disciplines[0]

        db.commit()
        return {"success": True}
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update showcase")

# ============================================================
# API: RECOMMENDATIONS
# ============================================================

@app.get("/api/recommendations")
async def api_recommendations(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    engine = get_recommendation_engine(db)
    if not user:
        trainers = engine._get_trending_trainers(6)
    else:
        trainers = engine.get_recommendations_for_user(user.id, limit=6)
        engine.update_user_interests(user.id)

    return [{
        "id": t.id, "name": t.name, "specialization": t.specialization,
        "disciplines": t.disciplines or [],
        "hourly_rate": t.hourly_rate, "rating": t.rating,
        "experience_years": t.experience_years, "verification_level": t.verification_level,
        "total_reviews": t.total_reviews, "rec_score": getattr(t, "rec_score", 0),
        "rec_reason": getattr(t, "rec_reason", ""), "bio": t.bio[:100] if t.bio else ""
    } for t in trainers]

# ============================================================
# API: BOOKINGS
# ============================================================

@app.post("/api/bookings")
async def api_create_booking(
    trainer_id: int = Form(...), booking_type: str = Form("single"),
    scheduled_at: str = Form(...), notes: str = Form(""),
    request: Request = None, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user or user.role != "client":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only clients can book")

    try:
        trainer = db.query(User).filter(User.id == trainer_id, User.role == "trainer").first()
        if not trainer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trainer not found")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error")

    sessions_map = {"single": 1, "package_5": 5, "package_10": 10, "package_20": 20}
    sessions = sessions_map.get(booking_type, 1)
    discount = {1: 1.0, 5: 0.95, 10: 0.90, 20: 0.85}.get(sessions, 1.0)
    amount = float(trainer.hourly_rate) * sessions * discount
    platform_fee = amount * float(trainer.sliding_commission_rate)

    if float(user.wallet_balance) + float(user.wallet_bonus) < amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient wallet balance. Please top up.")

    bonus_used = min(float(user.wallet_bonus), amount)
    balance_used = amount - bonus_used

    user.wallet_balance = float(user.wallet_balance) - balance_used
    user.wallet_bonus = float(user.wallet_bonus) - bonus_used

    booking = Booking(
        client_id=user.id, trainer_id=trainer_id, booking_type=booking_type,
        sessions_total=sessions, sessions_used=0, amount=amount,
        platform_fee=platform_fee, scheduled_at=datetime.fromisoformat(scheduled_at.replace("Z", "+00:00")),
        notes=sanitize_input(notes), status="confirmed"
    )
    try:
        db.add(booking)
        db.commit()
        db.refresh(booking)

        db.add(WalletTransaction(
            user_id=user.id, type="payment", amount=-amount,
            balance_after=user.wallet_balance, description=f"Booking with {trainer.name}",
            reference_id=booking.id
        ))
        db.commit()

        _update_streak(user, db)

        cashback = amount * 0.05
        user.wallet_bonus = float(user.wallet_bonus) + cashback
        db.add(WalletTransaction(
            user_id=user.id, type="cashback", amount=cashback,
            balance_after=user.wallet_balance, description="Cashback for booking",
            reference_id=booking.id
        ))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create booking")

    return {"success": True, "booking_id": booking.id, "amount": amount, "cashback": cashback}

@app.post("/api/bookings/{booking_id}/complete")
async def api_complete_booking(booking_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        if booking.client_id != user.id and booking.trainer_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")

        booking.status = "completed"
        booking.completed_at = datetime.utcnow()
        booking.sessions_used = booking.sessions_total

        trainer = db.query(User).filter(User.id == booking.trainer_id).first()
        if not trainer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trainer not found")

        trainer_amount = float(booking.amount) - float(booking.platform_fee)
        trainer.wallet_balance = float(trainer.wallet_balance) + trainer_amount
        trainer.total_earnings = float(trainer.total_earnings) + trainer_amount
        trainer.total_bookings = (trainer.total_bookings or 0) + booking.sessions_total

        earnings = float(trainer.total_earnings)
        if earnings > 200000:
            trainer.sliding_commission_rate = 0.05
        elif earnings > 100000:
            trainer.sliding_commission_rate = 0.07
        elif earnings > 50000:
            trainer.sliding_commission_rate = 0.10
        elif earnings > 20000:
            trainer.sliding_commission_rate = 0.15
        else:
            trainer.sliding_commission_rate = 0.20

        db.add(WalletTransaction(
            user_id=trainer.id, type="withdrawal", amount=trainer_amount,
            balance_after=trainer.wallet_balance, description=f"Payment for booking #{booking.id}",
            reference_id=booking.id
        ))

        db.commit()

        engine = get_recommendation_engine(db)
        engine.update_user_interests(booking.client_id)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to complete booking")

    return {"success": True, "trainer_amount": trainer_amount}

@app.post("/api/reviews")
async def api_post_review(
    booking_id: int = Form(...), rating: int = Form(...),
    professionalism: int = Form(5), punctuality: int = Form(5),
    effectiveness: int = Form(5), comment: str = Form(""),
    request: Request = None, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

    if not (1 <= rating <= 5) or not (1 <= professionalism <= 5) or not (1 <= punctuality <= 5) or not (1 <= effectiveness <= 5):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ratings must be between 1 and 5")

    sanitized_comment = sanitize_input(comment)

    try:
        booking = db.query(Booking).filter(Booking.id == booking_id, Booking.client_id == user.id).first()
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        review = Review(
            booking_id=booking_id, client_id=user.id, trainer_id=booking.trainer_id,
            rating=rating, professionalism=professionalism, punctuality=punctuality,
            effectiveness=effectiveness, comment=sanitized_comment
        )
        db.add(review)
        db.commit()

        trainer = db.query(User).filter(User.id == booking.trainer_id).first()
        reviews = db.query(Review).filter(Review.trainer_id == trainer.id).all()
        if reviews:
            trainer.rating = round(sum(r.rating for r in reviews) / len(reviews), 1)
            trainer.total_reviews = len(reviews)
        db.commit()

        user.loyalty_points = (user.loyalty_points or 0) + 50
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to submit review")

    return {"success": True, "review_id": review.id}

# ============================================================
# API: WALLET / PROFILE
# ============================================================

@app.post("/api/wallet/deposit")
async def api_deposit(amount: float = Form(...), request: Request = None, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Deposit amount must be positive")

    try:
        user.wallet_balance = float(user.wallet_balance) + amount
        db.add(WalletTransaction(
            user_id=user.id, type="deposit", amount=amount,
            balance_after=user.wallet_balance, description="Wallet top-up"
        ))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process deposit")

    return {"success": True, "new_balance": float(user.wallet_balance)}

@app.get("/api/profile")
async def api_get_profile(request: Request, db: Session = Depends(get_db)):
    """Get current user profile."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
    return {
        "id": user.id, "name": user.name, "email": user.email, "phone": user.phone,
        "role": user.role, "bio": user.bio, "location": user.location,
        "fitness_goal": user.fitness_goal, "experience_level": user.experience_level,
        "preferred_sport": user.preferred_sport, "budget_max": user.budget_max,
        "wallet_balance": float(user.wallet_balance), "wallet_bonus": float(user.wallet_bonus),
        "loyalty_points": user.loyalty_points, "client_level": user.client_level,
        "streak_weeks": user.streak_weeks, "achievements": user.achievements or [],
        "disciplines": user.disciplines or [], "work_formats": user.work_formats or [],
        "student_levels": user.student_levels or [], "gym": user.gym,
        "personal_grade": user.personal_grade,
    }

@app.post("/api/profile")
async def api_update_profile(
    name: str = Form(None), phone: str = Form(None), bio: str = Form(None),
    location: str = Form(None), fitness_goal: str = Form(None),
    experience_level: str = Form(None), preferred_sport: str = Form(None),
    budget_max: int = Form(None), request: Request = None,
    db: Session = Depends(get_db)
):
    """Update current user profile."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
    try:
        if name: user.name = sanitize_input(name.strip())
        if phone: user.phone = phone.strip()
        if bio: user.bio = sanitize_input(bio.strip())
        if location: user.location = sanitize_input(location.strip())
        if fitness_goal: user.fitness_goal = fitness_goal
        if experience_level: user.experience_level = experience_level
        if preferred_sport: user.preferred_sport = preferred_sport
        if budget_max is not None: user.budget_max = budget_max
        db.commit()
        return {"success": True}
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update profile")

@app.post("/api/withdrawal")
async def api_withdrawal(amount: float = Form(...), request: Request = None, db: Session = Depends(get_db)):
    """Trainer withdrawal request."""
    user = get_current_user(request, db)
    if not user or user.role != "trainer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only trainers can withdraw")
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Amount must be positive")
    if float(user.wallet_balance) < amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance")
    try:
        user.wallet_balance = float(user.wallet_balance) - amount
        db.add(WalletTransaction(
            user_id=user.id, type="withdrawal", amount=-amount,
            balance_after=user.wallet_balance, description="Withdrawal to bank card"
        ))
        db.commit()
        return {"success": True, "new_balance": float(user.wallet_balance)}
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process withdrawal")

# ============================================================
# API: MESSAGES
# ============================================================

@app.post("/api/messages")
async def api_send_message(
    receiver_id: int = Form(...), content: str = Form(...),
    request: Request = None, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

    if not content or not content.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message content cannot be empty")

    has_contact = bool(re.search(r"(\+7\d{10}|\d{3}-\d{3}-\d{4}|@\w+|\.ru|\.com|http|t\.me/|vk\.com/|instagram\.com/|whatsapp|telegram)", content, re.I))

    try:
        msg = Message(
            sender_id=user.id, receiver_id=receiver_id, content=sanitize_input(content),
            has_contact_info=has_contact
        )
        db.add(msg)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send message")

    if has_contact:
        return {"success": True, "warning": "Please keep communication on platform for safety"}
    return {"success": True}

@app.get("/api/messages/{trainer_id}")
async def api_get_messages(trainer_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

    try:
        messages = db.query(Message).filter(
            ((Message.sender_id == user.id) & (Message.receiver_id == trainer_id)) |
            ((Message.sender_id == trainer_id) & (Message.receiver_id == user.id))
        ).order_by(Message.created_at.asc()).all()
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load messages")

    return [{
        "id": m.id, "sender_id": m.sender_id, "content": m.content,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "has_contact_info": m.has_contact_info
    } for m in messages]

@app.get("/api/stats")
async def api_stats(db: Session = Depends(get_db)):
    try:
        total_trainers = db.query(User).filter(User.role == "trainer").count()
        total_clients = db.query(User).filter(User.role == "client").count()
        total_bookings = db.query(Booking).count()
        total_products = db.query(Product).filter(Product.status == "active").count()
        avg_rating = db.query(func.avg(User.rating)).filter(User.role == "trainer").scalar() or 0
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load statistics")
    return {
        "total_trainers": total_trainers, "total_clients": total_clients,
        "total_bookings": total_bookings, "total_products": total_products,
        "avg_rating": round(float(avg_rating), 1)
    }

# ============================================================
# API: MARKETPLACE
# ============================================================

@app.post("/api/market/products")
@rate_limit(max_requests=10, window=60)
async def api_create_product(
    request: Request,
    title: str = Form(...), category: str = Form(...),
    price: float = Form(...), condition: str = Form("good"),
    brand: str = Form(""), size: str = Form(""),
    description: str = Form(""), city: str = Form(""),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    """Create a new marketplace listing (lot)."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

    title = title.strip()
    if not (3 <= len(title) <= 150):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Title must be 3-150 characters")
    if category not in GEAR_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown category")
    if condition not in CONDITIONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown condition")
    if price <= 0 or price > 100_000_000:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid price")

    image_path = ""
    if image is not None and image.filename:
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in ALLOWED_IMAGE_EXT:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only jpg/png/webp images are allowed")
        content = await image.read()
        if len(content) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Image is too large (max 8 MB)")
        filename = "%s%s" % (uuid.uuid4().hex, ext)
        with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
            f.write(content)
        image_path = "uploads/" + filename

    product = Product(
        seller_id=user.id, title=sanitize_input(title), category=category,
        brand=sanitize_input(brand.strip()), size=sanitize_input(size.strip()),
        condition=condition, price=price, description=sanitize_input(description.strip()),
        city=sanitize_input(city.strip()), image=image_path, status="active",
    )
    try:
        db.add(product)
        db.commit()
        db.refresh(product)
        db.add(ActivityLog(user_id=user.id, action="product_created", extra_data={"product_id": product.id}))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create listing")

    return {"success": True, "product_id": product.id}

@app.post("/api/market/products/{product_id}/archive")
async def api_archive_product(product_id: int, request: Request, db: Session = Depends(get_db)):
    """Seller archives (removes) their own active listing."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.seller_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your listing")
    if product.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Listing is not active")
    try:
        product.status = "archived"
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to archive listing")
    return {"success": True}

@app.post("/api/market/products/{product_id}/buy")
async def api_buy_product(product_id: int, request: Request, db: Session = Depends(get_db)):
    """Buy a listing with escrow: money is held until the buyer confirms receipt."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Listing is no longer available")
    if product.seller_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot buy your own listing")

    amount = float(product.price)
    if float(user.wallet_balance) + float(user.wallet_bonus) < amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient wallet balance. Please top up.")

    bonus_used = min(float(user.wallet_bonus), amount)
    balance_used = amount - bonus_used
    fee = round(amount * MARKET_FEE_RATE, 2)

    try:
        user.wallet_balance = float(user.wallet_balance) - balance_used
        user.wallet_bonus = float(user.wallet_bonus) - bonus_used

        order = MarketOrder(
            product_id=product.id, buyer_id=user.id, seller_id=product.seller_id,
            amount=amount, fee=fee, status="escrow",
        )
        db.add(order)
        product.status = "sold"
        db.commit()
        db.refresh(order)

        db.add(WalletTransaction(
            user_id=user.id, type="escrow", amount=-amount,
            balance_after=user.wallet_balance,
            description="Safe deal: %s" % product.title, reference_id=order.id,
        ))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create order")

    return {"success": True, "order_id": order.id, "amount": amount}

@app.post("/api/market/orders/{order_id}/confirm")
async def api_confirm_order(order_id: int, request: Request, db: Session = Depends(get_db)):
    """Buyer confirms receipt — escrow is released to the seller minus the fee."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

    order = db.query(MarketOrder).filter(MarketOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.buyer_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the buyer can confirm receipt")
    if order.status != "escrow":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not in escrow")

    try:
        seller = db.query(User).filter(User.id == order.seller_id).first()
        if not seller:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")

        seller_amount = float(order.amount) - float(order.fee)
        seller.wallet_balance = float(seller.wallet_balance) + seller_amount
        seller.seller_sales = (seller.seller_sales or 0) + 1

        order.status = "completed"
        order.completed_at = datetime.utcnow()

        db.add(WalletTransaction(
            user_id=seller.id, type="escrow_release", amount=seller_amount,
            balance_after=seller.wallet_balance,
            description="Safe deal payout (order #%d)" % order.id, reference_id=order.id,
        ))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to release escrow")

    return {"success": True, "seller_amount": seller_amount}

@app.post("/api/market/orders/{order_id}/cancel")
async def api_cancel_order(order_id: int, request: Request, db: Session = Depends(get_db)):
    """Cancel an escrow order (buyer or seller) — full refund to the buyer."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

    order = db.query(MarketOrder).filter(MarketOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.buyer_id != user.id and order.seller_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your order")
    if order.status != "escrow":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only escrow orders can be cancelled")

    try:
        buyer = db.query(User).filter(User.id == order.buyer_id).first()
        product = db.query(Product).filter(Product.id == order.product_id).first()

        buyer.wallet_balance = float(buyer.wallet_balance) + float(order.amount)
        if product:
            product.status = "active"
        order.status = "refunded"
        order.completed_at = datetime.utcnow()

        db.add(WalletTransaction(
            user_id=buyer.id, type="refund", amount=float(order.amount),
            balance_after=buyer.wallet_balance,
            description="Safe deal refund (order #%d)" % order.id, reference_id=order.id,
        ))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to cancel order")

    return {"success": True, "refunded": float(order.amount)}

@app.post("/api/market/orders/{order_id}/review")
async def api_review_seller(
    order_id: int, rating: int = Form(...), comment: str = Form(""),
    request: Request = None, db: Session = Depends(get_db),
):
    """Buyer leaves feedback about the seller after a completed order."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
    if not (1 <= rating <= 5):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rating must be between 1 and 5")

    order = db.query(MarketOrder).filter(MarketOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.buyer_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the buyer can review this order")
    if order.status != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not completed yet")
    if db.query(MarketReview).filter(MarketReview.order_id == order_id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order already reviewed")

    try:
        review = MarketReview(
            order_id=order_id, buyer_id=user.id, seller_id=order.seller_id,
            rating=rating, comment=sanitize_input(comment),
        )
        db.add(review)
        db.commit()

        seller = db.query(User).filter(User.id == order.seller_id).first()
        reviews = db.query(MarketReview).filter(MarketReview.seller_id == seller.id).all()
        seller.seller_rating = round(sum(r.rating for r in reviews) / len(reviews), 1)
        seller.seller_reviews_total = len(reviews)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to submit feedback")

    return {"success": True, "review_id": review.id}

# ============================================================
# HELPERS
# ============================================================

def _get_week_key(dt: datetime) -> int:
    """Return an integer representing the ISO calendar week for comparison."""
    return dt.isocalendar()[0] * 100 + dt.isocalendar()[1]

def _iso_week_monday(year: int, week: int) -> date:
    """Monday of the given ISO week. Python 3.7 compatible (no date.fromisocalendar)."""
    return datetime.strptime("%d %d 1" % (year, week), "%G %V %u").date()

def _update_streak(user: User, db: Session) -> None:
    """Update user streak based on consecutive weekly bookings."""
    try:
        bookings = db.query(Booking).filter(
            Booking.client_id == user.id,
            Booking.status.in_(["confirmed", "completed"])
        ).order_by(Booking.created_at.desc()).all()

        if not bookings:
            return

        booked_weeks: List[int] = []
        for booking in bookings:
            if booking.created_at:
                week_key = _get_week_key(booking.created_at)
                if week_key not in booked_weeks:
                    booked_weeks.append(week_key)

        if not booked_weeks:
            return

        current_streak = 1
        for i in range(len(booked_weeks) - 1):
            year1, week1 = divmod(booked_weeks[i], 100)
            year2, week2 = divmod(booked_weeks[i + 1], 100)
            dt1 = _iso_week_monday(year1, week1)
            dt2 = _iso_week_monday(year2, week2)
            week_diff = (dt1 - dt2).days // 7
            if week_diff == 1:
                current_streak += 1
            else:
                break

        current_week = _get_week_key(datetime.utcnow())
        latest_booking_week = booked_weeks[0]
        year_cur, week_cur = divmod(current_week, 100)
        year_latest, week_latest = divmod(latest_booking_week, 100)
        dt_cur = _iso_week_monday(year_cur, week_cur)
        dt_latest = _iso_week_monday(year_latest, week_latest)
        weeks_since_last = (dt_cur - dt_latest).days // 7

        if weeks_since_last > 1:
            user.streak_weeks = 0
        else:
            user.streak_weeks = current_streak

        achievements = list(user.achievements or [])
        total_bookings = db.query(Booking).filter(
            Booking.client_id == user.id,
            Booking.status.in_(["confirmed", "completed"])
        ).count()

        if total_bookings >= 1 and "first_booking" not in achievements:
            achievements.append("first_booking")
        if total_bookings >= 5 and "five_bookings" not in achievements:
            achievements.append("five_bookings")
        if user.streak_weeks >= 4 and "month_streak" not in achievements:
            achievements.append("month_streak")

        user.achievements = achievements

        if total_bookings >= 20 and user.streak_weeks >= 8:
            user.client_level = "master"
        elif total_bookings >= 10 and user.streak_weeks >= 4:
            user.client_level = "advanced"
        elif total_bookings >= 3:
            user.client_level = "active"

        db.commit()
    except SQLAlchemyError:
        db.rollback()

def _seed_demo_bookings_and_reviews(db: Session) -> None:
    """Create demo bookings and reviews so the site shows real data."""
    trainers = db.query(User).filter(User.role == "trainer").all()
    if not trainers:
        return

    client = db.query(User).filter(User.email == "demo@client.ru").first()
    if not client:
        client = User(
            name="Демо Клиент", email="demo@client.ru",
            password_hash=hash_password("demo123"), role="client",
            wallet_balance=25000.00, wallet_bonus=500.00,
            preferred_sport="bouldering", fitness_goal="learn_basics"
        )
        db.add(client)
        db.commit()
        db.refresh(client)

    reviews_data = {
        "bouldering": [
            (5, "Пришёл совсем зелёным — за два месяца уверенно лезу 6А. Дмитрий круто объясняет работу ног и флажки.", "Артём К."),
            (5, "Лучший боулдеринг-тренер в городе. Каждое занятие — разбор видео и новые приёмы.", "Мария Л."),
            (4, "Отличные тренировки, жаль вечерние слоты разлетаются быстро.", "Олег П."),
        ],
        "lead": [
            (5, "Готовился к первой нижней на скалах — Антон довёл до результата: пролез 6b+ в Крыму!", "Игорь С."),
            (5, "Научил правильно отдыхать на трассе и клиппить без паники. Страховка — на высшем уровне.", "Вера Н."),
            (4, "Требовательный тренер, но прогресс реальный: с 6а до 7а за сезон.", "Роман Д."),
        ],
        "speed": [
            (5, "Дочь за полгода вышла на всероссийский уровень. Постановка старта и бега по трассе — супер.", "Елена В."),
            (4, "Хорошая работа над скоростными связками, много специфики.", "Кирилл А."),
        ],
        "toprope": [
            (5, "Боялась высоты — теперь лажу с удовольствием. Очень бережный и внимательный подход.", "Наталья М."),
            (5, "Идеально для старта: узлы, страховка, первые трассы. Рекомендую всем новичкам!", "Павел Г."),
        ],
        "trad": [
            (5, "Сергей научил читать рельеф и ставить закладки так, что стало спокойно на собственных маршрутах.", "Андрей Т."),
            (5, "Выезд на трад-практику в Крым — лучшее, что случалось с моим лазанием. Френды больше не страшны.", "Юлия Р."),
        ],
        "multipitch": [
            (5, "Прошли с Максимом первый мультипитч 5 pitches на южном берегу. Станции, смены, спуски — всё чётко.", "Денис Б."),
            (4, "Грамотная подготовка к длинным маршрутам, много практики на рельефе.", "Семён К."),
        ],
        "ice": [
            (5, "Драйтулинг и лёд с нуля за зиму: техника кошек, ледобуры, безопасность. Топ!", "Владимир О."),
            (5, "Ездили на ледопады — организация и безопасность на высоте.", "Григорий Ш."),
        ],
        "training": [
            (5, "Пальцы окрепли заметно: хангборд-программа Ольги дала +1 категория за 3 месяца.", "Станислав Ж."),
            (4, "Системная СФП: антагонисты, плечи, кисти. Меньше травм, больше лазания.", "Алиса Ф."),
        ],
        "kids": [
            (5, "Сын (8 лет) в восторге: игры, зацепы, первые верхушки. Тренер находит подход к детям.", "Оксана Д."),
            (5, "Дочка стала увереннее не только на стене, но и в жизни. Спасибо за терпение!", "Михаил Р."),
        ],
    }

    for trainer in trainers:
        key = _trainer_primary_discipline(trainer)
        trainer_reviews = reviews_data.get(key, [])

        for rating, comment, reviewer_name in trainer_reviews:
            booking = Booking(
                client_id=client.id,
                trainer_id=trainer.id,
                status="completed",
                booking_type="single",
                sessions_total=1,
                sessions_used=1,
                amount=float(trainer.hourly_rate),
                platform_fee=float(trainer.hourly_rate) * 0.20,
                completed_at=datetime.utcnow() - timedelta(days=rating * 7),
                notes="Demo booking for review"
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)

            review = Review(
                booking_id=booking.id,
                client_id=client.id,
                trainer_id=trainer.id,
                rating=rating,
                professionalism=rating,
                punctuality=rating,
                effectiveness=rating,
                comment=comment
            )
            db.add(review)
            db.commit()

        all_reviews = db.query(Review).filter(Review.trainer_id == trainer.id).all()
        if all_reviews:
            trainer.rating = round(sum(r.rating for r in all_reviews) / len(all_reviews), 1)
            trainer.total_reviews = len(all_reviews)

    db.commit()

def _seed_demo_products(db: Session, sellers: List[User]) -> None:
    """Create demo marketplace listings across gear categories."""
    products_data = [
        {"title": "Скальные туфли La Sportiva Solution, 42", "category": "shoes", "brand": "La Sportiva",
         "size": "EU 42", "condition": "good", "price": 6500, "city": "Москва",
         "description": "Легендарная модель для боулдеринга. Носок и пятка в отличном состоянии, резина XS Grip2. Лазали один сезон по залу.", "image": "images/products/shoes.jpg"},
        {"title": "Скальники Scarpa Drago, 41.5 — почти новые", "category": "shoes", "brand": "Scarpa",
         "size": "EU 41.5", "condition": "like_new", "price": 8900, "city": "Санкт-Петербург",
         "description": "Мягкие и чувствительные, идеальны для боулдеринга. Куплены в этом сезоне, оказались малы. Пробовали 3 раза в зале.", "image": "images/products/shoes2.jpg"},
        {"title": "Обвязка Petzl Corax, размер 2", "category": "harness", "brand": "Petzl",
         "size": "2 (76-107 см)", "condition": "good", "price": 3200, "city": "Москва",
         "description": "Универсальная регулируемая обвязка для зала и скал. 4 точки для снаряжения. Состояние отличное, без повреждений строп.", "image": "images/products/harness.jpg"},
        {"title": "Petzl GriGri+ с карабином", "category": "belay", "brand": "Petzl",
         "size": "", "condition": "good", "price": 7500, "city": "Екатеринбург",
         "description": "Страховочное устройство с вспомогательной блокировкой. Ручка и кулачок в норме, люфтов нет. В комплекте карабин Petzl Attache.", "image": "images/products/grigri.jpg"},
        {"title": "Оттяжки Black Diamond HotForge, 6 шт", "category": "carabiners", "brand": "Black Diamond",
         "size": "12 см", "condition": "like_new", "price": 9900, "city": "Москва",
         "description": "Комплект из 6 оттяжек для трудности. Карабины без задиров, стропа без потёртостей. Использовались два выезда.", "image": "images/products/quickdraws.jpg"},
        {"title": "Верёвка динамическая Beal Joker 9.1, 60 м", "category": "ropes", "brand": "Beal",
         "size": "60 м", "condition": "good", "price": 11500, "city": "Красноярск",
         "description": "Одинарная/половинная/сдвоенная. Сухая пропитка Golden Dry. Рывков выше фактора 1 не было, концы целые, не мохнатая.", "image": "images/products/rope.jpg"},
        {"title": "Крашпад Ocun Paddy Dominator", "category": "crashpads", "brand": "Ocun",
         "size": "120x100x10 см", "condition": "good", "price": 14000, "city": "Санкт-Петербург",
         "description": "Надёжный боулдермат для выездов на камни. Пена держит форму, чехол без дыр, лямки целые. Отличный вариант для Скал Довбуша и не только.", "image": "images/products/crashpad.jpg"},
        {"title": "Мешок для магнезии + магнезия 300 г", "category": "chalk", "brand": "Red Chili",
         "size": "", "condition": "new", "price": 1500, "city": "Москва",
         "description": "Новый мешочек с плотной затяжкой + пачка магнезии в подарок. Флисовая внутренность, держит форму.", "image": "images/products/chalk.jpg"},
        {"title": "Каска Black Diamond Half Dome, M/L", "category": "helmets", "brand": "Black Diamond",
         "size": "M/L", "condition": "like_new", "price": 4200, "city": "Новосибирск",
         "description": "Классическая прочная каска для скал и мультипитча. Без ударов и падений камней, пользовался аккуратно.", "image": "images/products/helmet.jpg"},
        {"title": "Хангборд Beastmaker 1000", "category": "training_gear", "brand": "Beastmaker",
         "size": "", "condition": "good", "price": 6800, "city": "Москва",
         "description": "Деревянный фингерборд для домашних тренировок пальцев. Щадящий для кожи. Крепёж в комплекте.", "image": "images/products/hangboard.jpg"},
        {"title": "Закладки Black Diamond Stoppers №1-13, набор", "category": "trad_gear", "brand": "Black Diamond",
         "size": "№1-13", "condition": "good", "price": 8500, "city": "Сочи",
         "description": "Полный набор закладок на оттяжке. Проверены, тросики без заломов. Отличный стартовый трад-комплект.", "image": "images/products/nuts.jpg"},
        {"title": "Рюкзак Black Diamond Crag 40", "category": "packs", "brand": "Black Diamond",
         "size": "40 л", "condition": "like_new", "price": 5900, "city": "Москва",
         "description": "Вместительный крэг-пак под верёвку и снарягу для выездов на скалы. Почти не использовался.", "image": "images/products/backpack.jpg"},
    ]

    created = []
    for i, pd in enumerate(products_data):
        seller = sellers[i % len(sellers)]
        product = Product(
            seller_id=seller.id, title=pd["title"], category=pd["category"],
            brand=pd["brand"], size=pd["size"], condition=pd["condition"],
            price=pd["price"], description=pd["description"], city=pd["city"],
            image=pd["image"], status="active", views=10 + i * 7,
            created_at=datetime.utcnow() - timedelta(days=i * 2),
        )
        db.add(product)
        created.append(product)
    db.commit()

    # A couple of completed demo orders + seller feedback
    client = db.query(User).filter(User.email == "demo@client.ru").first()
    if client and created:
        for product, rating, comment in [
            (created[2], 5, "Всё как в описании, отправил быстро. Рекомендую продавца!"),
            (created[7], 5, "Мешочек новый, магнезия в подарок — приятно. Спасибо!"),
        ]:
            order = MarketOrder(
                product_id=product.id, buyer_id=client.id, seller_id=product.seller_id,
                amount=float(product.price), fee=round(float(product.price) * MARKET_FEE_RATE, 2),
                status="completed", created_at=datetime.utcnow() - timedelta(days=5),
                completed_at=datetime.utcnow() - timedelta(days=3),
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            db.add(MarketReview(order_id=order.id, buyer_id=client.id, seller_id=product.seller_id,
                                rating=rating, comment=comment))
            db.commit()

        # Refresh seller stats
        for seller in sellers:
            reviews = db.query(MarketReview).filter(MarketReview.seller_id == seller.id).all()
            if reviews:
                seller.seller_rating = round(sum(r.rating for r in reviews) / len(reviews), 1)
                seller.seller_reviews_total = len(reviews)
            seller.seller_sales = db.query(MarketOrder).filter(
                MarketOrder.seller_id == seller.id, MarketOrder.status == "completed").count()
        db.commit()

# Seed data endpoint (for demo) - protected to prevent re-seeding and unauthorized access
SEED_LOCK: bool = False

@app.post("/api/seed")
async def api_seed(request: Request, db: Session = Depends(get_db)):
    global SEED_LOCK

    if SEED_LOCK:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Seeding already in progress or completed")

    try:
        if db.query(User).count() > 0:
            SEED_LOCK = True
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Database already seeded")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error checking seed status")

    SEED_LOCK = True

    trainers_data = [
        {"name": "Дмитрий Кравцов", "email": "dmitry@trainer.ru", "password": "demo123", "role": "trainer",
         "specialization": "bouldering", "disciplines": ["bouldering", "training"],
         "work_formats": ["gym"], "student_levels": ["beginner", "intermediate", "advanced"],
         "hourly_rate": 1800, "experience_years": 9, "rating": 4.9, "total_reviews": 46,
         "bio": "Тренер по боулдерингу. КМС, финалист этапов Кубка России. Разбор видео на каждом занятии, ставлю технику ног и динамику.",
         "verification_level": 3, "certification": "КМС по скалолазанию, судья всероссийской категории",
         "location": "Москва", "gym": "Скала Сити", "personal_grade": "V10 / 8A",
         "achievements_text": "Финалист Кубка России по боулдерингу (2023), чемпион Москвы (2022)"},
        {"name": "Антон Скворцов", "email": "anton@trainer.ru", "password": "demo123", "role": "trainer",
         "specialization": "lead", "disciplines": ["lead", "toprope", "multipitch"],
         "work_formats": ["gym", "outdoor"], "student_levels": ["beginner", "intermediate", "advanced"],
         "hourly_rate": 2000, "experience_years": 12, "rating": 4.8, "total_reviews": 39,
         "bio": "Трудность и скалы. Готовлю к первой нижней страховке и выездам в Крым и на Кавказ. Упор на безопасность и чтение рельефа.",
         "verification_level": 3, "certification": "Инструктор спортивного скалолазания, ФАР",
         "location": "Москва", "gym": "BigWall", "personal_grade": "8a+",
         "achievements_text": "Пролез 30+ маршрутов категории 8а и выше, организатор выездов в Крым"},
        {"name": "Виктория Ланская", "email": "vika@trainer.ru", "password": "demo123", "role": "trainer",
         "specialization": "speed", "disciplines": ["speed", "training"],
         "work_formats": ["gym"], "student_levels": ["intermediate", "advanced", "competition"],
         "hourly_rate": 2200, "experience_years": 7, "rating": 4.7, "total_reviews": 28,
         "bio": "Скорость: постановка старта, беговые связки, работа с секундомером. Готовлю спортсменов к всероссийским стартам.",
         "verification_level": 2, "certification": "Мастер спорта по скалолазанию (скорость)",
         "location": "Санкт-Петербург", "gym": "Северная стена", "personal_grade": "7.8 сек (15 м)",
         "achievements_text": "Мастер спорта, призёр чемпионата СПб по скорости"},
        {"name": "Ольга Мирная", "email": "olga@trainer.ru", "password": "demo123", "role": "trainer",
         "specialization": "toprope", "disciplines": ["toprope", "bouldering"],
         "work_formats": ["gym"], "student_levels": ["beginner"],
         "hourly_rate": 1400, "experience_years": 5, "rating": 4.9, "total_reviews": 52,
         "bio": "Мягкий старт в скалолазание: верхняя страховка, узлы, первые трассы. Работаю со страхом высоты — бережно и по шагам.",
         "verification_level": 3, "certification": "Инструктор скалодрома, курс первой помощи",
         "location": "Москва", "gym": "Лаймстоун", "personal_grade": "7a",
         "achievements_text": "Провела 500+ вводных занятий для новичков"},
        {"name": "Сергей Гранитов", "email": "sergey@trainer.ru", "password": "demo123", "role": "trainer",
         "specialization": "trad", "disciplines": ["trad", "multipitch"],
         "work_formats": ["outdoor"], "student_levels": ["intermediate", "advanced"],
         "hourly_rate": 2500, "experience_years": 15, "rating": 4.8, "total_reviews": 24,
         "bio": "Трад и собственные точки: закладки, френды, станции. Практика на реальном рельефе — Крым, Кавказ, Кольский.",
         "verification_level": 3, "certification": "Инструктор альпинизма 2 категории",
         "location": "Сочи", "gym": "", "personal_grade": "7b+ trad",
         "achievements_text": "100+ пройденных трад-маршрутов, первопроходы на Кавказе"},
        {"name": "Максим Орлов", "email": "maxim@trainer.ru", "password": "demo123", "role": "trainer",
         "specialization": "multipitch", "disciplines": ["multipitch", "lead"],
         "work_formats": ["outdoor", "gym"], "student_levels": ["intermediate", "advanced"],
         "hourly_rate": 2300, "experience_years": 11, "rating": 4.6, "total_reviews": 19,
         "bio": "Мультипитч: организация станций, смена лидера, спуски. Подготовка к длинным маршрутам от А до Я.",
         "verification_level": 2, "certification": "Инструктор спортивного скалолазания",
         "location": "Красноярск", "gym": "Столбы-outdoor клуб", "personal_grade": "7c",
         "achievements_text": "Восхождения на Столбы, Такын-Тау; гид по Красноярскому краю"},
        {"name": "Игорь Северин", "email": "igor@trainer.ru", "password": "demo123", "role": "trainer",
         "specialization": "ice", "disciplines": ["ice"],
         "work_formats": ["outdoor"], "student_levels": ["beginner", "intermediate", "advanced"],
         "hourly_rate": 2600, "experience_years": 14, "rating": 4.7, "total_reviews": 16,
         "bio": "Ледолазание и драйтулинг: техника кошек и инструментов, ледобуры, безопасность на ледопадах. Зимние выезды.",
         "verification_level": 3, "certification": "Инструктор альпинизма, UIAA Ice Climbing",
         "location": "Екатеринбург", "gym": "", "personal_grade": "WI5 / M7",
         "achievements_text": "Участник чемпионата России по ледолазанию, гид зимних программ"},
        {"name": "Ольга Дорофеева", "email": "olgad@trainer.ru", "password": "demo123", "role": "trainer",
         "specialization": "training", "disciplines": ["training", "bouldering"],
         "work_formats": ["gym", "online"], "student_levels": ["beginner", "intermediate", "advanced", "competition"],
         "hourly_rate": 1500, "experience_years": 8, "rating": 4.8, "total_reviews": 33,
         "bio": "СФП/ОФП для скалолазов: хангборд-программы, антагонисты, профилактика травм пальцев и плеч. Онлайн-ведение.",
         "verification_level": 2, "certification": "МГМСУ, спортивная реабилитация",
         "location": "Москва", "gym": "Rock Zona", "personal_grade": "V7",
         "achievements_text": "Ведёт онлайн-группы СФП 200+ скалолазов"},
        {"name": "Марина Зайцева", "email": "marina@trainer.ru", "password": "demo123", "role": "trainer",
         "specialization": "kids", "disciplines": ["kids", "toprope", "bouldering"],
         "work_formats": ["gym"], "student_levels": ["beginner", "intermediate"],
         "hourly_rate": 1300, "experience_years": 6, "rating": 4.9, "total_reviews": 61,
         "bio": "Детские занятия 5-14 лет: игровые форматы, безопасность, первые соревнования. Диплом педагога-психолога.",
         "verification_level": 3, "certification": "Педагог-психолог, инструктор скалодрома",
         "location": "Санкт-Петербург", "gym": "X8", "personal_grade": "6c",
         "achievements_text": "Воспитанники — призёры первенства города среди юниоров"},
        {"name": "Руслан Агиев", "email": "ruslan@trainer.ru", "password": "demo123", "role": "trainer",
         "specialization": "bouldering", "disciplines": ["bouldering", "lead"],
         "work_formats": ["gym", "outdoor"], "student_levels": ["beginner", "intermediate"],
         "hourly_rate": 1200, "experience_years": 4, "rating": 4.5, "total_reviews": 15,
         "bio": "Боулдеринг для взрослых с нуля. Спокойный темп, много практики, выезды на камни летом.",
         "verification_level": 1, "certification": "Инструктор скалодрома",
         "location": "Казань", "gym": "Грот", "personal_grade": "V6",
         "achievements_text": "Организатор летних боулдеринг-выездов"},
    ]

    trainers = []
    for td in trainers_data:
        td["password_hash"] = hash_password(td.pop("password"))
        t = User(**td)
        db.add(t)
        trainers.append(t)
    db.commit()
    for t in trainers:
        db.refresh(t)

    _seed_demo_bookings_and_reviews(db)
    _seed_demo_products(db, trainers)

    return {"message": "Database seeded with 10 climbing trainers and 12 gear listings"}
