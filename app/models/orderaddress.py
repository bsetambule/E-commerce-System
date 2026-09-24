from datetime import datetime, timezone
from app.extensions import db


class OrderAddress(db.Model):
    __tablename__ = "order_addresses"

    id = db.Column(db.BigInteger, primary_key=True)

    order_id = db.Column(
        db.BigInteger,
        db.ForeignKey("orders.id"),
        nullable=False,
        unique=True
    )

    # =====================================================
    # CONTACT INFO
    # =====================================================

    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(30), nullable=False)

    # =====================================================
    # DELIVERY LOCATION
    # =====================================================

    city = db.Column(db.String(100), index=True)
    region = db.Column(db.String(100), index=True)

    area = db.Column(db.String(100), nullable=False, index=True)

    # MUST be non-null because you rely on matching
    area_normalized = db.Column(db.String(100), nullable=False, index=True)

    plot_number = db.Column(db.String(100), nullable=False)

    delivery_notes = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    order = db.relationship(
        "Order",
        back_populates="address"
    )

    # =====================================================
    # HELPERS
    # =====================================================

    @staticmethod
    def normalise_area(value: str) -> str:
        return (value or "").strip().lower()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if self.area:
            self.area_normalized = self.normalise_area(self.area)