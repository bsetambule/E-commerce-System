from app.models.audit import AuditLog
from app.extensions import db
from datetime import datetime, timezone
import re
from flask import request


MOBILE_RE = re.compile(r"iphone|ipod|android.*mobile|windows phone", re.I)
TABLET_RE = re.compile(r"ipad|android(?!.*mobile)|tablet", re.I)
BOT_RE = re.compile(r"bot|crawl|spider|slurp|wget|curl", re.I)

def get_request_meta():
    return {
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "user_agent": request.headers.get("User-Agent")
    }

def detect_device_type(user_agent: str) -> str:
    """
    Returns: mobile | tablet | desktop | bot | unknown
    """

    if not user_agent:
        return "unknown"

    ua = user_agent.lower()

    if BOT_RE.search(ua):
        return "bot"

    if MOBILE_RE.search(ua):
        return "mobile"

    if TABLET_RE.search(ua):
        return "tablet"

    return "desktop"


def log_action(
    *,
    user_id=None,
    email=None,
    action=None,
    entity_type=None,
    entity_id=None,
    ip_address=None,
    user_agent=None,
    meta_data=None
):
    if not action:
        raise ValueError("action is required for audit logging")

    log = AuditLog(
        user_id=user_id,
        email=email,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        ip_address=ip_address,
        user_agent=user_agent,
        device_type=detect_device_type(user_agent),
        meta_data=meta_data or {},
        timestamp=datetime.now(timezone.utc)
    )

    db.session.add(log)
   
    return log

    

