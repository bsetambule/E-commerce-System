# =========================================================
# BRANCH PRODUCT VARIANT
# Store-specific availability only
# NO pricing here anymore
# =========================================================

from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint
from app.extensions import db


class BranchProductVariant(db.Model):
    __tablename__ = "branch_product_variants"

    id = db.Column(db.BigInteger, primary_key=True)
    branch_product_id = db.Column(db.BigInteger, db.ForeignKey("branch_products.id"), nullable=False, index=True)
    variant_id = db.Column(db.BigInteger, db.ForeignKey("product_variants.id"), nullable=False, index=True)
    # REAL AVAILABILITY
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    # FULFILLMENT CONTROL (ONLY HERE)
    allows_pickup = db.Column(db.Boolean, default=True, nullable=False)
    allows_delivery = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    branch_product = db.relationship(
        "BranchProduct",
        back_populates="variants"
    )

    variant = db.relationship(
        "ProductVariant",
        back_populates="branch_variants"
    )

    inventory = db.relationship(
        "Inventory",
        back_populates="branch_variant",
        uselist=False,
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "branch_product_id",
            "variant_id",
            name="uq_branch_variant"
        ),
    )