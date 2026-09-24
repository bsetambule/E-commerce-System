from app.extensions import db
from datetime import datetime, timezone

class ProductSearch(db.Model):
    __tablename__ = "product_searches"

    id = db.Column(db.BigInteger, primary_key=True)

    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id"), nullable=True)

    query = db.Column(db.String(255), index=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )