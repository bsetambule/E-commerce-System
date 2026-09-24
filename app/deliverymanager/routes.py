from flask import Blueprint, render_template, redirect, url_for, request, abort, flash
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.security.decorators import role_required
from app.util.audit_helper import log_action
from app.models.branchstaff import BranchStaff
from app.models.storebranch import StoreBranch
from app.models.delivery import Delivery, DeliveryStatus
from app.models.order import Order
from app.models.user import User
from app.util.deliverymanager_helper import get_deliverymanager_branch
from sqlalchemy.orm import joinedload
from app.models.branchdeliveryzone import BranchDeliveryZone
from app.models.deliveryzone import DeliveryZone

deliverymanager_bp = Blueprint(
    "deliverymanager",
    __name__,
    url_prefix="/deliverymanager"
)

# =====================================================
# DELIVERY MANAGER DASHBOARD
# =====================================================
@deliverymanager_bp.route("/dashboard")
@login_required
@role_required("DELIVERYMANAGER")
def dashboard():

    user = current_user

    staff = getattr(user, "staff_profile", None)

    # =================================================
    # DELIVERY COUNTS (GLOBAL)
    # =================================================
    deliveries_count = Delivery.query.filter(
        Delivery.status == DeliveryStatus.DELIVERED
    ).count()

    ongoing_count = Delivery.query.filter(
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
        Delivery.status == DeliveryStatus.UNASSIGNED
    ).count()

    total_deliveries = Delivery.query.count()

    # =================================================
    # RECENT DELIVERIES (GLOBAL)
    # =================================================
    recent_deliveries = (
        Delivery.query
        .options(
            joinedload(Delivery.order),
            joinedload(Delivery.courier),
            joinedload(Delivery.delivery_zone)
        )
        .order_by(Delivery.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "deliverymanager/dashboard.html",
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
@deliverymanager_bp.route("/")
@login_required
@role_required("DELIVERYMANAGER")
def deliveries():

    current_tab = request.args.get("tab", "all")
    page = request.args.get("page", 1, type=int)

    # BASE QUERY (FIX)
    query = Delivery.query

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
        "deliverymanager/deliveries.html",
        deliveries=deliveries,
        current_tab=current_tab
    )


# -----------------------------
# DELIVERY DETAILS
# -----------------------------
@deliverymanager_bp.route("/deliveries/<int:delivery_id>")
@login_required
@role_required("DELIVERYMANAGER")
def deliverydetails(delivery_id):

   

    # get delivery
    delivery = Delivery.query.filter_by(
        id=delivery_id
    ).first_or_404()

    return render_template(
        "deliverymanager/deliverydetails.html",
        delivery=delivery
    )


# -----------------------------
# CREATE DELIVERY FROM ORDER
# -----------------------------
@deliverymanager_bp.route("/create/<int:order_id>", methods=["POST"])
@login_required
@role_required("DELIVERYMANAGER")
def create_delivery(order_id):
    

    order = Order.query.get_or_404(order_id)

    

    if not order.is_delivery:
        abort(400, "Order is not a delivery order")

    existing = Delivery.query.filter_by(order_id=order.id).first()
    if existing:
        flash("Delivery already exists", "info")
        return redirect(url_for("deliverymanager.list_deliveries"))

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    try:
        with db.session.begin():
            import random
            otp_code = str(random.randint(100000, 999999))

            delivery = Delivery(
                order_id=order.id,
               
                status="assigned",
                otp_code=otp_code,
                delivery_address=order.user.customer_profile.default_address
            )

            db.session.add(delivery)

        log_action(
            current_user.id,
            f"Created delivery for order {order.id}",
            ip_address=ip
        )

        flash("Delivery created", "success")

    except SQLAlchemyError:
        db.session.rollback()
        abort(500)

    return redirect(url_for("deliverymanager.list_deliveries"))


# -----------------------------
# ASSIGN COURIER
# -----------------------------
@deliverymanager_bp.route("/<int:id>/assign", methods=["POST"])
@login_required
@role_required("DELIVERYMANAGER")
def assign_courier(id):
    

    delivery = Delivery.query.get_or_404(id)

   

    courier_id = request.form.get("courier_id")

    courier = User.query.get(courier_id)

    if not courier or not courier.has_role("courier"):
        abort(400, "Invalid courier")

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    try:
        with db.session.begin():
            delivery.courier_id = courier.id
            delivery.status = "assigned"

        log_action(
            current_user.id,
            f"Assigned courier {courier.id} to delivery {delivery.id}",
            ip_address=ip
        )

        flash("Courier assigned", "success")

    except SQLAlchemyError:
        db.session.rollback()
        abort(500)

    return redirect(url_for("deliverymanager.list_deliveries"))


# -----------------------------
# UPDATE STATUS (PICKUP / TRANSIT)
# -----------------------------
@deliverymanager_bp.route("/<int:id>/status", methods=["POST"])
@login_required
@role_required("DELIVERYMANAGER")
def update_status(id):
   

    delivery = Delivery.query.get_or_404(id)

   

    status = request.form.get("status")

    allowed = ["assigned", "picked_up", "delivered"]

    if status not in allowed:
        abort(400, "Invalid status")

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    try:
        with db.session.begin():
            delivery.status = status

            if status == "delivered":
                from datetime import datetime, timezone
                delivery.delivered_at = datetime.now(timezone.utc)

        log_action(
            current_user.id,
            f"Updated delivery {delivery.id} → {status}",
            ip_address=ip
        )

        flash("Status updated", "success")

    except SQLAlchemyError:
        db.session.rollback()
        abort(500)

    return redirect(url_for("deliverymanager.list_deliveries"))


# -----------------------------
# LIST COURIERS
# -----------------------------
@deliverymanager_bp.route("/couriers")
@login_required
@role_required("DELIVERYMANAGER")
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
        "deliverymanager/couriers.html",
        users=users,
        current_tab=current_tab
    )


