# =========================================================
# PRODUCT IMAGES
# =========================================================

from datetime import datetime, timezone
from app.extensions import db


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    product_id = db.Column(
        db.BigInteger,
        db.ForeignKey("products.id"),
        nullable=False,
        index=True
    )

    image_url = db.Column(
        db.String(255),
        nullable=False
    )

    is_primary = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    product = db.relationship(
        "Product",
        back_populates="images"
    )