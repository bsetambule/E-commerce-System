from app.extensions import db
from datetime import datetime, timezone
import uuid
from app.util.idgenerator import generate_public_id

class CourierProfile(db.Model):
    __tablename__ = "courier_profiles"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    @staticmethod
    def generate_id():
        return generate_public_id(CourierProfile, "cou", db.session)

    public_id = db.Column(db.String(50), unique=True, index=True, default=generate_id)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), unique=True, index=True, nullable=False)
    first_name = db.Column(db.String(30), nullable=False)
    last_name = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="courier_profile", cascade="all, delete")
    