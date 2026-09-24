# =========================================================
# PRODUCT VARIANT
# Pricing controlled by Catalogue Manager
# =========================================================

from app.extensions import db


class ProductVariant(db.Model):
    __tablename__ = "product_variants"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
        autoincrement=True
    )

    product_id = db.Column(
        db.BigInteger,
        db.ForeignKey("products.id"),
        nullable=False,
        index=True
    )

    sku = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
        index=True
    )

    # Example:
    # Size -> 500ml
    name = db.Column(db.String(100))
    value = db.Column(db.String(100))

    # GLOBAL PRICE
    selling_price = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )
    #original price shown beside current selling price to indicate a discount or deal
    compare_at_price = db.Column(
        db.Numeric(10, 2)
    )

    is_default = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    product = db.relationship(
        "Product",
        back_populates="variants"
    )

    branch_variants = db.relationship(
        "BranchProductVariant",
        back_populates="variant",
        cascade="all, delete-orphan"
    )

