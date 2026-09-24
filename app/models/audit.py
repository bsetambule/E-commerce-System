from datetime import datetime, timezone
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    branch_id = db.Column(db.BigInteger, db.ForeignKey("store_branches.id"), index=True)
    # Actor (who performed the action)
    user_id = db.Column(db.BigInteger, index=True, nullable=True)
    email = db.Column(db.String(255), index=True, nullable=True)
    # Action (what happened)
    action = db.Column(db.String(200), index=True, nullable=False)
    entity_type = db.Column(db.String(150), index=True, nullable=True)
    entity_id = db.Column(db.String(100), index=True, nullable=True)
    # Context (where / how)
    ip_address = db.Column(db.String(45), index=True, nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    device_type = db.Column(db.String(20), index=True, nullable=True)
    # Flexible structured data (NOT a junk dump, only extras)
    meta_data = db.Column(db.JSON, nullable=True)
    # Timestamp
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)

    def __repr__(self):
        return f"<AuditLog {self.action} user_id={self.user_id}>"
    