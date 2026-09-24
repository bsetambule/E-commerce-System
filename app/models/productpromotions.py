# =========================================================
# PRODUCT PROMOTIONS / DEALS
# Catalogue manager creates promotions
# Store managers activate products in branch
# =========================================================

from datetime import datetime, timezone
from app.extensions import db
import enum


class PromotionType(enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"


class ProductPromotion(db.Model):
    __tablename__ = "product_promotions"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
        autoincrement=True
    )

    branch_product_id = db.Column(
        db.BigInteger,
        db.ForeignKey("branch_products.id"),
        nullable=False,
        index=True
    )

    title = db.Column(
        db.String(255),
        nullable=False
    )

    promotion_type = db.Column(
        db.Enum(PromotionType),
        nullable=False
    )

    value = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    starts_at = db.Column(
        db.DateTime,
        nullable=False
    )

    ends_at = db.Column(
        db.DateTime,
        nullable=False
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False,
        index=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    branch_product = db.relationship(
        "BranchProduct",
        back_populates="promotions"
    )