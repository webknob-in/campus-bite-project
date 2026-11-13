"""Model factories for the test suite.

Every factory takes the SQLAlchemy ``Session`` as its first argument, builds a row that satisfies
the data invariants of the application, ``flush()``es it (never commits) and returns the ORM
object. Rows are unique by construction (random suffixes), so factories can be called any number
of times in one test, and in every Hypothesis example.

Import in tests::

    from tests.factories import make_customer, make_order, make_restaurant

Every column of every model can be overridden with a keyword argument, for example
``make_user(db, email="a@b.co", phone=None)``. Unknown keywords raise ``TypeError``. Factories that
take related objects accept them as arguments and create a default one when omitted.

Factory                                                       Creates
------------------------------------------------------------  --------------------------------------------
``make_user(db, role=Role.CUSTOMER, **cols)``                 ``User`` with a bcrypt hash of ``DEFAULT_PASSWORD``
``make_customer`` / ``make_owner`` / ``make_partner``         ``make_user`` for one role
``make_restaurant(db, owner=None, **cols)``                   ``Restaurant`` (creates a RESTAURANT_OWNER if ``owner`` is None)
``make_menu_item(db, restaurant=None, **cols)``               ``MenuItem`` (creates a restaurant if None)
``make_order(db, status=..., items=..., ...)``                ``Order`` + ``OrderItem`` rows + PAYMENT ledger row
``make_ledger_entry(db, order=None, entry_type=..., **cols)`` ``PaymentLedger`` row for an order
``make_review(db, order=None, rating=5, **cols)``             ``Review`` for a (DELIVERED by default) order
``make_reminder(db, order=None, **cols)``                     ``AdminReminderLog`` for an order
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AdminReminderLog,
    LedgerType,
    MenuItem,
    Order,
    OrderItem,
    OrderStatus,
    PaymentLedger,
    PaymentStatus,
    Restaurant,
    ReturnStatus,
    Review,
    Role,
    User,
)

DEFAULT_PASSWORD = "Password123!"
CENT = Decimal("0.01")

# Statuses at which an order has necessarily been given to a delivery partner.
_PARTNER_STATUSES = {
    OrderStatus.ASSIGNED,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
    OrderStatus.REFUNDED,
}
# Statuses reached through DELIVERED (``delivered_at`` is set).
_DELIVERED_STATUSES = {OrderStatus.DELIVERED, OrderStatus.REFUNDED}


def _token() -> str:
    return uuid.uuid4().hex


def _money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(CENT)


@lru_cache(maxsize=1)
def _default_password_hash() -> str:
    # bcrypt is deliberately slow; hash the shared test password once per process.
    return hash_password(DEFAULT_PASSWORD)


def _save(db: Session, *rows: Any) -> None:
    db.add_all(rows)
    db.flush()


# --------------------------------------------------------------------------------------- users


def make_user(db: Session, role: Role | str = Role.CUSTOMER, **overrides: Any) -> User:
    """Create a ``User`` with the given ``role``.

    The password is ``DEFAULT_PASSWORD`` unless ``password=...`` is passed (hashed with bcrypt) or
    ``password_hash=...`` is overridden directly. Email is unique and lowercase.
    """
    role = Role(role)
    password = overrides.pop("password", None)
    password_hash = (
        hash_password(password) if password is not None else _default_password_hash()
    )
    suffix = _token()[:10]
    fields: dict[str, Any] = {
        "name": f"{role.value.title().replace('_', ' ')} {suffix[:4]}",
        "email": f"{role.value.lower()}-{suffix}@example.com",
        "password_hash": password_hash,
        "role": role,
        "phone": "9876543210",
        "address": "Hostel 1, Campus Road",
    }
    fields.update(overrides)
    user = User(**fields)
    _save(db, user)
    return user


def make_customer(db: Session, **overrides: Any) -> User:
    """``make_user`` with ``role=CUSTOMER``."""
    return make_user(db, Role.CUSTOMER, **overrides)


def make_owner(db: Session, **overrides: Any) -> User:
    """``make_user`` with ``role=RESTAURANT_OWNER`` (no restaurant; see ``make_restaurant``)."""
    return make_user(db, Role.RESTAURANT_OWNER, **overrides)


def make_partner(db: Session, **overrides: Any) -> User:
    """``make_user`` with ``role=DELIVERY_PARTNER``."""
    return make_user(db, Role.DELIVERY_PARTNER, **overrides)


# --------------------------------------------------------------------------- restaurant, menu


def make_restaurant(db: Session, owner: User | None = None, **overrides: Any) -> Restaurant:
    """Create a ``Restaurant`` owned by ``owner`` (a new RESTAURANT_OWNER user when omitted).

    An owner owns at most one restaurant (unique ``owner_id``), so pass a fresh owner each time.
    ``owner_id`` may also be overridden directly.
    """
    fields: dict[str, Any] = {
        "name": f"Restaurant {_token()[:6]}",
        "description": "Test restaurant serving campus favourites.",
        "cuisine": "Indian",
        "address": "Food Court, Block A",
        "image_url": None,
        "is_open": True,
    }
    fields.update(overrides)
    if "owner_id" not in fields:
        fields["owner_id"] = (owner or make_owner(db)).id
    restaurant = Restaurant(**fields)
    _save(db, restaurant)
    return restaurant


def make_menu_item(db: Session, restaurant: Restaurant | None = None, **overrides: Any) -> MenuItem:
    """Create an available ``MenuItem`` priced 10.00 (a new restaurant when omitted).

    ``price`` accepts ``Decimal``, ``int``, ``float`` or ``str`` and is quantized to 2 places.
    """
    fields: dict[str, Any] = {
        "name": f"Dish {_token()[:6]}",
        "description": "A test dish.",
        "price": Decimal("10.00"),
        "category": "Mains",
        "image_url": None,
        "is_available": True,
    }
    fields.update(overrides)
    fields["price"] = _money(fields["price"])
    if "restaurant_id" not in fields:
        fields["restaurant_id"] = (restaurant or make_restaurant(db)).id
    item = MenuItem(**fields)
    _save(db, item)
    return item


# ------------------------------------------------------------------------------------- orders


def _build_order_items(
    db: Session, items: list[Any] | None, total: Any | None, restaurant: Restaurant | None
) -> tuple[list[OrderItem], Restaurant | None]:
    """Turn the ``items`` spec into ``OrderItem`` rows and work out the restaurant they belong to.

    Each spec is a ``MenuItem`` (quantity 1), a ``(MenuItem, quantity)`` tuple, or a dict with keys
    ``menu_item`` (``MenuItem`` or ``None``), ``name``, ``unit_price``, ``quantity`` and
    ``line_total``. Name and price default to the menu item's snapshot.
    """
    specs = items
    if specs is None:
        if total is not None:
            # Keep the order consistent: one line whose total equals the requested order total.
            specs = [{"menu_item": None, "name": "Custom item", "unit_price": total, "quantity": 1}]
        else:
            if restaurant is None:
                restaurant = make_restaurant(db)
            specs = [(make_menu_item(db, restaurant, price="12.50"), 1)]

    rows: list[OrderItem] = []
    for spec in specs:
        if isinstance(spec, MenuItem):
            spec = {"menu_item": spec, "quantity": 1}
        elif isinstance(spec, tuple):
            spec = {"menu_item": spec[0], "quantity": spec[1]}
        else:
            spec = dict(spec)
        menu_item: MenuItem | None = spec.pop("menu_item", None)
        quantity = int(spec.pop("quantity", 1))
        unit_price = _money(
            spec.pop("unit_price", menu_item.price if menu_item is not None else Decimal("10.00"))
        )
        name = spec.pop("name", menu_item.name if menu_item is not None else f"Item {_token()[:6]}")
        line_total = _money(spec.pop("line_total", unit_price * quantity))
        if restaurant is None and menu_item is not None:
            restaurant = db.get(Restaurant, menu_item.restaurant_id)
        rows.append(
            OrderItem(
                menu_item_id=menu_item.id if menu_item is not None else None,
                name=name,
                unit_price=unit_price,
                quantity=quantity,
                line_total=line_total,
                **spec,
            )
        )
    return rows, restaurant


def make_order(
    db: Session,
    status: OrderStatus | str = OrderStatus.PLACED,
    *,
    items: list[Any] | None = None,
    total: Any | None = None,
    customer: User | None = None,
    restaurant: Restaurant | None = None,
    partner: User | None | bool = None,
    return_status: ReturnStatus | str | None = None,
    payment_status: PaymentStatus | str | None = None,
    created_at: datetime | None = None,
    status_updated_at: datetime | None = None,
    with_ledger: bool = True,
    **overrides: Any,
) -> Order:
    """Create an ``Order`` with its ``OrderItem`` rows and a PAYMENT ledger entry.

    Arguments (all optional):

    * ``status``: any ``OrderStatus``; the other fields are made consistent with it.
    * ``items``: list of ``MenuItem`` | ``(MenuItem, quantity)`` | dict (see ``_build_order_items``).
      Default: one new menu item (12.50) x 1 in ``restaurant`` (created when omitted).
    * ``total``: ``total_amount``. Default: the sum of line totals. When given without ``items`` the
      single default line is priced at ``total`` so that the sum invariant still holds. When given
      together with ``items`` the caller opts out of the sum invariant.
    * ``customer`` / ``restaurant``: created when omitted (restaurant is taken from the first menu
      item in ``items`` when not given).
    * ``partner``: ``delivery_partner``. ``None`` creates one when ``status`` is ASSIGNED,
      OUT_FOR_DELIVERY, DELIVERED or REFUNDED and none otherwise; ``False`` forces no partner.
    * ``return_status``: default ``none``, or ``approved`` for REFUNDED. Anything other than
      ``none`` also sets ``return_requested_at`` and ``return_reason``.
    * ``payment_status``: default ``mock_paid``, or ``refunded`` for REFUNDED. Orders that are
      ``refunded`` also get a REFUND ledger entry for the full total.
    * ``created_at`` (default now, UTC) and ``status_updated_at`` (default ``created_at``);
      ``updated_at`` follows ``status_updated_at`` and ``delivered_at`` is set to it for DELIVERED
      and REFUNDED orders. Pass ``delivered_at=...`` in ``overrides`` to change that.
    * ``with_ledger``: ``False`` skips every ledger entry.
    * ``**overrides``: any other ``Order`` column (``delivery_address``, ``return_reason``, ...).

    The PAYMENT entry has ``amount == total_amount``, status ``success`` (``pending`` for a pending
    order) and a unique ``transaction_ref``.
    """
    status = OrderStatus(status)
    customer = customer or make_customer(db)
    order_items, restaurant = _build_order_items(db, items, total, restaurant)
    restaurant = restaurant or make_restaurant(db)

    total_amount = _money(total) if total is not None else sum(
        (i.line_total for i in order_items), Decimal("0.00")
    )

    if partner is None and status in _PARTNER_STATUSES:
        partner = make_partner(db)
    delivery_partner_id = partner.id if isinstance(partner, User) else None

    if payment_status is None:
        payment_status = (
            PaymentStatus.refunded if status is OrderStatus.REFUNDED else PaymentStatus.mock_paid
        )
    payment_status = PaymentStatus(payment_status)
    if return_status is None:
        return_status = (
            ReturnStatus.approved if status is OrderStatus.REFUNDED else ReturnStatus.none
        )
    return_status = ReturnStatus(return_status)

    created_at = created_at or datetime.now(timezone.utc)
    status_updated_at = status_updated_at or created_at

    fields: dict[str, Any] = {
        "customer_id": customer.id,
        "restaurant_id": restaurant.id,
        "delivery_partner_id": delivery_partner_id,
        "status": status,
        "total_amount": total_amount,
        "delivery_address": "Hostel 1, Room 101, Campus Road",
        "delivery_phone": "9876543210",
        "payment_status": payment_status,
        "return_status": return_status,
        "return_reason": None,
        "return_requested_at": None,
        "created_at": created_at,
        "updated_at": status_updated_at,
        "status_updated_at": status_updated_at,
        "delivered_at": status_updated_at if status in _DELIVERED_STATUSES else None,
    }
    if return_status is not ReturnStatus.none:
        fields["return_reason"] = "Food arrived cold."
        fields["return_requested_at"] = status_updated_at
    fields.update(overrides)

    order = Order(**fields)
    order.items = order_items
    _save(db, order)

    if with_ledger:
        paid = order.payment_status in (PaymentStatus.mock_paid, PaymentStatus.refunded)
        make_ledger_entry(
            db,
            order,
            LedgerType.PAYMENT,
            status="success" if paid else "pending",
            created_at=created_at,
        )
        if order.payment_status is PaymentStatus.refunded:
            make_ledger_entry(db, order, LedgerType.REFUND, created_at=status_updated_at)
        db.refresh(order, attribute_names=["ledger_entries"])
    return order


# --------------------------------------------------------------------- ledger, review, reminder


def make_ledger_entry(
    db: Session,
    order: Order | None = None,
    entry_type: LedgerType | str = LedgerType.PAYMENT,
    **overrides: Any,
) -> PaymentLedger:
    """Create a ``PaymentLedger`` row for ``order`` (a new PLACED order without ledger if None).

    Defaults: ``amount`` = the order total, ``status`` = ``success``, a unique ``transaction_ref``
    (``MOCK-...`` for PAYMENT, ``MOCK-REF-...`` for REFUND) and ``card_last4`` = ``4242`` for PAYMENT
    entries (``None`` for REFUND).
    """
    entry_type = LedgerType(entry_type)
    if order is None:
        order = make_order(db, with_ledger=False)
    is_payment = entry_type is LedgerType.PAYMENT
    fields: dict[str, Any] = {
        "order_id": order.id,
        "entry_type": entry_type,
        "amount": order.total_amount,
        "status": "success",
        "transaction_ref": (
            f"MOCK-{_token()[:12].upper()}" if is_payment else f"MOCK-REF-{_token()[:10].upper()}"
        ),
        "card_last4": "4242" if is_payment else None,
    }
    fields.update(overrides)
    fields["amount"] = _money(fields["amount"])
    entry = PaymentLedger(**fields)
    _save(db, entry)
    return entry


def make_review(
    db: Session, order: Order | None = None, rating: int = 5, **overrides: Any
) -> Review:
    """Create a ``Review`` for ``order`` (a new DELIVERED order when omitted).

    ``customer_id`` and ``restaurant_id`` are taken from the order, which keeps the review
    consistent with it. There is at most one review per order.
    """
    if order is None:
        order = make_order(db, OrderStatus.DELIVERED)
    fields: dict[str, Any] = {
        "order_id": order.id,
        "customer_id": order.customer_id,
        "restaurant_id": order.restaurant_id,
        "rating": rating,
        "comment": "Tasty and on time.",
    }
    fields.update(overrides)
    review = Review(**fields)
    _save(db, review)
    return review


def make_reminder(db: Session, order: Order | None = None, **overrides: Any) -> AdminReminderLog:
    """Create an ``AdminReminderLog`` for ``order`` (a new PLACED order when omitted).

    ``status_at_reminder`` defaults to the order's current status and ``restaurant_id`` to the
    order's restaurant. ``is_resolved`` defaults to ``False``. There is at most one reminder per
    ``(order, status_at_reminder)``.
    """
    if order is None:
        order = make_order(db, OrderStatus.PLACED)
    status_at_reminder = OrderStatus(overrides.pop("status_at_reminder", order.status))
    fields: dict[str, Any] = {
        "order_id": order.id,
        "restaurant_id": order.restaurant_id,
        "status_at_reminder": status_at_reminder,
        "message": f"Order #{order.id} has been {status_at_reminder.value} for too long.",
        "is_resolved": False,
    }
    fields.update(overrides)
    reminder = AdminReminderLog(**fields)
    _save(db, reminder)
    return reminder
