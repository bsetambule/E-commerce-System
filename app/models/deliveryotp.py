from datetime import (
    datetime,
    timedelta,
    timezone
)

import enum

from app.extensions import db


class DeliveryOtpType(enum.Enum):

    PICKUP = "PICKUP"

    DELIVERY = "DELIVERY"


class DeliveryOtp(db.Model):
    __tablename__ = "delivery_otps"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
        autoincrement=True
    )

    delivery_id = db.Column(
        db.BigInteger,
        db.ForeignKey("deliveries.id"),
        index=True
    )

    order_id = db.Column(
        db.BigInteger,
        db.ForeignKey("orders.id"),
        nullable=False,
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

    otp_type = db.Column(
        db.Enum(DeliveryOtpType),
        nullable=False,
        index=True
    )

    otp_code_hash = db.Column(
        db.String(255),
        nullable=False
    )

    is_verified = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    is_invalidated = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    attempts = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    max_attempts = db.Column(
        db.Integer,
        nullable=False,
        default=5
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: (
            datetime.now(timezone.utc)
            + timedelta(minutes=15)
        )
    )

    verified_at = db.Column(
        db.DateTime(timezone=True)
    )

    invalidated_at = db.Column(
        db.DateTime(timezone=True)
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: (
            datetime.now(timezone.utc)
        )
    )

    order = db.relationship(
        "Order",
        back_populates="delivery_otps"
    )

    branch = db.relationship(
        "StoreBranch",
        back_populates="delivery_otps"
    )

    delivery = db.relationship(
        "Delivery",
        back_populates="otps"
    )

    courier = db.relationship(
        "User",
        foreign_keys=[courier_id]
    )

    __table_args__ = (

        db.UniqueConstraint(
            "order_id",
            "otp_type",
            "is_verified",
            "is_invalidated",
            name="uq_active_order_otp"
        ),
    )