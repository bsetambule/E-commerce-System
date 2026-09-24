from flask import Blueprint, render_template, redirect, url_for, request, abort, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.security.decorators import role_required
from app.util.audit_helper import log_action, get_request_meta
from app.models.branchproduct import BranchProduct
from app.models.product import Product
from app.models.audit import AuditLog
from app.models.productvariant import ProductVariant
from app.models.user import User
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from sqlalchemy import or_
from app.models.inventory import Inventory
from app.models.productimages import ProductImage
from app.util.upload_secure import save_image_secure, save_bulk_image
import os
from decimal import Decimal, InvalidOperation
from openpyxl import load_workbook
from io import BytesIO
from app.models.productsearch import ProductSearch
from app.models.branchstaff import BranchStaff
from app.util.deliverysupervisor_helper import get_deliverysupervisor_branch
from app.models.delivery import Delivery, DeliveryStatus
from app.models.deliveryzone import DeliveryZone
from app.models.branchdeliveryzone import BranchDeliveryZone

deliverysupervisor_bp = Blueprint("deliverysupervisor", __name__, url_prefix="/deliverysupervisor")

# =====================================================
# DELIVERY SUPERVISOR DASHBOARD
# =====================================================
@deliverysupervisor_bp.route("/dashboard")
@login_required
@role_required("DELIVERYSUPERVISOR")
def dashboard():

    user = current_user
    staff = user.staff_profile

    branch_staff = BranchStaff.query.filter_by(
        user_id=user.id,
        role="DELIVERYSUPERVISOR"
    ).first()

    if not branch_staff:
        abort(403, "Store assignment missing")

    branch = branch_staff.branch

    if not branch:
        abort(404, "Store not found")

    branch = get_deliverysupervisor_branch()

    # =================================================
    # DELIVERY COUNTS
    # =================================================
    deliveries_count = Delivery.query.filter(
        Delivery.branch_id == branch.id,
        Delivery.status == DeliveryStatus.DELIVERED
    ).count()

    ongoing_count = Delivery.query.filter(
        Delivery.branch_id == branch.id,
        Delivery.status.in_([
            DeliveryStatus.ASSIGNED,
            DeliveryStatus.ACCEPTED,
            DeliveryStatus.ARRIVED_AT_PICKUP,
            DeliveryStatus.PICKED_UP,
            DeliveryStatus.IN_TRANSIT,
            DeliveryStatus.OUT_FOR_DELIVERY
        ])
    ).count()

    unassigneddeliveries_count = Delivery.query.filter(
        Delivery.branch_id == branch.id,
        Delivery.status == DeliveryStatus.UNASSIGNED
    ).count()

    total_deliveries = Delivery.query.filter_by(
        branch_id=branch.id
    ).count()

    # =================================================
    # RECENT DELIVERIES
    # =================================================
    recent_deliveries = (
        Delivery.query
        .options(
            joinedload(Delivery.order),
            joinedload(Delivery.courier),
            joinedload(Delivery.delivery_zone)
        )
        .filter(
            Delivery.branch_id == branch.id
        )
        .order_by(
            Delivery.created_at.desc()
        )
        .limit(10)
        .all()
    )

    return render_template(
        "deliverysupervisor/dashboard.html",
        branch=branch,
        staff=staff,
        deliveries_count=deliveries_count,
        ongoing_count=ongoing_count,
        unassigneddeliveries_count=unassigneddeliveries_count,
        total_deliveries=total_deliveries,
        recent_deliveries=recent_deliveries
    )


