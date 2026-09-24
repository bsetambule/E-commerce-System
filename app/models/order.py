from datetime import datetime, timezone
import enum

from sqlalchemy import CheckConstraint

from app.extensions import db


class OrderStatus(enum.Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    PAID = "PAID"
    FULFILLMENT_PENDING = "FULFILLMENT_PENDING"
    PROCESSING = "PROCESSING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(32),
        unique=True,
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    branch_id = db.Column(
        db.BigInteger,
        db.ForeignKey("store_branches.id"),
        nullable=False,
        index=True
    )

    # INTERNAL ORDER SNAPSHOT TOTALS

    subtotal_amount = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    tax_amount = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    discount_amount = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    delivery_fee = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    grand_total = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    currency = db.Column(
        db.String(10),
        nullable=False,
        default="GBP"
    )

    status = db.Column(
        db.Enum(OrderStatus),
        nullable=False,
        default=OrderStatus.PENDING_PAYMENT,
        index=True
    )

    is_delivery = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    # IDEMPOTENCY + RECOVERY

    idempotency_key = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True
    )

    # PAYMENT LIFECYCLE

    payment_processing_started_at = db.Column(db.DateTime(timezone=True))
    paid_at = db.Column(db.DateTime(timezone=True))
    cancelled_at = db.Column(db.DateTime(timezone=True))
    refunded_at = db.Column(db.DateTime(timezone=True))

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # RELATIONSHIPS

    user = db.relationship("User", backref="orders")

    branch = db.relationship(
        "StoreBranch",
        back_populates="orders"
    )

    items = db.relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )

    payment = db.relationship(
        "Payment",
        back_populates="order",
        uselist=False
    )

    delivery = db.relationship(
        "Delivery",
        back_populates="order",
        uselist=False
    )

    address = db.relationship(
        "OrderAddress",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan"
    )

    delivery_otps = db.relationship(
        "DeliveryOtp",
        back_populates="order",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "subtotal_amount >= 0",
            name="ck_order_subtotal_non_negative"
        ),
        CheckConstraint(
            "tax_amount >= 0",
            name="ck_order_tax_non_negative"
        ),
        CheckConstraint(
            "discount_amount >= 0",
            name="ck_order_discount_non_negative"
        ),
        CheckConstraint(
            "delivery_fee >= 0",
            name="ck_order_delivery_fee_non_negative"
        ),
        CheckConstraint(
            "grand_total >= 0",
            name="ck_order_grand_total_non_negative"
        ),
    )