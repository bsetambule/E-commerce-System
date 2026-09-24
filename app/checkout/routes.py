from flask import (
    Blueprint,
    redirect,
    request,
    url_for,
    flash, render_template,
    jsonify
)
from flask_login import login_required, current_user
from app.extensions import db
from app.models.cart import Cart
from app.models.payment import Payment, PaymentStatus

from app.services.stripeservice import StripeService
from app.util.order_public_id import generate_order_public_id
from app.services.orderservice import OrderService
from app.util.initials_helper import get_user_initials
from app.models.branchdeliveryzone import BranchDeliveryZone
from app.models.storebranch import StoreBranch
from app.models.deliveryzone import DeliveryZone
from decimal import Decimal

from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError
from app.services.paymentservice import PaymentService
from app.services.inventoryservice import InventoryService


checkout_bp = Blueprint(
    "checkout",
    __name__,
    url_prefix="/checkout"
)

@checkout_bp.route("/", methods=["GET"])
@login_required
def checkout_page():

    cart = Cart.get_active_cart(current_user.id)

    if not cart or not cart.items:
        flash("Your cart is empty", "error")
        return redirect(url_for("customer.cart"))

    branch_ids = {item.branch_id for item in cart.items}

    if len(branch_ids) != 1:
        flash("Your cart contains items from multiple branches. Please clear cart.", "error")
        return redirect(url_for("customer.cart"))

    branch_id = next(iter(branch_ids))
    branch = StoreBranch.query.get_or_404(branch_id)

    supports_delivery = branch.allows_delivery
    supports_pickup = branch.allows_pickup

    # -------------------------
    # SUBTOTAL (Decimal-safe)
    # -------------------------
    subtotal = sum(
        (item.unit_price_snapshot or Decimal("0")) * item.quantity
        for item in cart.items
    )

    subtotal = Decimal(subtotal)

    delivery_fee = Decimal("0")
    delivery_zone = None

    # -------------------------
    # DELIVERY LOGIC
    # -------------------------
    if supports_delivery:

        user_profile = current_user.customer_profile

        delivery_zone = (
            db.session.query(BranchDeliveryZone)
            .join(DeliveryZone)
            .filter(
                BranchDeliveryZone.branch_id == branch_id,
                BranchDeliveryZone.is_active.is_(True),
                DeliveryZone.is_active.is_(True),
                DeliveryZone.city == user_profile.city
            )
            .first()
        )

        if not delivery_zone:
            flash("No delivery zone available for your address", "error")
            return redirect(url_for("customer.cart"))

        base_fee = delivery_zone.base_fee or Decimal("0")
        threshold = delivery_zone.free_delivery_threshold

        if threshold is not None and subtotal >= threshold:
            delivery_fee = Decimal("0")
        else:
            delivery_fee = base_fee

    elif supports_pickup:
        delivery_fee = Decimal("0")

    else:
        flash("Branch does not support delivery or pickup", "error")
        return redirect(url_for("customer.cart"))

    total = subtotal + delivery_fee

    return render_template(
        "customer/checkout.html",
        cart=cart,
        branch=branch,
        delivery_zone=delivery_zone,
        subtotal=subtotal,
        shipping_fee=delivery_fee,
        total=total,
        supports_delivery=supports_delivery,
        supports_pickup=supports_pickup,
        user_initials=get_user_initials(current_user)
    )


@checkout_bp.route("/create", methods=["POST"])
@login_required
def create_checkout():

    try:
        # -----------------------------
        # CART (SOURCE OF TRUTH)
        # -----------------------------
        cart = Cart.get_active_cart(current_user.id)

        if not cart:
            return jsonify({"error": "Cart not found"}), 404

        if not cart.items:
            return jsonify({"error": "Cart is empty"}), 400

        # IMPORTANT: extend at checkout start
        cart.extend_expiry()
        db.session.flush()

        # -----------------------------
        # PRICING SNAPSHOT
        # -----------------------------
        subtotal = sum(
            item.unit_price_snapshot * item.quantity
            for item in cart.items
        )

        tax_amount = 0
        delivery_fee = 0
        discount_amount = 0

        grand_total = subtotal + tax_amount + delivery_fee - discount_amount

        pricing_snapshot = {
            "subtotal": subtotal,
            "tax": tax_amount,
            "discount": discount_amount,
            "delivery_fee": delivery_fee,
            "grand_total": grand_total,
            "currency": "GBP"
        }

        idempotency_key = str(uuid4())

        # -----------------------------
        # FORM DATA
        # -----------------------------
        data = request.get_json() or {}

        order_method = data.get("order_method", "delivery")
        is_delivery = (order_method == "delivery")

        address_data = {
            "first_name": data.get("firstName"),
            "last_name": data.get("lastName"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "area": data.get("area"),
            "plot_number": data.get("plot_number"),
            "delivery_notes": data.get("delivery_notes"),
            "pickup_notes": data.get("pickup_notes"),
        }

        branch_id = cart.items[0].branch_id

        # -----------------------------
        # CREATE ORDER
        # -----------------------------
        order = OrderService.create_pending_order(
            user_id=current_user.id,
            branch_id=branch_id,
            cart=cart,
            pricing_snapshot=pricing_snapshot,
            is_delivery=is_delivery,
            address_data=address_data,
            idempotency_key=idempotency_key
        )

        # -----------------------------
        # RESERVE INVENTORY
        # -----------------------------
        InventoryService.reserve_inventory_for_order(
            order=order,
            cart_items=cart.items
        )

        # -----------------------------
        # CREATE PAYMENT
        # -----------------------------
        payment_result = PaymentService.create_payment_for_order(
            order=order,
            customer_email=current_user.email,
            idempotency_key=idempotency_key
        )

        db.session.commit()

        # -----------------------------
        # RESPONSE (CLEAN JSON)
        # -----------------------------
        return jsonify({
            "checkout_url": payment_result["checkout_url"],
            "order_id": order.public_id
        })

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Checkout transaction failed"}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400




@checkout_bp.route("/success")
@login_required
def success():

    session_id = request.args.get(
        "session_id"
    )

    payment = Payment.query.filter_by(
        provider_checkout_session_id=session_id
    ).first()

    if not payment:

        flash(
            "Payment not found",
            "error"
        )

        return redirect(
            url_for("customer.orders")
        )

    # webhook still processing

    if payment.status != PaymentStatus.SUCCEEDED:

        flash(
            "Payment processing...",
            "info"
        )

        return redirect(
            url_for("customer.orders")
        )

    return redirect(
        url_for(
            "customer.order_detail",
            public_id=payment.order.public_id
        )
    )