from datetime import datetime, timezone
import enum

from sqlalchemy import Numeric

from app.extensions import db


class PaymentStatus(enum.Enum):
    INITIATED = "INITIATED"
    REQUIRES_ACTION = "REQUIRES_ACTION"
    PROCESSING = "PROCESSING"
    AUTHORIZED = "AUTHORIZED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"


class PaymentProvider(enum.Enum):
    STRIPE = "STRIPE"


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
        autoincrement=True
    )

    order_id = db.Column(
        db.BigInteger,
        db.ForeignKey("orders.id"),
        nullable=False,
        unique=True,
        index=True
    )

    provider = db.Column(
        db.Enum(PaymentProvider),
        nullable=False,
        default=PaymentProvider.STRIPE
    )

    provider_payment_intent_id = db.Column(
        db.String(255),
        unique=True,
        index=True
    )

    provider_checkout_session_id = db.Column(
        db.String(255),
        unique=True,
        index=True
    )

    amount = db.Column(
        Numeric(12, 2),
        nullable=False
    )

    currency = db.Column(
        db.String(10),
        nullable=False,
        default="GBP"
    )

    status = db.Column(
        db.Enum(PaymentStatus),
        nullable=False,
        default=PaymentStatus.INITIATED,
        index=True
    )

    idempotency_key = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True
    )

    failure_code = db.Column(db.String(255))
    failure_message = db.Column(db.Text)

    paid_at = db.Column(db.DateTime(timezone=True))
    refunded_at = db.Column(db.DateTime(timezone=True))
    cancelled_at = db.Column(db.DateTime(timezone=True))

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    order = db.relationship(
        "Order",
        back_populates="payment"
    )