# -----------------------------
# VIEW COURIER
# -----------------------------
@deliverymanager_bp.route("/couriers/<int:user_id>")
@login_required
@role_required("DELIVERYMANAGER")
def view_courier(user_id):

    # get user
    user = User.query.get_or_404(user_id)

    # ensure user is a courier
    if not user.courier_profile:
        flash("Courier not found.", "danger")
        return redirect(url_for("deliverymanager.couriers"))

    courier = user.courier_profile

    # completed deliveries count
    completed_deliveries = Delivery.query.filter(
        Delivery.courier_id == user.id,
        Delivery.status == DeliveryStatus.DELIVERED
    ).count()

    return render_template(
        "deliverymanager/courierprofile.html",
        user=user,
        courier=courier,
        completed_deliveries=completed_deliveries
    )


# =====================================================
# CREATE DELIVERY ZONE
# =====================================================

@deliverymanager_bp.route(
    "/delivery-zones/create",
    methods=["GET", "POST"]
)
@login_required
@role_required("DELIVERYMANAGER")
def create_delivery_zone():

    if request.method == "GET":
        return render_template(
            "deliverymanager/createdeliveryzone.html"
        )

    try:
        # =====================================================
        # BASIC FIELDS
        # =====================================================

        name = request.form.get("name", "").strip()
        town = request.form.get("town", "").strip()
        city = request.form.get("city", "").strip()

        # =====================================================
        # VALIDATION
        # =====================================================

        if not name:
            flash("Zone name is required.", "danger")
            return redirect(url_for("deliverymanager.create_delivery_zone"))

        existing = DeliveryZone.query.filter(
            DeliveryZone.name.ilike(name)
        ).first()

        if existing:
            flash("Zone already exists.", "warning")
            return redirect(url_for("deliverymanager.create_delivery_zone"))

        # =====================================================
        # COVERED AREAS (FROM TEXTAREA)
        # =====================================================

        raw_areas = request.form.get("covered_areas_raw", "")

        covered_areas = [
            a.strip().lower()
            for a in raw_areas.split("\n")
            if a.strip()
        ]

        if not covered_areas:
            flash("At least one covered area is required.", "danger")
            return redirect(url_for("deliverymanager.create_delivery_zone"))

        # =====================================================
        # CREATE ZONE
        # =====================================================

        zone = DeliveryZone(
            name=name,
            town=town or None,
            city=city or None,
            covered_areas=covered_areas,
            is_active=True
        )

        db.session.add(zone)
        db.session.commit()

        flash("Delivery zone created successfully.", "success")
        return redirect(url_for("deliverymanager.zones"))

    except Exception as e:
        db.session.rollback()
        print(f"[CREATE DELIVERY ZONE ERROR]: {e}")

        flash("Failed to create delivery zone.", "danger")
        return redirect(url_for("deliverymanager.create_delivery_zone"))

# =====================================================
# LIST DELIVERY ZONES
# =====================================================
@deliverymanager_bp.route("/delivery-zones")
@login_required
@role_required("DELIVERYMANAGER")
def zones():

    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    tab = request.args.get("tab", "active")

    query = DeliveryZone.query

    # FILTERS
    if tab == "active":
        query = query.filter(
            DeliveryZone.is_active.is_(True)
        )

    elif tab == "inactive":
        query = query.filter(
            DeliveryZone.is_active.is_(False)
        )

    elif tab == "all":
        pass

    # SEARCH
    if search:
        query = query.filter(
            DeliveryZone.name.ilike(f"%{search}%")
        )

    zones = query.order_by(
        DeliveryZone.created_at.desc()
    ).paginate(
        page=page,
        per_page=20,
        error_out=False
    )

    return render_template(
        "deliverymanager/deliveryzones.html",
        zones=zones,
        search=search,
        current_tab=tab
    )



