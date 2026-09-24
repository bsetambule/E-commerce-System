from datetime import datetime, timezone
import enum

from app.extensions import db


class DeliveryStatus(enum.Enum):

    UNASSIGNED = "UNASSIGNED"

    ASSIGNED = "ASSIGNED"

    ACCEPTED = "ACCEPTED"

    ARRIVED_AT_PICKUP = (
        "ARRIVED_AT_PICKUP"
    )

    PICKED_UP = "PICKED_UP"

    IN_TRANSIT = "IN_TRANSIT"

    OUT_FOR_DELIVERY = (
        "OUT_FOR_DELIVERY"
    )

    DELIVERED = "DELIVERED"

    CANCELLED = "CANCELLED"

    FAILED = "FAILED"

    RETURNED = "RETURNED"


class Delivery(db.Model):
    __tablename__ = "deliveries"

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

    branch_id = db.Column(
        db.BigInteger,
        db.ForeignKey("store_branches.id"),
        nullable=False,
        index=True
    )

    courier_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id"),
        index=True
    )

    status = db.Column(
        db.Enum(DeliveryStatus),
        nullable=False,
        default=DeliveryStatus.UNASSIGNED,
        index=True
    )

    delivery_zone_id = db.Column(
        db.BigInteger,
        db.ForeignKey("delivery_zones.id"),
        index=True
    )

    delivery_zone_name = db.Column(
        db.String(100)
    )

    delivery_fee_applied = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    # IMMUTABLE SNAPSHOT
    delivery_address_snapshot = db.Column(
        db.JSON,
        nullable=False
    )

    assigned_at = db.Column(
        db.DateTime(timezone=True)
    )

    accepted_at = db.Column(
        db.DateTime(timezone=True)
    )

    picked_up_at = db.Column(
        db.DateTime(timezone=True)
    )

    out_for_delivery_at = db.Column(
        db.DateTime(timezone=True)
    )

    delivered_at = db.Column(
        db.DateTime(timezone=True)
    )

    failed_at = db.Column(
        db.DateTime(timezone=True)
    )

    cancelled_at = db.Column(
        db.DateTime(timezone=True)
    )

    returned_at = db.Column(
        db.DateTime(timezone=True)
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: (
            datetime.now(timezone.utc)
        )
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: (
            datetime.now(timezone.utc)
        ),
        onupdate=lambda: (
            datetime.now(timezone.utc)
        )
    )

    order = db.relationship(
        "Order",
        back_populates="delivery"
    )

    branch = db.relationship(
        "StoreBranch",
        back_populates="deliveries"
    )

    courier = db.relationship(
        "User",
        foreign_keys=[courier_id]
    )

    delivery_zone = db.relationship(
        "DeliveryZone",
        back_populates="deliveries"
    )

    otps = db.relationship(
        "DeliveryOtp",
        back_populates="delivery",
        cascade="all, delete-orphan"
    )