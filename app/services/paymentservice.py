from urllib.parse import urljoin

import stripe
from flask import current_app

from app.extensions import db
from app.models.payment import Payment, PaymentStatus


class PaymentService:

    @staticmethod
    def create_payment_for_order(
        *,
        order,
        customer_email,
        idempotency_key
    ):

        # -------------------------
        # EXISTING PAYMENT GUARD
        # -------------------------
        existing_payment = Payment.query.filter_by(
            order_id=order.id
        ).first()

        if existing_payment:
            return {
                "payment": existing_payment,
                "checkout_url": None
            }

        # -------------------------
        # CREATE PAYMENT RECORD
        # -------------------------
        payment = Payment(
            order_id=order.id,
            amount=order.grand_total,
            currency=order.currency,
            status=PaymentStatus.INITIATED,
            idempotency_key=idempotency_key
        )

        db.session.add(payment)
        db.session.flush()

        # -------------------------
        # STRIPE CONFIG
        # -------------------------
        stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

        frontend = current_app.config.get("FRONTEND_URL")
        if not frontend:
            raise ValueError("FRONTEND_URL missing")

        # -------------------------
        # BUILD LINE ITEMS (SAFE)
        # -------------------------
        line_items = []

        for item in order.items:

            if item is None:
                continue

            if item.unit_price is None:
                raise ValueError(f"Missing unit_price for item {item.id}")

            line_items.append({
                "price_data": {
                    "currency": (item.currency or "GBP").lower(),
                    "product_data": {
                        "name": item.product_name or "Product"
                    },
                    "unit_amount": int(float(item.unit_price) * 100)
                },
                "quantity": item.quantity or 1
            })

        # -------------------------
        # CREATE STRIPE SESSION
        # -------------------------
        checkout_session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=customer_email,
            line_items=line_items,
            success_url=urljoin(
                frontend,
                "/checkout/success?session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=urljoin(
                frontend,
                "/checkout/cancel"
            )
        )

        if not checkout_session or not checkout_session.url:
            raise ValueError("Stripe session creation failed")

        # -------------------------
        # RETURN CLEAN STRUCTURE
        # -------------------------
        return {
            "payment": payment,
            "checkout_url": checkout_session.url
        }