# =====================================================
# VIEW DELIVERY ZONE
# =====================================================
@deliverymanager_bp.route(
    "/delivery-zones/<int:zone_id>"
)
@login_required
@role_required("DELIVERYMANAGER")
def view_delivery_zone(zone_id):

    zone = DeliveryZone.query.get_or_404(zone_id)

    return render_template(
        "deliverymanager/viewdeliveryzone.html",
        zone=zone
    )


# =====================================================
# EDIT DELIVERY ZONE
# =====================================================

@deliverymanager_bp.route(
    "/delivery-zones/<int:zone_id>/edit",
    methods=["GET", "POST"]
)
@login_required
@role_required("DELIVERYMANAGER")
def edit_delivery_zone(zone_id):

    zone = DeliveryZone.query.get_or_404(zone_id)

    if request.method == "POST":

        try:
            # =====================================================
            # BASIC FIELDS
            # =====================================================

            name = request.form.get("name", "").strip()
            town = request.form.get("town", "").strip()
            city = request.form.get("city", "").strip()

            if not name:
                flash("Zone name is required.", "danger")
                return redirect(url_for(
                    "deliverymanager.edit_delivery_zone",
                    zone_id=zone.id
                ))

            # Prevent duplicate names (excluding current zone)
            existing = DeliveryZone.query.filter(
                DeliveryZone.name.ilike(name),
                DeliveryZone.id != zone.id
            ).first()

            if existing:
                flash("Another zone with this name already exists.", "warning")
                return redirect(url_for(
                    "deliverymanager.edit_delivery_zone",
                    zone_id=zone.id
                ))

            # =====================================================
            # COVERED AREAS (FROM TEXTAREA)
            # =====================================================

            raw_areas = request.form.get("covered_areas_raw", "")

            covered_areas = [
                a.strip().lower()
                for a in raw_areas.split("\n")
                if a.strip()
            ]

            if not covered_areas:
                flash("At least one covered area is required.", "danger")
                return redirect(url_for(
                    "deliverymanager.edit_delivery_zone",
                    zone_id=zone.id
                ))

            # =====================================================
            # UPDATE ZONE
            # =====================================================

            zone.name = name
            zone.town = town or None
            zone.city = city or None
            zone.covered_areas = covered_areas

            db.session.commit()

            flash("Delivery zone updated successfully.", "success")

            return redirect(url_for("deliverymanager.zones"))

        except Exception as e:
            db.session.rollback()
            print(f"[EDIT DELIVERY ZONE ERROR]: {e}")

            flash("Update failed.", "danger")

            return redirect(url_for(
                "deliverymanager.edit_delivery_zone",
                zone_id=zone.id
            ))

    return render_template(
        "deliverymanager/editdeliveryzone.html",
        zone=zone
    )



# =====================================================
# DELETE DELIVERY ZONE
# =====================================================
@deliverymanager_bp.route(
    "/delivery-zones/<int:zone_id>/delete",
    methods=["POST"]
)
@login_required
@role_required("DELIVERYMANAGER")
def delete_delivery_zone(zone_id):

    zone = DeliveryZone.query.get_or_404(zone_id)

    try:

        if not zone.is_active:

            flash(
                "Delivery zone already inactive.",
                "warning"
            )

            return redirect(
                url_for(
                    "deliverymanager.view_delivery_zone",
                    zone_id=zone.id
                )
            )

        # Soft delete
        zone.is_active = False

        db.session.commit()

        flash(
            "Delivery zone deleted successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print(f"[DELETE DELIVERY ZONE ERROR]: {e}")

        flash(
            "Delete failed.",
            "danger"
        )

    return redirect(
        url_for(
            "deliverymanager.zones"
        )
    )


# =====================================================
# RESTORE DELIVERY ZONE
# =====================================================
@deliverymanager_bp.route(
    "/delivery-zones/<int:zone_id>/restore",
    methods=["POST"]
)
@login_required
@role_required("DELIVERYMANAGER")
def restore_delivery_zone(zone_id):

    try:

        zone = DeliveryZone.query.get_or_404(zone_id)

        zone.is_active = True

        db.session.commit()

        flash(
            "Delivery zone restored successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print(f"[RESTORE DELIVERY ZONE ERROR]: {e}")

        flash("Restore failed.", "danger")

    return redirect(
        url_for(
            "deliverymanager.zones"
        )
    )

