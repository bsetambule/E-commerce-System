from datetime import datetime, timezone
import enum

from sqlalchemy import CheckConstraint

from app.extensions import db


class InventoryReservationStatus(enum.Enum):
    RESERVED = "RESERVED"
    COMMITTED = "COMMITTED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class InventoryReservation(db.Model):
    __tablename__ = "inventory_reservations"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
        autoincrement=True
    )

    order_id = db.Column(
        db.BigInteger,
        db.ForeignKey("orders.id"),
        nullable=False,
        index=True
    )

    inventory_id = db.Column(
        db.BigInteger,
        db.ForeignKey("inventory.id"),
        nullable=False,
        index=True
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    status = db.Column(
        db.Enum(InventoryReservationStatus),
        nullable=False,
        default=InventoryReservationStatus.RESERVED,
        index=True
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        index=True
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    committed_at = db.Column(
        db.DateTime(timezone=True)
    )

    released_at = db.Column(
        db.DateTime(timezone=True)
    )

    expired_at = db.Column(
        db.DateTime(timezone=True)
    )

    inventory = db.relationship(
        "Inventory",
        back_populates="reservations"
    )

    order = db.relationship(
        "Order",
        backref="inventory_reservations"
    )

    __table_args__ = (

        CheckConstraint(
            "quantity > 0",
            name=(
                "ck_inventory_reservation_quantity_positive"
            )
        ),

        db.UniqueConstraint(
            "order_id",
            "inventory_id",
            name=(
                "uq_inventory_reservation_order_inventory"
            )
        ),
    )