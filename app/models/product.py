# =========================================================
# PRODUCT
# Catalogue Manager owns:
# - product creation
# - pricing
# - variants
# =========================================================

from datetime import datetime, timezone
from app.extensions import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    name = db.Column(
        db.String(255),
        nullable=False,
        index=True
    )

    description = db.Column(db.Text)

    category = db.Column(
        db.String(100),
        index=True
    )

    brand = db.Column(
        db.String(100),
        index=True
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
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    variants = db.relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan"
    )

    images = db.relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan"
    )

    branch_products = db.relationship(
        "BranchProduct",
        back_populates="product",
        cascade="all, delete-orphan"
    )