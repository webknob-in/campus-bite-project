"""Enumerations shared by the ORM models.

Each enum is stored as a native PostgreSQL enum type (see the ``SAEnum(..., name=...)``
columns in the model modules). Member names equal member values, so the labels written to
the database match the values exposed through the API.
"""

from enum import Enum


class Role(str, Enum):
    CUSTOMER = "CUSTOMER"
    RESTAURANT_OWNER = "RESTAURANT_OWNER"
    DELIVERY_PARTNER = "DELIVERY_PARTNER"


class OrderStatus(str, Enum):
    PLACED = "PLACED"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    READY = "READY"
    ASSIGNED = "ASSIGNED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class PaymentStatus(str, Enum):
    pending = "pending"
    mock_paid = "mock_paid"
    refunded = "refunded"


class ReturnStatus(str, Enum):
    none = "none"
    requested = "requested"
    approved = "approved"
    rejected = "rejected"


class LedgerType(str, Enum):
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
