from datetime import datetime, timezone

from app.extensions import db

from app.models.deliveryotp import (
    DeliveryOtp,
    DeliveryOtpType
)

from app.util.deliveryotp_helper import (
    generate_otp_code,
    hash_otp,
    verify_otp
)


class OtpService:

    @staticmethod
    def create_order_otp(
        *,
        order,
        otp_type,
        delivery=None
    ):

        existing_otp = (
            DeliveryOtp.query.filter_by(
                order_id=order.id,
                otp_type=otp_type,
                is_verified=False,
                is_invalidated=False
            ).first()
        )

        if existing_otp:
            return None

        raw_otp = generate_otp_code()

        otp_record = DeliveryOtp(
            order_id=order.id,
            branch_id=order.branch_id,
            delivery_id=(
                delivery.id
                if delivery
                else None
            ),
            otp_type=otp_type,
            otp_code_hash=hash_otp(raw_otp)
        )

        db.session.add(otp_record)

        return raw_otp

    @staticmethod
    def verify_order_otp(
        *,
        otp_record,
        otp_code
    ):

        if otp_record.is_verified:
            return False

        if otp_record.is_invalidated:
            return False

        if (
            otp_record.attempts
            >= otp_record.max_attempts
        ):

            otp_record.is_invalidated = True

            otp_record.invalidated_at = (
                datetime.now(timezone.utc)
            )

            return False

        if (
            otp_record.expires_at
            < datetime.now(timezone.utc)
        ):

            otp_record.is_invalidated = True

            otp_record.invalidated_at = (
                datetime.now(timezone.utc)
            )

            return False

        otp_record.attempts += 1

        is_valid = verify_otp(
            otp_code,
            otp_record.otp_code_hash
        )

        if not is_valid:
            return False

        otp_record.is_verified = True

        otp_record.verified_at = (
            datetime.now(timezone.utc)
        )

        return True