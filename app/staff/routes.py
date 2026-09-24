# app/routes/staff.py

from flask import Blueprint, render_template, request, abort, flash, redirect, url_for
from flask_login import login_required, current_user

from sqlalchemy import func

from app.extensions import db
from app.models.order import Order, OrderStatus
from app.models.branchstaff import BranchStaff
from app.models.storebranch import StoreBranch
from app.models.inventory import Inventory
from app.models.productvariant import ProductVariant

from app.security.decorators import role_required
from app.util.audit_helper import log_action


staff_bp = Blueprint("staff", __name__, url_prefix="/staff")


# =====================================================
# STAFF DASHBOARD (ROLE-AWARE)
# =====================================================
@staff_bp.route("/dashboard")
@login_required
@role_required("staff")  # or "store_manager/inventory_manager/delivery_manager"
def dashboard():

    user = current_user

    # branches assigned to staff
    branch_links = BranchStaff.query.filter_by(user_id=user.id).all()
    branch_ids = [b.branch_id for b in branch_links]

    # orders in assigned branches
    orders = Order.query.filter(
        Order.branch_id.in_(branch_ids)
    ).order_by(Order.created_at.desc()).limit(20).all()

    total_orders = Order.query.filter(
        Order.branch_id.in_(branch_ids)
    ).count()

    pending_orders = Order.query.filter(
        Order.branch_id.in_(branch_ids),
        Order.status == OrderStatus.pending.value
    ).count()

    return render_template(
        "staff/dashboard.html",
        orders=orders,
        total_orders=total_orders,
        pending_orders=pending_orders
    )


# =====================================================
# STORE OVERVIEW (BY BRANCH)
# =====================================================
@staff_bp.route("/branches")
@login_required
@role_required("staff")
def branches():

    branch_links = BranchStaff.query.filter_by(user_id=current_user.id).all()

    branches = StoreBranch.query.filter(
        StoreBranch.id.in_([b.branch_id for b in branch_links])
    ).all()

    return render_template(
        "staff/branches.html",
        branches=branches
    )


# =====================================================
# BRANCH DETAIL VIEW
# =====================================================
@staff_bp.route("/branch/<int:branch_id>")
@login_required
@role_required("staff")
def branch_detail(branch_id):

    # security check: ensure staff belongs to branch
    allowed = BranchStaff.query.filter_by(
        user_id=current_user.id,
        branch_id=branch_id
    ).first()

    if not allowed:
        abort(403)

    branch = StoreBranch.query.get_or_404(branch_id)

    inventory = Inventory.query.filter_by(branch_id=branch_id).all()

    return render_template(
        "staff/branch_detail.html",
        branch=branch,
        inventory=inventory
    )


# =====================================================
# ORDERS FOR BRANCH
# =====================================================
@staff_bp.route("/orders/<int:branch_id>")
@login_required
@role_required("staff")
def branch_orders(branch_id):

    allowed = BranchStaff.query.filter_by(
        user_id=current_user.id,
        branch_id=branch_id
    ).first()

    if not allowed:
        abort(403)

    orders = Order.query.filter_by(
        branch_id=branch_id
    ).order_by(Order.created_at.desc()).all()

    return render_template(
        "staff/orders.html",
        orders=orders,
        branch_id=branch_id
    )


# =====================================================
# UPDATE ORDER STATUS (STAFF OPERATION)
# =====================================================
@staff_bp.route("/order/<int:order_id>/status", methods=["POST"])
@login_required
@role_required("staff")
def update_order_status(order_id):

    order = Order.query.get_or_404(order_id)

    new_status = request.form.get("status")

    allowed_statuses = [
        "processing",
        "collected",
        "shipped",
        "delivered"
    ]

    if new_status not in allowed_statuses:
        abort(400)

    # branch access check
    allowed = BranchStaff.query.filter_by(
        user_id=current_user.id,
        branch_id=order.branch_id
    ).first()

    if not allowed:
        abort(403)

    order.status = new_status
    db.session.commit()

    log_action(
        current_user.id,
        f"Updated order {order.id} to {new_status}",
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr)
    )

    flash("Order updated", "success")

    return redirect(request.referrer or url_for("staff.dashboard"))


# =====================================================
# LOW STOCK VIEW (INVENTORY ALERTS)
# =====================================================
@staff_bp.route("/inventory/low-stock")
@login_required
@role_required("staff")
def low_stock():

    branch_links = BranchStaff.query.filter_by(user_id=current_user.id).all()
    branch_ids = [b.branch_id for b in branch_links]

    low_stock_items = Inventory.query.filter(
        Inventory.branch_id.in_(branch_ids),
        Inventory.quantity <= Inventory.reserved_quantity + 5
    ).all()

    return render_template(
        "staff/low_stock.html",
        items=low_stock_items
    )