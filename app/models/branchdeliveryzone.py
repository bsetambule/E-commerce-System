from datetime import datetime, timezone
from app.extensions import db


class BranchDeliveryZone(db.Model):
    __tablename__ = "branch_delivery_zones"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    branch_id = db.Column(
        db.BigInteger,
        db.ForeignKey("store_branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    delivery_zone_id = db.Column(
        db.BigInteger,
        db.ForeignKey("delivery_zones.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # =====================================================
    # DELIVERY RULES
    # =====================================================

    base_fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    min_order_value = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    free_delivery_threshold = db.Column(db.Numeric(10, 2), nullable=True)

    estimated_delivery_minutes = db.Column(db.Integer, nullable=True)

    max_delivery_distance_km = db.Column(db.Numeric(5, 2), nullable=True)

    # =====================================================
    # OPERATIONS
    # =====================================================

    supports_same_day_delivery = db.Column(db.Boolean, default=True, nullable=False)
    supports_scheduled_delivery = db.Column(db.Boolean, default=True, nullable=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            "branch_id",
            "delivery_zone_id",
            name="uq_branch_delivery_zone"
        ),
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    branch = db.relationship(
        "StoreBranch",
        back_populates="branch_delivery_zones"
    )

    delivery_zone = db.relationship(
        "DeliveryZone",
        back_populates="branch_configs"
    )

    # =====================================================
    # BUSINESS LOGIC
    # =====================================================

    def is_free_delivery(self, order_total):
        if self.free_delivery_threshold is None:
            return False
        return order_total >= self.free_delivery_threshold