"""Idempotent demo-data seed (Requirement 42).

Run from ``backend/``::

    python -m scripts.seed
    docker compose exec api python -m scripts.seed

Every record is looked up by a natural key before it is created, so a rerun creates nothing
and leaves existing rows unchanged:

* Users by (lowercased) email
* Restaurants by owner
* Menu_Items by (restaurant, name)
* Orders by the ``transaction_ref`` of their PAYMENT ledger row (``SEED-<order-key>-PAYMENT``)
* Reviews by order

Sample orders are written directly (bypassing the endpoints and the state machine), but keep
the same invariants: totals equal the sum of the item snapshots, ``delivered_at`` is set for
``DELIVERED``/``REFUNDED``, a refunded order has ``return_status=approved``,
``payment_status=refunded`` and a REFUND ledger row.

``seed(db)`` flushes but does not commit, so tests can call it on their own session;
``main()`` opens a ``SessionLocal`` session and commits once at the end.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import utcnow
from app.models.enums import LedgerType, OrderStatus, PaymentStatus, ReturnStatus, Role
from app.models.menu_item import MenuItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment_ledger import PaymentLedger
from app.models.restaurant import Restaurant
from app.models.review import Review
from app.models.user import User

DEMO_PASSWORD = "Password123!"
CENT = Decimal("0.01")

# (key, name, email, phone, address)
CUSTOMERS = [
    ("alice", "Alice Customer", "alice@campusbite.example.com", "9000000001", "Hostel 4, Room 210, Campus"),
    ("bob", "Bob Customer", "bob@campusbite.example.com", "9000000002", "Hostel 7, Room 105, Campus"),
]
PARTNERS = [
    ("dave", "Dave Rider", "dave@campusbite.example.com", "9000000011", None),
    ("erin", "Erin Rider", "erin@campusbite.example.com", "9000000012", None),
]

# Each restaurant: owner (name, email, phone), details, and dishes
# (name, description, price, category, is_available).
RESTAURANTS: list[dict[str, Any]] = [
    {
        "key": "curry",
        "owner": ("Priya Owner", "owner.curry@campusbite.example.com", "9000000021"),
        "name": "Campus Curry House",
        "description": "Home-style North Indian curries, breads and rice bowls.",
        "cuisine": "Indian",
        "address": "Food Court, Block A, Campus",
        "dishes": [
            ("Butter Chicken", "Creamy tomato gravy with tender chicken", "220.00", "Mains", True),
            ("Paneer Tikka Masala", "Grilled paneer in spiced masala", "190.00", "Mains", True),
            ("Dal Tadka", "Yellow lentils tempered with garlic and cumin", "120.00", "Mains", True),
            ("Garlic Naan", "Tandoori flatbread with garlic butter", "40.00", "Breads", True),
            ("Veg Biryani", "Fragrant basmati rice with vegetables", "150.00", "Rice", True),
            ("Gulab Jamun", "Two warm syrup-soaked dumplings", "60.00", "Dessert", False),
        ],
    },
    {
        "key": "burgers",
        "owner": ("Rahul Owner", "owner.burgers@campusbite.example.com", "9000000022"),
        "name": "Byte Burgers",
        "description": "Smash burgers, fries and shakes for late-night study sessions.",
        "cuisine": "American",
        "address": "Food Court, Block B, Campus",
        "dishes": [
            ("Classic Cheeseburger", "Beef patty, cheddar, pickles, house sauce", "180.00", "Burgers", True),
            ("Crispy Chicken Burger", "Buttermilk fried chicken with slaw", "170.00", "Burgers", True),
            ("Veggie Burger", "Black bean and corn patty", "140.00", "Burgers", True),
            ("Loaded Fries", "Fries with cheese sauce and jalapenos", "110.00", "Sides", True),
            ("Chocolate Shake", "Thick chocolate milkshake", "120.00", "Drinks", True),
        ],
    },
    {
        "key": "noodles",
        "owner": ("Mei Owner", "owner.noodles@campusbite.example.com", "9000000023"),
        "name": "Noodle Lab",
        "description": "Wok-tossed noodles, ramen and dumplings.",
        "cuisine": "Asian",
        "address": "Food Court, Block C, Campus",
        "dishes": [
            ("Chicken Ramen", "Rich broth, noodles, egg and chicken", "210.00", "Ramen", True),
            ("Veg Hakka Noodles", "Stir-fried noodles with vegetables", "130.00", "Noodles", True),
            ("Schezwan Fried Rice", "Spicy fried rice with garlic", "140.00", "Rice", True),
            ("Steamed Momos", "Six pieces with chilli dip", "100.00", "Starters", True),
            ("Iced Lemon Tea", "Chilled tea with lemon", "70.00", "Drinks", True),
        ],
    },
]

# Sample orders. ``items`` are (dish name, quantity). ``age_min`` is the order's age in minutes
# when first seeded; ``status_age_min`` the minutes since its last status change.
ORDERS: list[dict[str, Any]] = [
    {"key": "placed", "restaurant": "curry", "customer": "alice", "status": OrderStatus.PLACED,
     "items": [("Butter Chicken", 1), ("Garlic Naan", 2)], "age_min": 30, "status_age_min": 30,
     "card_last4": "4242"},
    {"key": "accepted", "restaurant": "burgers", "customer": "bob", "status": OrderStatus.ACCEPTED,
     "items": [("Classic Cheeseburger", 2), ("Loaded Fries", 1)], "age_min": 20, "status_age_min": 10,
     "card_last4": "1111"},
    {"key": "ready", "restaurant": "noodles", "customer": "alice", "status": OrderStatus.READY,
     "items": [("Chicken Ramen", 1), ("Steamed Momos", 1)], "age_min": 45, "status_age_min": 5,
     "card_last4": "4242"},
    {"key": "assigned", "restaurant": "curry", "customer": "bob", "status": OrderStatus.ASSIGNED,
     "partner": "dave", "items": [("Veg Biryani", 2), ("Dal Tadka", 1)], "age_min": 60,
     "status_age_min": 8, "card_last4": "1111"},
    {"key": "delivered", "restaurant": "burgers", "customer": "alice", "status": OrderStatus.DELIVERED,
     "partner": "dave", "items": [("Crispy Chicken Burger", 1), ("Chocolate Shake", 1)],
     "age_min": 24 * 60, "status_age_min": 23 * 60, "card_last4": "4242",
     "review": (5, "Hot, fresh and delivered fast. Great burger!")},
    {"key": "cancelled", "restaurant": "noodles", "customer": "bob", "status": OrderStatus.CANCELLED,
     "items": [("Veg Hakka Noodles", 2)], "age_min": 2 * 24 * 60, "status_age_min": 2 * 24 * 60 - 5,
     "card_last4": "1111"},
    {"key": "refunded", "restaurant": "curry", "customer": "alice", "status": OrderStatus.REFUNDED,
     "partner": "erin", "items": [("Paneer Tikka Masala", 1), ("Garlic Naan", 1)],
     "age_min": 3 * 24 * 60, "status_age_min": 2 * 24 * 60, "card_last4": "4242",
     "return_reason": "Food arrived cold and the packaging was damaged."},
]


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT)


def _get_or_create_user(
    db: Session, counts: dict[str, int], *, name: str, email: str, role: Role,
    phone: str | None, address: str | None, password_hash: str,
) -> User:
    email = email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            name=name, email=email, password_hash=password_hash, role=role,
            phone=phone, address=address,
        )
        db.add(user)
        db.flush()
        counts["users"] += 1
    return user


def _get_or_create_restaurant(
    db: Session, counts: dict[str, int], owner: User, spec: dict[str, Any]
) -> Restaurant:
    restaurant = db.scalar(select(Restaurant).where(Restaurant.owner_id == owner.id))
    if restaurant is None:
        restaurant = Restaurant(
            owner_id=owner.id, name=spec["name"], description=spec["description"],
            cuisine=spec["cuisine"], address=spec["address"], is_open=True,
        )
        db.add(restaurant)
        db.flush()
        counts["restaurants"] += 1
    return restaurant


def _get_or_create_dish(
    db: Session, counts: dict[str, int], restaurant: Restaurant, dish: tuple
) -> MenuItem:
    name, description, price, category, is_available = dish
    item = db.scalar(
        select(MenuItem).where(MenuItem.restaurant_id == restaurant.id, MenuItem.name == name)
    )
    if item is None:
        item = MenuItem(
            restaurant_id=restaurant.id, name=name, description=description,
            price=_money(Decimal(price)), category=category, is_available=is_available,
        )
        db.add(item)
        db.flush()
        counts["menu_items"] += 1
    return item


def _ref(order_key: str, kind: str) -> str:
    return f"SEED-{order_key.upper()}-{kind}"  # at most 40 chars (transaction_ref column)


def _seed_order(
    db: Session, counts: dict[str, int], spec: dict[str, Any], now: datetime,
    restaurants: dict[str, Restaurant], dishes: dict[tuple[str, str], MenuItem],
    customers: dict[str, User], partners: dict[str, User],
) -> None:
    payment_ref = _ref(spec["key"], "PAYMENT")
    existing = db.scalar(select(PaymentLedger).where(PaymentLedger.transaction_ref == payment_ref))
    if existing is not None:
        order = db.get(Order, existing.order_id)
        _seed_review(db, counts, spec, order, now)
        return

    restaurant = restaurants[spec["restaurant"]]
    customer = customers[spec["customer"]]
    status: OrderStatus = spec["status"]
    created_at = now - timedelta(minutes=spec["age_min"])
    status_updated_at = now - timedelta(minutes=spec["status_age_min"])

    lines: list[OrderItem] = []
    for dish_name, quantity in spec["items"]:
        menu_item = dishes[(spec["restaurant"], dish_name)]
        unit_price = _money(menu_item.price)
        lines.append(
            OrderItem(
                menu_item_id=menu_item.id, name=menu_item.name, unit_price=unit_price,
                quantity=quantity, line_total=_money(unit_price * quantity),
            )
        )
    total = _money(sum((line.line_total for line in lines), Decimal("0")))

    refunded = status is OrderStatus.REFUNDED
    order = Order(
        customer_id=customer.id,
        restaurant_id=restaurant.id,
        delivery_partner_id=partners[spec["partner"]].id if "partner" in spec else None,
        status=status,
        total_amount=total,
        delivery_address=customer.address or "Campus",
        delivery_phone=customer.phone or "9000000000",
        payment_status=PaymentStatus.refunded if refunded else PaymentStatus.mock_paid,
        return_status=ReturnStatus.approved if refunded else ReturnStatus.none,
        return_reason=spec.get("return_reason"),
        return_requested_at=(status_updated_at - timedelta(hours=2)) if refunded else None,
        created_at=created_at,
        updated_at=status_updated_at,
        status_updated_at=status_updated_at,
        delivered_at=(
            status_updated_at - timedelta(hours=3) if refunded
            else status_updated_at if status is OrderStatus.DELIVERED
            else None
        ),
        items=lines,
    )
    db.add(order)
    db.flush()
    counts["orders"] += 1
    counts["order_items"] += len(lines)

    db.add(
        PaymentLedger(
            order_id=order.id, entry_type=LedgerType.PAYMENT, amount=total, status="success",
            transaction_ref=payment_ref, card_last4=spec["card_last4"], created_at=created_at,
        )
    )
    counts["payment_ledger"] += 1
    if refunded:
        db.add(
            PaymentLedger(
                order_id=order.id, entry_type=LedgerType.REFUND, amount=total, status="success",
                transaction_ref=_ref(spec["key"], "REFUND"), card_last4=None,
                created_at=status_updated_at,
            )
        )
        counts["payment_ledger"] += 1
    db.flush()
    _seed_review(db, counts, spec, order, now)


def _seed_review(
    db: Session, counts: dict[str, int], spec: dict[str, Any], order: Order, now: datetime
) -> None:
    if "review" not in spec:
        return
    if db.scalar(select(Review.id).where(Review.order_id == order.id)) is not None:
        return
    rating, comment = spec["review"]
    db.add(
        Review(
            order_id=order.id, customer_id=order.customer_id, restaurant_id=order.restaurant_id,
            rating=rating, comment=comment, created_at=order.status_updated_at,
        )
    )
    db.flush()
    counts["reviews"] += 1


def seed(db: Session) -> dict[str, Any]:
    """Create any missing demo records on ``db`` (flush only, no commit).

    Returns ``{"created": {table: n, ...}, "credentials": [{...}, ...]}``. On a rerun every
    count in ``created`` is zero.
    """
    now = utcnow()
    counts = {
        "users": 0, "restaurants": 0, "menu_items": 0, "orders": 0,
        "order_items": 0, "payment_ledger": 0, "reviews": 0,
    }
    password_hash: str | None = None

    def hashed() -> str:
        # Hash lazily: bcrypt is slow and a rerun finds every user already present.
        nonlocal password_hash
        if password_hash is None:
            password_hash = hash_password(DEMO_PASSWORD)
        return password_hash

    credentials: list[dict[str, str]] = []

    def ensure_user(name: str, email: str, role: Role, phone: str | None, address: str | None) -> User:
        email = email.lower()
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = _get_or_create_user(
                db, counts, name=name, email=email, role=role, phone=phone, address=address,
                password_hash=hashed(),
            )
        credentials.append({"role": role.value, "name": name, "email": email, "password": DEMO_PASSWORD})
        return user

    restaurants: dict[str, Restaurant] = {}
    dishes: dict[tuple[str, str], MenuItem] = {}
    for spec in RESTAURANTS:
        owner_name, owner_email, owner_phone = spec["owner"]
        owner = ensure_user(owner_name, owner_email, Role.RESTAURANT_OWNER, owner_phone, None)
        restaurant = _get_or_create_restaurant(db, counts, owner, spec)
        restaurants[spec["key"]] = restaurant
        for dish in spec["dishes"]:
            dishes[(spec["key"], dish[0])] = _get_or_create_dish(db, counts, restaurant, dish)

    partners = {
        key: ensure_user(name, email, Role.DELIVERY_PARTNER, phone, address)
        for key, name, email, phone, address in PARTNERS
    }
    customers = {
        key: ensure_user(name, email, Role.CUSTOMER, phone, address)
        for key, name, email, phone, address in CUSTOMERS
    }

    for order_spec in ORDERS:
        _seed_order(db, counts, order_spec, now, restaurants, dishes, customers, partners)

    return {"created": counts, "credentials": credentials}


def _print_credentials(credentials: list[dict[str, str]]) -> None:
    print("\nDemo credentials (password for every account: " + DEMO_PASSWORD + ")")
    print(f"{'ROLE':<18} {'EMAIL':<42} PASSWORD")
    for cred in credentials:
        print(f"{cred['role']:<18} {cred['email']:<42} {cred['password']}")


def main() -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        result = seed(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    created = result["created"]
    total_created = sum(created.values())
    if total_created:
        print("Seed complete. Created: " + ", ".join(f"{n} {t}" for t, n in created.items() if n))
    else:
        print("Seed data already present; nothing created.")
    _print_credentials(result["credentials"])


if __name__ == "__main__":
    main()
