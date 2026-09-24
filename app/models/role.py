from app.extensions import db

class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)

    users = db.relationship("User", secondary="user_roles", back_populates="roles")
    