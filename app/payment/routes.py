import stripe

from flask import (
    Blueprint,
    request,
    jsonify,
    current_app
)

from app.extensions import db

from app.models.payment import Payment

from app.services.paymentservice import (
    PaymentService
)
from app.services.webhookservice import WebhookService
from sqlalchemy.exc import SQLAlchemyError

payment_bp = Blueprint(
    "payment",
    __name__,
    url_prefix="/payment"
)


@payment_bp.route(
    "/stripe",
    methods=["POST"]
)
def stripe_webhook():

    payload = request.data

    signature = request.headers.get(
        "Stripe-Signature"
    )

    try:

        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=current_app.config[
                "STRIPE_WEBHOOK_SECRET"
            ]
        )

    except stripe.error.SignatureVerificationError:

        return jsonify({
            "error": (
                "Invalid Stripe signature"
            )
        }), 400

    except ValueError:

        return jsonify({
            "error": (
                "Invalid webhook payload"
            )
        }), 400

    event_type = event["type"]
    event_id = event["id"]

    try:

        if event_type == (
            "checkout.session.completed"
        ):

            stripe_session = (
                event["data"]["object"]
            )

            WebhookService.process_checkout_session_completed(
                event_id=event_id,
                stripe_session=stripe_session
            )

        db.session.commit()

    except SQLAlchemyError:

        db.session.rollback()

        return jsonify({
            "error": (
                "Database transaction failed"
            )
        }), 500

    except Exception:

        db.session.rollback()

        return jsonify({
            "error": (
                "Webhook processing failed"
            )
        }), 500

    return jsonify({
        "received": True
    }), 200