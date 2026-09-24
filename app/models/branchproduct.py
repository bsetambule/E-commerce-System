# =========================================================
# BRANCH PRODUCT
# Store Manager controls:
# - visibility in branch
# - availability in branch
# =========================================================

from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint
from app.extensions import db


class BranchProduct(db.Model):
    __tablename__ = "branch_products"

    id = db.Column(db.BigInteger, primary_key=True)

    branch_id = db.Column(db.BigInteger, db.ForeignKey("store_branches.id"), nullable=False, index=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), nullable=False, index=True)
    # ONLY VISIBILITY / MERCHANDISING
    is_visible = db.Column(db.Boolean, default=True, nullable=False)
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    branch = db.relationship(
        "StoreBranch",
        back_populates="branch_products"
    )

    product = db.relationship(
        "Product",
        back_populates="branch_products"
    )

    variants = db.relationship(
        "BranchProductVariant",
        back_populates="branch_product",
        cascade="all, delete-orphan"
    )

    promotions = db.relationship(
        "ProductPromotion",
        back_populates="branch_product",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "branch_id",
            "product_id",
            name="uq_branch_product"
        ),
    )