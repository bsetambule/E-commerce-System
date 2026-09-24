from datetime import datetime, timezone

from app.extensions import db


class ProcessedWebhookEvent(db.Model):
    __tablename__ = "processed_webhook_events"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
        autoincrement=True
    )

    provider = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    event_id = db.Column(
        db.String(255),
        nullable=False,
        unique=True,
        index=True
    )

    event_type = db.Column(
        db.String(255),
        nullable=False
    )

    processed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )