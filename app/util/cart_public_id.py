from datetime import datetime, timezone
import secrets

def generate_cart_public_id(prefix="CART"):
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d")

    token = secrets.token_hex(4).upper()

    return f"{prefix}-{timestamp}-{token}"
