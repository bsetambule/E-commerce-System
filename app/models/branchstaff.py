from app.extensions import db

class BranchStaff(db.Model):
    __tablename__ = "branch_staff"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    branch_id = db.Column(db.BigInteger, db.ForeignKey("store_branches.id"), index=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), index=True)
    role = db.Column(db.String(50))

    branch = db.relationship("StoreBranch", back_populates="staff_members")
    user = db.relationship("User", back_populates="branch_staff")
    