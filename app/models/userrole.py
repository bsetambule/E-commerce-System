from app.extensions import db

class UserRole(db.Model):
    __tablename__ = "user_roles"

    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), primary_key=True)
    role_id = db.Column(db.BigInteger, db.ForeignKey("roles.id"), primary_key=True)