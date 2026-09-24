from datetime import datetime, timezone

from app.extensions import db


class StoreBranch(db.Model):
    __tablename__ = "store_branches"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
        autoincrement=True
    )

    # =====================================================
    # BASIC INFO
    # =====================================================

    name = db.Column(
        db.String(100),
        nullable=False,
        index=True
    )

    phone_number = db.Column(
        db.String(30),
        nullable=True
    )

    email = db.Column(
        db.String(120),
        nullable=True
    )

    # =====================================================
    # LOCATION
    # =====================================================

    plot_number = db.Column(
        db.String(50),
        nullable=True
    )

    area = db.Column(
        db.String(100),
        nullable=True,
        index=True
    )

    town = db.Column(
        db.String(100),
        nullable=False,
        index=True
    )

    city = db.Column(
        db.String(100),
        nullable=True,
        index=True
    )

    country = db.Column(
        db.String(100),
        nullable=False,
        default="Botswana"
    )

    postal_code = db.Column(
        db.String(20),
        nullable=True,
        index=True
    )

    latitude = db.Column(
        db.Float,
        nullable=True
    )

    longitude = db.Column(
        db.Float,
        nullable=True
    )

    # =====================================================
    # STORE SETTINGS
    # =====================================================

    allows_delivery = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    allows_pickup = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    # Example:
    # {
    #   "monday": {"open": "08:00", "close": "22:00"},
    #   "tuesday": {"open": "08:00", "close": "22:00"}
    # }
    operating_hours = db.Column(
        db.JSON,
        nullable=True
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False,
        index=True
    )

    is_deleted = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    branch_delivery_zones = db.relationship(
        "BranchDeliveryZone",
        back_populates="branch",
        cascade="all, delete-orphan"
    )

    branch_products = db.relationship(
        "BranchProduct",
        back_populates="branch",
        cascade="all, delete-orphan"
    )

    deliveries = db.relationship(
        "Delivery",
        back_populates="branch"
    )

    staff_members = db.relationship(
        "BranchStaff",
        back_populates="branch"
    )

    orders = db.relationship(
        "Order",
        back_populates="branch"
    )

    delivery_otps = db.relationship(
        "DeliveryOtp",
        back_populates="branch"
    )