# -----------------------------
# LIST DELIVERIES
# -----------------------------
@deliverysupervisor_bp.route("/")
@login_required
@role_required("DELIVERYSUPERVISOR")
def deliveries():

    branch = get_deliverysupervisor_branch()

    # -----------------------------
    # FILTERS
    # -----------------------------
    current_tab = request.args.get("tab", "all")
    page = request.args.get("page", 1, type=int)

    query = Delivery.query.filter_by(branch_id=branch.id)

    # -----------------------------
    # TAB FILTERING
    # -----------------------------
    if current_tab == "unassigned":
        query = query.filter(
            Delivery.status == DeliveryStatus.UNASSIGNED
        )

    elif current_tab == "ongoing":
        query = query.filter(
            Delivery.status.in_([
                DeliveryStatus.ASSIGNED,
                DeliveryStatus.ACCEPTED,
                DeliveryStatus.ARRIVED_AT_PICKUP,
                DeliveryStatus.PICKED_UP,
                DeliveryStatus.IN_TRANSIT,
                DeliveryStatus.OUT_FOR_DELIVERY,
            ])
        )

    elif current_tab == "completed":
        query = query.filter(
            Delivery.status == DeliveryStatus.DELIVERED
        )

    # -----------------------------
    # PAGINATION
    # -----------------------------
    deliveries = query.order_by(
        Delivery.created_at.desc()
    ).paginate(
        page=page,
        per_page=20,
        error_out=False
    )

    return render_template(
        "deliverysupervisor/deliveries.html",
        deliveries=deliveries,
        branch=branch,
        current_tab=current_tab
    )

# -----------------------------
# DELIVERY DETAILS
# -----------------------------
@deliverysupervisor_bp.route("/deliveries/<int:delivery_id>")
@login_required
@role_required("DELIVERYSUPERVISOR")
def deliverydetails(delivery_id):

    branch = get_deliverysupervisor_branch()

    # get delivery
    delivery = Delivery.query.filter_by(
        id=delivery_id,
        branch_id=branch.id
    ).first_or_404()

    return render_template(
        "deliverysupervisor/deliverydetails.html",
        delivery=delivery
    )


# -----------------------------
# LIST COURIERS
# -----------------------------
@deliverysupervisor_bp.route("/couriers")
@login_required
@role_required("DELIVERYSUPERVISOR")
def couriers():

    current_tab = request.args.get("tab", "all")
    page = request.args.get("page", 1, type=int)

    query = User.query.filter(
        User.is_active == True
    )

    # only courier users
    query = query.filter(User.roles.any(name="COURIER"))

    users = query.paginate(
        page=page,
        per_page=20,
        error_out=False
    )

    return render_template(
        "deliverysupervisor/couriers.html",
        users=users,
        current_tab=current_tab
    )


# -----------------------------
# VIEW COURIER
# -----------------------------
@deliverysupervisor_bp.route("/couriers/<int:user_id>")
@login_required
@role_required("DELIVERYSUPERVISOR")
def view_courier(user_id):

    # get user
    user = User.query.get_or_404(user_id)

    # ensure user is a courier
    if not user.courier_profile:
        flash("Courier not found.", "danger")
        return redirect(url_for("deliverysupervisor.couriers"))

    courier = user.courier_profile

    # completed deliveries count
    completed_deliveries = Delivery.query.filter(
        Delivery.courier_id == user.id,
        Delivery.status == DeliveryStatus.DELIVERED
    ).count()

    return render_template(
        "deliverysupervisor/courierprofile.html",
        user=user,
        courier=courier,
        completed_deliveries=completed_deliveries
    )


# =====================================================
# ATTACH DELIVERY ZONE TO BRANCH
# =====================================================

