from datetime import (
    datetime,
    timezone
)

from sqlalchemy import (
    CheckConstraint
)

from app.extensions import db


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
        autoincrement=True
    )

    cart_id = db.Column(
        db.BigInteger,
        db.ForeignKey("carts.id"),
        nullable=False,
        index=True
    )

    variant_id = db.Column(
        db.BigInteger,
        db.ForeignKey("product_variants.id"),
        nullable=False,
        index=True
    )

    branch_id = db.Column(
        db.BigInteger,
        db.ForeignKey("store_branches.id"),
        nullable=False,
        index=True
    )

    branch_variant_id = db.Column(
        db.BigInteger,
        db.ForeignKey(
            "branch_product_variants.id"
        ),
        nullable=False,
        index=True
    )

    quantity = db.Column(
        db.Integer,
        nullable=False,
        default=1
    )

    unit_price_snapshot = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    currency = db.Column(
        db.String(10),
        nullable=False,
        default="GBP"
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: (
            datetime.now(timezone.utc)
        )
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: (
            datetime.now(timezone.utc)
        ),
        onupdate=lambda: (
            datetime.now(timezone.utc)
        )
    )

    cart = db.relationship(
        "Cart",
        back_populates="items"
    )

    variant = db.relationship(
        "ProductVariant"
    )

    branch_variant = db.relationship(
        "BranchProductVariant"
    ) 

    __table_args__ = (

        CheckConstraint(
            "quantity > 0",
            name=(
                "ck_cart_item_quantity_positive"
            )
        ),

        db.UniqueConstraint(
            "cart_id",
            "variant_id",
            "branch_id",
            name=(
                "uq_cart_variant_branch"
            )
        ),
    )