# app/routes/inventory_manager.py

from flask import Blueprint, render_template, redirect, url_for, request, abort, flash
from flask_login import login_required, current_user

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_

from app.extensions import db
from app.security.decorators import role_required
from app.util.audit_helper import log_action

from app.models.branchstaff import BranchStaff
from app.models.inventory import Inventory
from app.models.inventoryreservation import InventoryReservation
from app.models.productvariant import ProductVariant

inventorymanager_bp = Blueprint(
    "inventory_manager",
    __name__,
    url_prefix="/inventory"
)


# -----------------------------
# HELPER: GET INVENTORY MANAGER BRANCH
# -----------------------------
def get_inventory_branch():
    staff = BranchStaff.query.filter_by(
        user_id=current_user.id,
        role="inventory_manager"
    ).first()

    if not staff:
        abort(403, "No branch assigned")

    return staff.branch


# -----------------------------
# DASHBOARD
# -----------------------------
@inventorymanager_bp.route("/dashboard")
@login_required
@role_required("inventory_manager")
def dashboard():
    branch = get_inventory_branch()

    total_items = Inventory.query.filter_by(branch_id=branch.id).count()

    low_stock = Inventory.query.filter(
        Inventory.branch_id == branch.id,
        Inventory.quantity < 10
    ).count()

    reserved = Inventory.query.filter(
        Inventory.branch_id == branch.id,
        Inventory.reserved_quantity > 0
    ).count()

    return render_template(
        "inventory/dashboard.html",
        branch=branch,
        total_items=total_items,
        low_stock=low_stock,
        reserved=reserved
    )


# -----------------------------
# VIEW INVENTORY
# -----------------------------
@inventorymanager_bp.route("/")
@login_required
@role_required("inventory_manager")
def list_inventory():
    branch = get_inventory_branch()

    inventory = Inventory.query.filter_by(branch_id=branch.id).all()

    return render_template(
        "inventory/list.html",
        inventory=inventory,
        branch=branch
    )


# -----------------------------
# UPDATE STOCK
# -----------------------------
@inventorymanager_bp.route("/<int:id>/update", methods=["POST"])
@login_required
@role_required("inventory_manager")
def update_stock(id):
    branch = get_inventory_branch()

    item = Inventory.query.get_or_404(id)

    if item.branch_id != branch.id:
        abort(403)

    new_quantity = request.form.get("quantity", type=int)
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    if new_quantity is None or new_quantity < 0:
        flash("Invalid quantity", "danger")
        return redirect(url_for("inventory_manager.list_inventory"))

    try:
        with db.session.begin():
            if new_quantity < item.reserved_quantity:
                flash("Cannot reduce below reserved stock", "warning")
                return redirect(url_for("inventory_manager.list_inventory"))

            item.quantity = new_quantity

        log_action(
            current_user.id,
            f"Updated stock variant={item.variant_id} → {new_quantity}",
            ip_address=ip
        )

        flash("Stock updated", "success")

    except SQLAlchemyError:
        db.session.rollback()
        abort(500)

    return redirect(url_for("inventory_manager.list_inventory"))


# -----------------------------
# ADD INVENTORY ITEM
# -----------------------------
@inventorymanager_bp.route("/add", methods=["GET", "POST"])
@login_required
@role_required("inventory_manager")
def add_inventory():
    branch = get_inventory_branch()

    variants = ProductVariant.query.all()

    if request.method == "POST":
        variant_id = request.form.get("variant_id")
        quantity = request.form.get("quantity", type=int)

        ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        if not variant_id or quantity is None:
            flash("All fields required", "warning")
            return redirect(url_for("inventory_manager.add_inventory"))

        existing = Inventory.query.filter_by(
            branch_id=branch.id,
            variant_id=variant_id
        ).first()

        if existing:
            flash("Inventory already exists", "info")
            return redirect(url_for("inventory_manager.list_inventory"))

        try:
            with db.session.begin():
                item = Inventory(
                    branch_id=branch.id,
                    variant_id=variant_id,
                    quantity=quantity,
                    reserved_quantity=0
                )

                db.session.add(item)

            log_action(
                current_user.id,
                f"Added inventory variant={variant_id} qty={quantity}",
                ip_address=ip
            )

            flash("Inventory added", "success")
            return redirect(url_for("inventory_manager.list_inventory"))

        except SQLAlchemyError:
            db.session.rollback()
            abort(500)

    return render_template(
        "inventory/add.html",
        variants=variants,
        branch=branch
    )


# -----------------------------
# VIEW RESERVATIONS
# -----------------------------
@inventorymanager_bp.route("/reservations")
@login_required
@role_required("inventory_manager")
def reservations():
    branch = get_inventory_branch()

    reservations = InventoryReservation.query.join(Inventory).filter(
        Inventory.branch_id == branch.id
    ).all()

    return render_template(
        "inventory/reservations.html",
        reservations=reservations,
        branch=branch
    )


# -----------------------------
# RELEASE RESERVATION (MANUAL)
# -----------------------------
@inventorymanager_bp.route("/reservations/<int:id>/release", methods=["POST"])
@login_required
@role_required("inventory_manager")
def release_reservation(id):
    branch = get_inventory_branch()

    reservation = InventoryReservation.query.get_or_404(id)
    inventory = Inventory.query.filter_by(
        variant_id=reservation.variant_id,
        branch_id=branch.id
    ).first()

    if not inventory:
        abort(404)

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    try:
        with db.session.begin():
            if reservation.status != "reserved":
                flash("Reservation already processed", "warning")
                return redirect(url_for("inventory_manager.reservations"))

            inventory.reserved_quantity -= reservation.quantity
            reservation.status = "released"

        log_action(
            current_user.id,
            f"Released reservation {reservation.id}",
            ip_address=ip
        )

        flash("Reservation released", "success")

    except SQLAlchemyError:
        db.session.rollback()
        abort(500)

    return redirect(url_for("inventory_manager.reservations"))