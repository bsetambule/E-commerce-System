from sqlalchemy.exc import IntegrityError

from app.extensions import db

from app.models.order import (
    Order,
    OrderStatus
)

from app.models.orderitem import OrderItem
from app.models.orderaddress import OrderAddress

from app.util.order_public_id import (
    generate_order_public_id
)


class OrderService:

    @staticmethod
    def create_pending_order(
        *,
        user_id,
        branch_id,
        cart,
        pricing_snapshot,
        is_delivery,
        address_data,
        idempotency_key
    ):

        existing_order = Order.query.filter_by(
            idempotency_key=idempotency_key
        ).first()

        if existing_order:
            return existing_order

        try:

            order = Order(
                user_id=user_id,
                branch_id=branch_id,
                subtotal_amount=pricing_snapshot["subtotal"],
                tax_amount=pricing_snapshot["tax"],
                discount_amount=pricing_snapshot["discount"],
                delivery_fee=pricing_snapshot["delivery_fee"],
                grand_total=pricing_snapshot["grand_total"],
                currency=pricing_snapshot["currency"],
                status=OrderStatus.PENDING_PAYMENT,
                public_id=generate_order_public_id("ORD"),
                is_delivery=is_delivery,
                idempotency_key=idempotency_key
            )

            db.session.add(order)
            db.session.flush()

            # ---------------------------------------
            # ORDER ITEMS (FIXED PATH)
            # ---------------------------------------
            for cart_item in cart.items:

                variant = cart_item.variant
                product = variant.product if variant else None

                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id if product else None,
                    variant_id=cart_item.variant_id,
                    branch_id=branch_id,
                    quantity=cart_item.quantity,

                    product_name=product.name if product else None,
                    variant_name=variant.name if variant else None,
                    sku_snapshot=variant.sku if variant else None,

                    # use snapshot price from cart
                    unit_price=cart_item.unit_price_snapshot,
                    total_price=cart_item.unit_price_snapshot * cart_item.quantity,

                    currency=pricing_snapshot["currency"]
                )

                db.session.add(order_item)

            # ---------------------------------------
            # ADDRESS
            # ---------------------------------------
            if is_delivery:

                address = OrderAddress(
                    order_id=order.id,
                    first_name=address_data.get("firstName"),
                    last_name=address_data.get("lastName"),
                    phone=address_data.get("phone"),
                    city=address_data.get("city"),
                    region=address_data.get("region"),
                    area=address_data.get("area"),
                    plot_number=address_data.get("plot_number"),
                    delivery_notes=address_data.get("delivery_notes")
                )

                db.session.add(address)

            db.session.flush()

            return order

        except IntegrityError:
            db.session.rollback()

            existing_order = Order.query.filter_by(
                idempotency_key=idempotency_key
            ).first()

            if existing_order:
                return existing_order

            raise