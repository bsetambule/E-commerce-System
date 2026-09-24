from datetime import datetime, timezone
from app.extensions import db


class DeliveryZone(db.Model):
    __tablename__ = "delivery_zones"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    name = db.Column(db.String(100), nullable=False, unique=True, index=True)

    town = db.Column(db.String(100), nullable=True, index=True)
    city = db.Column(db.String(100), nullable=True, index=True)

    covered_areas = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    postcode_prefixes = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False,
        index=True
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    branch_configs = db.relationship(
        "BranchDeliveryZone",
        back_populates="delivery_zone",
        cascade="all, delete-orphan"
    )

    deliveries = db.relationship(
        "Delivery",
        back_populates="delivery_zone"
    )

    # =====================================================
    # HELPERS
    # =====================================================

    def normalised_areas(self):
        return {
            a.strip().lower()
            for a in (self.covered_areas or [])
        }

    def matches_area(self, area: str) -> bool:
        if not area:
            return False
        return area.strip().lower() in self.normalised_areas()