@deliverysupervisor_bp.route(
    "/delivery-zones/create",
    methods=["GET", "POST"]
)
@login_required
@role_required("DELIVERYSUPERVISOR")
def create_branch_delivery_zone():

    branch = get_deliverysupervisor_branch()

    delivery_zones = (
        DeliveryZone.query
        .filter(DeliveryZone.is_active.is_(True))
        .order_by(DeliveryZone.name.asc())
        .all()
    )

    if request.method == "GET":
        return render_template(
            "deliverysupervisor/createbranchdeliveryzone.html",
            branch=branch,
            delivery_zones=delivery_zones
        )

    try:

        # =====================================================
        # ZONE VALIDATION
        # =====================================================

        delivery_zone_id = request.form.get("delivery_zone_id", type=int)

        if not delivery_zone_id:
            flash("Please select a delivery zone.", "danger")
            return redirect(url_for(
                "deliverysupervisor.create_branch_delivery_zone"
            ))

        zone = DeliveryZone.query.filter(
            DeliveryZone.id == delivery_zone_id,
            DeliveryZone.is_active.is_(True)
        ).first()

        if not zone:
            flash("Delivery zone not found.", "danger")
            return redirect(url_for(
                "deliverysupervisor.create_branch_delivery_zone"
            ))

        # =====================================================
        # DUPLICATE CHECK
        # =====================================================

        existing = BranchDeliveryZone.query.filter_by(
            branch_id=branch.id,
            delivery_zone_id=zone.id
        ).first()

        if existing:
            flash("Zone already attached to this branch.", "warning")
            return redirect(url_for(
                "deliverysupervisor.create_branch_delivery_zone"
            ))

        # =====================================================
        # HELPERS (SAFE PARSING)
        # =====================================================

        def parse_decimal(field):
            val = request.form.get(field)
            try:
                return float(val) if val not in (None, "", " ") else None
            except ValueError:
                return None

        def parse_int(field):
            val = request.form.get(field)
            try:
                return int(val) if val not in (None, "", " ") else None
            except ValueError:
                return None

        # =====================================================
        # CREATE BRANCH DELIVERY ZONE
        # =====================================================

        branch_zone = BranchDeliveryZone(
            branch_id=branch.id,
            delivery_zone_id=zone.id,

            base_fee=parse_decimal("base_fee") or 0,
            min_order_value=parse_decimal("min_order_value") or 0,

            free_delivery_threshold=parse_decimal("free_delivery_threshold"),

            estimated_delivery_minutes=parse_int("estimated_delivery_minutes"),

            max_delivery_distance_km=parse_decimal("max_delivery_distance_km"),

            supports_same_day_delivery=(
                request.form.get("supports_same_day_delivery") == "1"
            ),

            supports_scheduled_delivery=(
                request.form.get("supports_scheduled_delivery") == "1"
            ),

            is_active=True,

            notes=(request.form.get("notes") or "").strip()
        )

        db.session.add(branch_zone)
        db.session.commit()

        flash("Delivery zone attached successfully.", "success")

        return redirect(url_for("deliverysupervisor.zones"))

    except Exception as e:
        db.session.rollback()
        print(f"[BRANCH DELIVERY ZONE ERROR]: {e}")

        flash("Failed to attach delivery zone.", "danger")

        return redirect(url_for(
            "deliverysupervisor.create_branch_delivery_zone"
        ))

# =====================================================
# LIST BRANCH DELIVERY ZONES
# =====================================================
@deliverysupervisor_bp.route("/delivery-zones")
@login_required
@role_required("DELIVERYSUPERVISOR")
def zones():

    branch = get_deliverysupervisor_branch()

    page = request.args.get(
        "page",
        1,
        type=int
    )

    tab = request.args.get(
        "tab",
        "active"
    )

    search = request.args.get(
        "search",
        ""
    ).strip()

    query = (
        BranchDeliveryZone.query
        .join(DeliveryZone)
        .filter(
            BranchDeliveryZone.branch_id == branch.id
        )
    )

    if tab == "active":

        query = query.filter(
            BranchDeliveryZone.is_active.is_(True)
        )

    elif tab == "inactive":

        query = query.filter(
            BranchDeliveryZone.is_active.is_(False)
        )

    if search:

        query = query.filter(
            DeliveryZone.name.ilike(
                f"%{search}%"
            )
        )

    zones = query.order_by(
        BranchDeliveryZone.created_at.desc()
    ).paginate(
        page=page,
        per_page=20,
        error_out=False
    )

    return render_template(
        "deliverysupervisor/branchdeliveryzones.html",
        branch=branch,
        zones=zones,
        current_tab=tab,
        search=search
    )


# =====================================================
# VIEW BRANCH DELIVERY ZONE
# =====================================================
@deliverysupervisor_bp.route("/delivery-zones/<int:branch_zone_id>")
@login_required
@role_required("DELIVERYSUPERVISOR")
def view_branch_delivery_zone(branch_zone_id):

    branch = get_deliverysupervisor_branch()

    branch_zone = (
        BranchDeliveryZone.query
        .filter_by(
            id=branch_zone_id,
            branch_id=branch.id
        )
        .first_or_404()
    )

    # flatten for template clarity
    zone = branch_zone.delivery_zone

    return render_template(
        "deliverysupervisor/viewbranchdeliveryzone.html",
        branch=branch,
        branch_zone=branch_zone,
        zone=branch_zone.delivery_zone
    )


