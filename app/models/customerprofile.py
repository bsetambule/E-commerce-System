from app.extensions import db
import uuid
from app.util.idgenerator import generate_public_id

class CustomerProfile(db.Model):
    __tablename__ = "customer_profiles"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(50), unique=True, index=True, default=lambda: generate_public_id("cus"))
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), unique=True, index=True, nullable=False)
    first_name = db.Column(db.String(30), nullable=False)
    last_name = db.Column(db.String(30), nullable=False)
    city = db.Column(db.String(100), nullable=False, index=True)
    default_address = db.Column(db.String(255))

    user = db.relationship("User", back_populates="customer_profile", cascade="all, delete")
    