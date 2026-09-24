# app/routes/courier.py

from flask import Blueprint, render_template, redirect, url_for, request, abort, flash
from flask_login import login_required, current_user

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.security.decorators import role_required
from app.util.audit_helper import log_action

from app.models.delivery import Delivery
from app.models.order import Order

from datetime import datetime, timezone
from app.models.delivery import DeliveryStatus
from app.models.order import OrderStatus

courier_bp = Blueprint(
    "courier",
    __name__,
    url_prefix="/courier"
)

# -----------------------------
# DASHBOARD
# -----------------------------
@courier_bp.route("/dashboard")
@login_required
@role_required("COURIER")
def dashboard():
    # single query (source of truth)
    deliveries = Delivery.query.filter_by(
        courier_id=current_user.id
    ).order_by(Delivery.created_at.desc()).all()

    # active statuses (courier working state)
    active_statuses = {
        DeliveryStatus.ASSIGNED,
        DeliveryStatus.ACCEPTED,
        DeliveryStatus.PICKED_UP,
        DeliveryStatus.IN_TRANSIT,
        DeliveryStatus.OUT_FOR_DELIVERY
    }

    # split once (no duplicate querying)
    active_deliveries = []
    completed_deliveries = []

    for d in deliveries:
        if d.status == DeliveryStatus.DELIVERED:
            completed_deliveries.append(d)
        elif d.status in active_statuses:
            active_deliveries.append(d)

    # recent = already sorted list (no second query needed)
    recent_deliveries = deliveries[:10]

    return render_template(
        "courier/dashboard.html",
        staff=current_user.courier_profile if hasattr(current_user, "courier_profile") else None,
        active_count=len(active_deliveries),
        completed_count=len(completed_deliveries),
        active_deliveries=active_deliveries,
        completed_deliveries=completed_deliveries,
        recent_deliveries=recent_deliveries
    )

# -----------------------------
# LIST MY DELIVERIES
# -----------------------------
@courier_bp.route("/")
@login_required
@role_required("COURIER")
def deliveries():

    tab = request.args.get("tab", "active")
    page = request.args.get("page", 1, type=int)

    base_query = Delivery.query.filter_by(
        courier_id=current_user.id
    ).order_by(Delivery.created_at.desc())

    if tab == "completed":
        base_query = base_query.filter(Delivery.status == DeliveryStatus.DELIVERED)
    else:
        base_query = base_query.filter(
            Delivery.status.in_([
                DeliveryStatus.ASSIGNED,
                DeliveryStatus.ACCEPTED,
                DeliveryStatus.PICKED_UP,
                DeliveryStatus.IN_TRANSIT,
                DeliveryStatus.OUT_FOR_DELIVERY
            ])
        )

    deliveries = base_query.paginate(page=page, per_page=10)

    return render_template(
        "courier/deliveries.html",
        deliveries=deliveries,
        current_tab=tab
    )


# -----------------------------
# PICK UP DELIVERY
# -----------------------------
@courier_bp.route("/<int:id>/pickup", methods=["POST"])
@login_required
@role_required("COURIER")
def pickup_delivery(id):

    delivery = Delivery.query.get_or_404(id)

    if delivery.courier_id != current_user.id:
        abort(403)

    if delivery.status != DeliveryStatus.ASSIGNED:
        flash("Delivery cannot be picked up.", "warning")
        return redirect(url_for("courier.deliverydetails", id=id))

    try:
        with db.session.begin():
            delivery.status = DeliveryStatus.PICKED_UP
            delivery.picked_up_at = datetime.now(timezone.utc)

    except SQLAlchemyError:
        db.session.rollback()
        abort(500)

    flash("Delivery picked up.", "success")
    return redirect(url_for("courier.deliverydetails", id=id))


# -----------------------------
# VERIFY OTP & COMPLETE DELIVERY
# -----------------------------
@courier_bp.route("/<int:id>/complete", methods=["POST"])
@login_required
@role_required("COURIER")
def complete_delivery(id):

    delivery = Delivery.query.get_or_404(id)

    if delivery.courier_id != current_user.id:
        abort(403)

    if delivery.status != DeliveryStatus.PICKED_UP:
        flash("Delivery must be picked up first.", "warning")
        return redirect(url_for("courier.deliverydetails", id=id))

    otp_input = request.form.get("otp_code", "").strip()

    if not otp_input:
        flash("OTP is required.", "warning")
        return redirect(url_for("courier.deliverydetails", id=id))

    # LEGACY OTP CHECK (replace later with DeliveryOtp table)
    if otp_input != getattr(delivery, "otp_code", None):

        flash("Invalid OTP.", "danger")
        return redirect(url_for("courier.deliverydetails", id=id))

    try:
        with db.session.begin():

            delivery.status = DeliveryStatus.DELIVERED
            delivery.delivered_at = datetime.now(timezone.utc)

            if delivery.order:
                delivery.order.status = OrderStatus.DELIVERED

    except SQLAlchemyError:
        db.session.rollback()
        abort(500)

    flash("Delivery completed successfully.", "success")
    return redirect(url_for("courier.deliverydetails", id=id))