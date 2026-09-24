from datetime import datetime, timezone

from app.extensions import db

from app.models.payment import (
    Payment,
    PaymentStatus
)

from app.models.order import (
    OrderStatus
)

from app.models.processedwebhookevent import (
    ProcessedWebhookEvent
)


class WebhookService:

    @staticmethod
    def has_processed_event(event_id):

        return (
            ProcessedWebhookEvent.query.filter_by(
                event_id=event_id
            ).first()
            is not None
        )

    @staticmethod
    def mark_event_processed(
        *,
        provider,
        event_id,
        event_type
    ):

        processed_event = (
            ProcessedWebhookEvent(
                provider=provider,
                event_id=event_id,
                event_type=event_type
            )
        )

        db.session.add(processed_event)

    @staticmethod
    def process_checkout_session_completed(
        *,
        event_id,
        stripe_session
    ):

        if WebhookService.has_processed_event(
            event_id
        ):
            return

        payment = (
            Payment.query.filter_by(
                provider_checkout_session_id=(
                    stripe_session["id"]
                )
            )
            .with_for_update()
            .first()
        )

        if not payment:
            raise ValueError(
                "Payment not found"
            )

        if payment.status == (
            PaymentStatus.SUCCEEDED
        ):
            WebhookService.mark_event_processed(
                provider="stripe",
                event_id=event_id,
                event_type=(
                    "checkout.session.completed"
                )
            )

            return

        payment.status = (
            PaymentStatus.SUCCEEDED
        )

        payment.provider_payment_intent_id = (
            stripe_session.get(
                "payment_intent"
            )
        )

        payment.paid_at = (
            datetime.now(timezone.utc)
        )

        order = payment.order

        order.status = OrderStatus.PAID
        order.paid_at = (
            datetime.now(timezone.utc)
        )

        WebhookService.mark_event_processed(
            provider="stripe",
            event_id=event_id,
            event_type=(
                "checkout.session.completed"
            )
        )

        # IMPORTANT:
        # Async fulfillment event emitted later