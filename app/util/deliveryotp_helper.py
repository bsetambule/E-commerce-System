import secrets
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.extensions import db
from app.models.deliveryotp import DeliveryOtp

ph = PasswordHasher()

def generate_otp_code() -> str:
   
    return f"{secrets.randbelow(900000) + 100000}"

def hash_otp(otp_code: str) -> str:

    return ph.hash(otp_code)

def create_delivery_otp(
    delivery,
    otp_type,
    order_id,
    branch_id,
    courier_id=None,
):
    # invalidate old unverified OTPs
    old_otps = DeliveryOtp.query.filter(
        DeliveryOtp.delivery_id == delivery.id,
        DeliveryOtp.otp_type == otp_type,
        DeliveryOtp.is_verified.is_(False)
    ).all()

    now = datetime.now(timezone.utc)

    for otp in old_otps:
        otp.invalidated_at = now

    raw_otp = generate_otp_code()

    otp_record = DeliveryOtp(
        delivery_id=delivery.id,
        order_id=order_id,
        branch_id=branch_id,
        courier_id=courier_id,
        otp_type=otp_type,
        otp_code=hash_otp(raw_otp),
        is_verified=False,
    )

    db.session.add(otp_record)
    db.session.commit()

    return raw_otp, otp_record


def verify_delivery_otp(
    delivery_id,
    otp_type,
    otp_input,
):

    otp_record = (
        DeliveryOtp.query
        .filter(
            DeliveryOtp.delivery_id == delivery_id,
            DeliveryOtp.otp_type == otp_type,
            DeliveryOtp.is_verified.is_(False),
            DeliveryOtp.invalidated_at.is_(None),
        )
        .order_by(DeliveryOtp.created_at.desc())
        .first()
    )

    if not otp_record:
        return False, "OTP not found"

    if otp_record.attempts >= otp_record.max_attempts:
        return False, "Maximum attempts exceeded"

    try:
        ph.verify(otp_record.otp_code, otp_input)

        otp_record.is_verified = True
        otp_record.verified_at = datetime.now(timezone.utc)

        db.session.commit()

        return True, "OTP verified"

    except VerifyMismatchError:

        otp_record.attempts += 1

        db.session.commit()

        return False, "Invalid OTP"

    except Exception:
        db.session.rollback()
        raise