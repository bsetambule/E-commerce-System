from datetime import datetime, timezone

from app.extensions import db
from app.util.idgenerator import generate_public_id


class StaffProfile(db.Model):
    __tablename__ = "staff_profiles"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    @staticmethod
    def generate_id():
        return generate_public_id(StaffProfile, "sta", db.session)

    public_id = db.Column(db.String(50), unique=True, index=True, default=generate_id)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), unique=True, index=True, nullable=False)
    # -----------------------------
    # PERSONAL INFO
    # -----------------------------
    first_name = db.Column(db.String(30), nullable=False)
    last_name = db.Column(db.String(30), nullable=False)
    # -----------------------------
    # META
    # -----------------------------
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    # -----------------------------
    # RELATIONSHIP
    # -----------------------------
    user = db.relationship("User", back_populates="staff_profile")
    