# =====================================================
# EDIT BRANCH DELIVERY ZONE
# =====================================================
@deliverysupervisor_bp.route("/delivery-zones/<int:branch_zone_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("DELIVERYSUPERVISOR")
def edit_branch_delivery_zone(
    branch_zone_id
):

    branch = get_deliverysupervisor_branch()

    branch_zone = (
        BranchDeliveryZone.query
        .filter_by(
            id=branch_zone_id,
            branch_id=branch.id
        )
        .first_or_404()
    )

    if request.method == "GET":

        delivery_zones = DeliveryZone.query.filter_by(is_active=True).all()

        return render_template(
            "deliverysupervisor/editbranchdeliveryzone.html",
            branch=branch,
            branch_zone=branch_zone,
            delivery_zones=delivery_zones
        )

    try:

        branch_zone.base_fee = request.form.get(
            "base_fee",
            type=float,
            default=0
        )

        branch_zone.min_order_value = request.form.get(
            "min_order_value",
            type=float,
            default=0
        )

        branch_zone.free_delivery_threshold = request.form.get(
            "free_delivery_threshold",
            type=float
        )

        branch_zone.estimated_delivery_minutes = request.form.get(
            "estimated_delivery_minutes",
            type=int
        )

        branch_zone.max_delivery_distance_km = request.form.get(
            "max_delivery_distance_km",
            type=float
        )

        branch_zone.supports_same_day_delivery = (
            request.form.get(
                "supports_same_day_delivery"
            ) == "on"
        )

        branch_zone.supports_scheduled_delivery = (
            request.form.get(
                "supports_scheduled_delivery"
            ) == "on"
        )

        branch_zone.notes = request.form.get(
            "notes",
            ""
        ).strip()

        db.session.commit()

        flash(
            "Delivery zone updated successfully.",
            "success"
        )

        return redirect(
            url_for(
                "deliverysupervisor.view_branch_delivery_zone",
                branch_zone_id=branch_zone.id
            )
        )

    except Exception as e:

        db.session.rollback()

        print(
            f"[EDIT BRANCH DELIVERY ZONE ERROR]: {e}"
        )

        flash(
            "Update failed.",
            "danger"
        )

        return redirect(
            url_for(
                "deliverysupervisor.edit_branch_delivery_zone",
                branch_zone_id=branch_zone.id
            )
        )
    

# =====================================================
# DEACTIVATE BRANCH DELIVERY ZONE
# =====================================================
@deliverysupervisor_bp.route("/delivery-zones/<int:branch_zone_id>/delete", methods=["POST"])
@login_required
@role_required("DELIVERYSUPERVISOR")
def delete_branch_delivery_zone(
    branch_zone_id
):

    branch = get_deliverysupervisor_branch()

    try:

        branch_zone = (
            BranchDeliveryZone.query
            .filter_by(
                id=branch_zone_id,
                branch_id=branch.id
            )
            .first_or_404()
        )

        branch_zone.is_active = False

        db.session.commit()

        flash(
            "Delivery zone deactivated.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print(
            f"[DELETE BRANCH DELIVERY ZONE ERROR]: {e}"
        )

        flash(
            "Failed to deactivate zone.",
            "danger"
        )

    return redirect(
        url_for(
            "deliverysupervisor.zones"
        )
    )


# =====================================================
# RESTORE BRANCH DELIVERY ZONE
# =====================================================
@deliverysupervisor_bp.route("/delivery-zones/<int:branch_zone_id>/restore", methods=["POST"])
@login_required
@role_required("DELIVERYSUPERVISOR")
def restore_branch_delivery_zone(
    branch_zone_id
):

    branch = get_deliverysupervisor_branch()

    try:

        branch_zone = (
            BranchDeliveryZone.query
            .filter_by(
                id=branch_zone_id,
                branch_id=branch.id
            )
            .first_or_404()
        )

        branch_zone.is_active = True

        db.session.commit()

        flash(
            "Delivery zone restored.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print(
            f"[RESTORE BRANCH DELIVERY ZONE ERROR]: {e}"
        )

        flash(
            "Restore failed.",
            "danger"
        )

    return redirect(
        url_for(
            "deliverysupervisor.zones"
        )
    )