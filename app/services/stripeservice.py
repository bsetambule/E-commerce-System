import stripe

from flask import current_app


class StripeService:

    @staticmethod
    def init_app(app):
        stripe.api_key = app.config["STRIPE_SECRET_KEY"]

    @staticmethod
    def create_checkout_session(
        checkout_session,
        payment,
        customer_email
    ):

        line_items = []

        for item in checkout_session.items:

            line_items.append({
                "price_data": {
                    "currency": "gbp",
                    "product_data": {
                        "name": item.product_name
                    },
                    "unit_amount": int(
                        float(item.unit_price) * 100
                    )
                },
                "quantity": item.quantity
            })

        if checkout_session.shipping_fee > 0:

            line_items.append({
                "price_data": {
                    "currency": "gbp",
                    "product_data": {
                        "name": "Shipping"
                    },
                    "unit_amount": int(
                        float(checkout_session.shipping_fee)
                        * 100
                    )
                },
                "quantity": 1
            })

        return stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            customer_email=customer_email,
            line_items=line_items,

            expires_at=int(
                checkout_session.expires_at.timestamp()
            ),

            client_reference_id=str(
                checkout_session.public_id
            ),

            payment_intent_data={
                "metadata": {
                    "checkout_id":
                        checkout_session.public_id,

                    "order_id":
                        str(payment.order_id)
                }
            },

            metadata={
                "checkout_session_id": str(
                    checkout_session.id
                ),
                "payment_id": str(payment.id),
                "order_id": str(payment.order_id)
            }, 
            success_url=(
                f"{current_app.config['BASE_URL']}"
                "/checkout/success"
                "?session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=(
                f"{current_app.config['BASE_URL']}"
                "/checkout/cancel"
            )
            
        )