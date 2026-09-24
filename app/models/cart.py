from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.util.cart_public_id import generate_cart_public_id


class Cart(db.Model):
    __tablename__ = "carts"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    public_id = db.Column(
        db.String(32),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: generate_cart_public_id()
    )

    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    checked_out_at = db.Column(db.DateTime(timezone=True))

    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        index=True
    )

    items = db.relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan"
    )

    user = db.relationship("User", back_populates="cart", uselist=False)

    @classmethod
    def get_active_cart(cls, user_id):
        now = datetime.now(timezone.utc)

        return (
            cls.query
            .filter(
                cls.user_id == user_id,
                cls.is_active.is_(True),
                cls.expires_at.isnot(None),
                cls.expires_at > now
            )
            .first()
        )

    def extend_expiry(self, minutes=30):
        self.expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    def is_expired(self):
        if not self.expires_at:
            return False
        expires_at = self.expires_at
    # FORCE timezone awareness
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at < datetime.now(timezone.utc)