from datetime import datetime, timezone
import enum

from app.extensions import db


class OrderItemStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"
    REFUNDED = "REFUNDED"


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.BigInteger, primary_key=True)

    order_id = db.Column(
        db.BigInteger,
        db.ForeignKey("orders.id"),
        nullable=False,
        index=True
    )

    product_id = db.Column(
        db.BigInteger,
        db.ForeignKey("products.id"),
        nullable=False
    )

    variant_id = db.Column(
        db.BigInteger,
        db.ForeignKey("product_variants.id"),
        nullable=True
    )

    branch_id = db.Column(
        db.BigInteger,
        db.ForeignKey("store_branches.id"),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    # IMMUTABLE SNAPSHOT DATA

    product_name = db.Column(
        db.String(255),
        nullable=False
    )

    variant_name = db.Column(
        db.String(255)
    )

    sku_snapshot = db.Column(
        db.String(100)
    )

    unit_price = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    total_price = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    currency = db.Column(
        db.String(10),
        nullable=False,
        default="GBP"
    )

    status = db.Column(
        db.Enum(OrderItemStatus),
        nullable=False,
        default=OrderItemStatus.PENDING,
        index=True
    )

    carrier = db.Column(db.String(100))
    tracking_number = db.Column(db.String(255))

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
        back_populates="items"
    )

    product = db.relationship(
        "Product",
        backref="order_items"
    )

    variant = db.relationship(
        "ProductVariant",
        backref="order_items"
    )

    __table_args__ = (
        db.CheckConstraint(
            "quantity > 0",
            name="check_quantity_positive"
        ),
    )