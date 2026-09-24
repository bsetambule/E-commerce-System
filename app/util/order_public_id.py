from datetime import datetime, timezone
import secrets

def generate_order_public_id(prefix="ORD"):
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d")

    token = secrets.token_hex(4).upper()

    return f"{prefix}-{timestamp}-{token}"
