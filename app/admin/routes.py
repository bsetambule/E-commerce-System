from flask_login import login_required, current_user
from flask import Blueprint, render_template, redirect, url_for, abort, flash, request

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

from app.models.user import User
from app.models.order import Order
from app.models.role import Role
from app.models.branchstaff import BranchStaff
from app.models.storebranch import StoreBranch

from app.extensions import db
from app.security.decorators import role_required
from app.util.audit_helper import log_action, get_request_meta

from app.models.storebranch import StoreBranch

from argon2 import PasswordHasher

from app.constants.roles import (
    ALLOWED_ASSIGNABLE_ROLES,
    BRANCH_REQUIRED_ROLES,
    PROTECTED_ROLES
)

from app.models.courierprofile import CourierProfile
from app.models.staffprofile import StaffProfile
import os
import shlex

from app.models.delivery import Delivery, DeliveryStatus
import json

from app.models.audit import AuditLog
from sqlalchemy import desc

from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from app.models.orderitem import OrderItem
from app.models.product import Product
from app.models.courierprofile import CourierProfile
from app.models.customerprofile import CustomerProfile
from app.models.productsearch import ProductSearch

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ph = PasswordHasher()



# =====================================================
# DASHBOARD
# =====================================================
@admin_bp.route("/dashboard")
@login_required
@role_required("ADMIN")
def dashboard():

    # -----------------------------
    # USER COUNTS BY ROLE
    # -----------------------------
    customer_count = (
        db.session.query(User.id)
        .join(User.roles)
        .filter(Role.name == "CUSTOMER")
        .distinct()
        .count()
    )

    staff_count = (
        db.session.query(User.id)
        .join(User.roles)
        .filter(Role.name.in_(["STAFF", "PRODUCTMANAGER", "SYSTEMMANAGER", "STOREMANAGER", "DELIVERYMANAGER", "DELIVERYSUPERVISOR", "COURIER"]))
        .distinct()
        .count()
    )

    courier_count = (
        db.session.query(User.id)
        .join(User.roles)
        .filter(Role.name == "COURIER")
        .distinct()
        .count()
    )

    admin_count = (
        db.session.query(User.id)
        .join(User.roles)
        .filter(Role.name == "ADMIN")
        .distinct()
        .count()
    )

    # -----------------------------
    # ACTIVITY LOGS (RECENT FEED)
    # -----------------------------
    activity_logs = (
        AuditLog.query
        .order_by(desc(AuditLog.timestamp))
        .limit(20)
        .all()
    )


    # -----------------------------
    # BUSINESS COUNTS
    # -----------------------------
    store_count = StoreBranch.query.filter_by(is_deleted=False).count()
    order_count = Order.query.count()
    unassigned_deliveries_count = 0

    # -----------------------------
    # RECENT USERS
    # -----------------------------
    users = (
        User.query
        .order_by(User.id.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "admin/dashboard.html",

        customer_count=customer_count,
        staff_count=staff_count,
        courier_count=courier_count,
        admin_count=admin_count,

        store_count=store_count,
        order_count=order_count,
        unassigneddeliveries_count=unassigned_deliveries_count,

        users=users,
        activity_logs=activity_logs
    ) 


# =====================================================
# USERS (TAB SYSTEM)
# =====================================================
@admin_bp.route("/users")
@login_required
@role_required("ADMIN")
def list_users():
    page = request.args.get("page", 1, type=int)
    tab = request.args.get("tab", "all")

    query = User.query

    # -----------------------------
    # TAB FILTERING
    # -----------------------------
    if tab == "customers":
        query = query.filter(User.customer_profile.has())

    elif tab == "couriers":
        query = query.filter(User.courier_profile.has())

    elif tab == "staff":
        query = query.filter(User.staff_profile.has())

    # all = no filter

    users = query.order_by(User.id.desc()).paginate(
        page=page,
        per_page=25
    )

    return render_template(
        "admin/users.html",
        users=users,
        current_tab=tab
    )
 

# =====================================================
# VIEW COURIER PROFILE
# =====================================================
@admin_bp.route("/couriers/<int:user_id>")
@login_required
@role_required("ADMIN")
def view_courier(user_id):

    user = User.query.get_or_404(user_id)

    if not user.has_role("COURIER"):
        abort(404, "Not a courier")

    courier = user.courier_profile

    if not courier:
        abort(404, "Courier profile not found")

    # -----------------------------
    # METRICS (SAFE DEFAULT)
    # -----------------------------
    completed_deliveries = Delivery.query.filter_by(courier_id=courier.id, status="completed").count()
    return render_template(
        "admin/courierprofile.html",
        user=user,
        courier=courier,
        completed_deliveries=completed_deliveries
    )



# =====================================================
# VIEW CUSTOMER PROFILE
# =====================================================
@admin_bp.route("/customers/<int:user_id>")
@login_required
@role_required("ADMIN")
def view_customer(user_id):

    user = User.query.get_or_404(user_id)

    # -----------------------------
    # ENSURE CUSTOMER ROLE
    # -----------------------------
    if not user.has_role("CUSTOMER"):
        abort(404, "Not a customer")

    profile = user.customer_profile

    if not profile:
        abort(404, "Customer profile missing")

    # -----------------------------
    # ORDER STATS
    # -----------------------------
    total_orders = Order.query.filter_by(user_id=user.id).count()

    total_spent = db.session.query(
        func.coalesce(func.sum(Order.subtotal_amount), 0)
    ).filter(Order.user_id == user.id).scalar()

    last_order = (
        Order.query
        .filter_by(user_id=user.id)
        .order_by(Order.created_at.desc())
        .first()
    )

    orders = (
        Order.query
        .filter_by(user_id=user.id)
        .order_by(Order.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "admin/customerprofile.html",

        user=user,
        profile=profile,

        total_orders=total_orders,
        total_spent=round(total_spent or 0, 2),
        last_order_date=last_order.created_at if last_order else None,

        orders=orders
    )

# =====================================================
# VIEW STAFF PROFILE
# =====================================================
@admin_bp.route("/staff/<int:user_id>")
@login_required
@role_required("ADMIN")
def view_staff(user_id):

    user = (
        User.query
        .options(
            joinedload(User.staff_profile),
            joinedload(User.branch_staff).joinedload(BranchStaff.branch),
            joinedload(User.roles)
        )
        .get_or_404(user_id)
    )

    STAFF_ROLES = {
        "SYSTEMMANAGER",
        "PRODUCTMANAGER",
        "STAFF",
        "STOREMANAGER",
        "DELIVERYMANAGER",
        "DELIVERYSUPERVISOR"
    }

    # -----------------------------
    # ROLE CHECK
    # -----------------------------
    if not user.has_any_role(*STAFF_ROLES):
        abort(404, "Not a staff member")

    staff = user.staff_profile

    if not staff:
        abort(404, "Staff profile missing")

    assignments = user.branch_staff or []

    return render_template(
        "admin/staffprofile.html",
        user=user,
        staff=staff,
        assignments=assignments
    )


# =====================================================
# VIEW STORE PROFILE
# =====================================================
@admin_bp.route("/stores/<int:store_id>")
@login_required
@role_required("ADMIN")
def view_store(store_id):

    # -----------------------------
    # LOAD STORE + RELATIONSHIPS
    # -----------------------------
    storebranch = (
        StoreBranch.query
        .options(
            joinedload(StoreBranch.staff_members)
            .joinedload(BranchStaff.user)
            .joinedload(User.staff_profile),

            joinedload(StoreBranch.products),
            joinedload(StoreBranch.orders)
        )
        .get_or_404(store_id)
    )

    # -----------------------------
    # FIND STORE MANAGER (IF ANY)
    # -----------------------------
    manager = None

    for staff in storebranch.staff_members:
        if staff.role == "STOREMANAGER":
            manager = staff.user
            break

    # -----------------------------
    # BASIC METRICS (SAFE)
    # -----------------------------
    total_orders = len(storebranch.orders) if storebranch.orders else 0
    total_products = len(storebranch.products) if storebranch.products else 0

    # revenue placeholder (replace with real aggregation later)
    total_revenue = 0

    # -----------------------------
    # RETURN
    # -----------------------------
    return render_template(
        "admin/storeprofile.html",
        store=storebranch,
        manager=manager,
        total_orders=total_orders,
        total_products=total_products,
        total_revenue=total_revenue
    )



# =====================================================
# CREATE USER 
# =====================================================
@admin_bp.route("/users/createuser", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def create_user():

    branches = StoreBranch.query.filter_by(is_deleted=False).all()

    if request.method == "POST":

        first_name = request.form.get("firstName", "").strip()
        last_name = request.form.get("lastName", "").strip()
        email = request.form.get("email", "").strip().lower()
        country_code = request.form.get("countryCode")
        phone = request.form.get("phone", "").strip()
        role_name = request.form.get("role")
        branch_id = request.form.get("branch_id")

        full_phone = f"{country_code}{phone}" if phone else None
        meta = get_request_meta()

        if not all([first_name, last_name, email, role_name]):
            flash("Missing required fields", "warning")
            return redirect(url_for("admin.create_user"))

        if User.query.filter_by(email=email).first():
            flash("Email already exists", "warning")
            return redirect(url_for("admin.create_user"))

        if full_phone and User.query.filter_by(phone_number=full_phone).first():
            flash("Phone already exists", "warning")
            return redirect(url_for("admin.create_user"))

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            abort(400, "Invalid role")

        if role_name not in ALLOWED_ASSIGNABLE_ROLES:
            abort(403, "Role not assignable")

        requires_branch = role_name in BRANCH_REQUIRED_ROLES

        if requires_branch and not branch_id:
            flash("Branch is required for this role", "warning")
            return redirect(url_for("admin.create_user"))

        try:
            # -----------------------------
            # CREATE USER
            # -----------------------------
            user = User(
                email=email,
                phone_number=full_phone,
                is_active=True,
                email_verified=True
            )

            user.password = "admin12345"
            user.roles.append(role)

            db.session.add(user)
            db.session.flush()

            # -----------------------------
            # PROFILE
            # -----------------------------
            if role_name == "COURIER":
                profile = CourierProfile(
                    user_id=user.id,
                    first_name=first_name,
                    last_name=last_name
                )
            else:
                profile = StaffProfile(
                    user_id=user.id,
                    first_name=first_name,
                    last_name=last_name
                )

            db.session.add(profile)

            # -----------------------------
            # BRANCH ASSIGNMENT
            # -----------------------------
            if requires_branch:
                branch = StoreBranch.query.get(branch_id)

                if not branch or branch.is_deleted:
                    abort(404, "Branch not found")

                db.session.add(BranchStaff(
                    user_id=user.id,
                    branch_id=branch.id,
                    role=role_name
                ))

            # -----------------------------
            # AUDIT LOG
            # -----------------------------
            log_action(
                user_id=current_user.id,
                action="Created user",
                entity_type="User",
                entity_id=user.id,
                ip_address=meta["ip"],
                user_agent=meta["user_agent"],
                meta_data={
                    "email": email,
                    "role": role_name,
                    "branch_id": branch_id
                }
            )

            db.session.commit()

            flash("User created successfully", "success")
            return redirect(url_for("admin.list_users"))

        except Exception as e:
            db.session.rollback()
            print(e)
            abort(500)

    return render_template("admin/createuser.html", branches=branches)


# =====================================================
# EDIT USER
# =====================================================
@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def update_user(user_id):

    user = User.query.get_or_404(user_id)
    branches = StoreBranch.query.filter_by(is_deleted=False).all()

    if request.method == "POST":

        first_name = request.form.get("firstName", "").strip()
        last_name = request.form.get("lastName", "").strip()
        email = request.form.get("email", "").strip().lower()
        country_code = request.form.get("countryCode")
        phone = request.form.get("phone", "").strip()
        role_name = request.form.get("role")
        branch_id = request.form.get("branch_id")

        full_phone = f"{country_code}{phone}" if phone else None
        meta = get_request_meta()

        if not all([first_name, last_name, email, role_name]):
            flash("Missing required fields", "warning")
            return redirect(request.url)

        if User.query.filter(User.email == email, User.id != user.id).first():
            flash("Email already exists", "warning")
            return redirect(request.url)

        if full_phone and User.query.filter(
            User.phone_number == full_phone,
            User.id != user.id
        ).first():
            flash("Phone already exists", "warning")
            return redirect(request.url)

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            abort(400, "Invalid role")

        if role_name not in ALLOWED_ASSIGNABLE_ROLES:
            abort(403, "Role not assignable")

        requires_branch = role_name in BRANCH_REQUIRED_ROLES

        if requires_branch and not branch_id:
            flash("Branch is required for this role", "warning")
            return redirect(request.url)

        # -----------------------------
        # BEFORE STATE
        # -----------------------------
        before = {
            "email": user.email,
            "phone": user.phone_number,
            "role": user.roles[0].name if user.roles else None,
            "first_name": getattr(user.staff_profile or user.courier_profile, "first_name", None),
            "last_name": getattr(user.staff_profile or user.courier_profile, "last_name", None),
            "branch_id": user.branch_staff[0].branch_id if user.branch_staff else None
        }

        try:
            # -----------------------------
            # UPDATE CORE
            # -----------------------------
            user.email = email
            user.phone_number = full_phone

            user.roles.clear()
            user.roles.append(role)

            # -----------------------------
            # PROFILE HANDLING
            # -----------------------------
            if role_name == "COURIER":

                if user.staff_profile:
                    db.session.delete(user.staff_profile)

                profile = user.courier_profile or CourierProfile(user_id=user.id)
                profile.first_name = first_name
                profile.last_name = last_name
                db.session.add(profile)

            else:

                if user.courier_profile:
                    db.session.delete(user.courier_profile)

                profile = user.staff_profile or StaffProfile(user_id=user.id)
                profile.first_name = first_name
                profile.last_name = last_name
                db.session.add(profile)

            # -----------------------------
            # BRANCH RESET
            # -----------------------------
            BranchStaff.query.filter_by(user_id=user.id).delete()

            if requires_branch:
                branch = StoreBranch.query.get(branch_id)

                if not branch or branch.is_deleted:
                    abort(404, "Branch not found")

                db.session.add(BranchStaff(
                    user_id=user.id,
                    branch_id=branch.id,
                    role=role_name
                ))

            # -----------------------------
            # AFTER STATE
            # -----------------------------
            after = {
                "email": email,
                "phone": full_phone,
                "role": role_name,
                "first_name": first_name,
                "last_name": last_name,
                "branch_id": int(branch_id) if branch_id else None
            }

            changes = {
                k: {"old": before[k], "new": after[k]}
                for k in before
                if before[k] != after[k]
            }

            # -----------------------------
            # AUDIT
            # -----------------------------
            if changes:
                log_action(
                    user_id=current_user.id,
                    action="Updated user",
                    entity_type="User",
                    entity_id=user.id,
                    ip_address=meta["ip"],
                    user_agent=meta["user_agent"],
                    meta_data={"changes": changes}
                )

            db.session.commit()

            flash("User updated successfully", "success")
            return redirect(url_for("admin.list_users"))

        except Exception as e:
            db.session.rollback()
            print(e)
            abort(500)

    return render_template("admin/edituser.html", user=user, branches=branches)


# =====================================================
# USER STATUS MANAGEMENT
# freeze | unfreeze | delete | restore
# =====================================================
@admin_bp.route("/users/<int:user_id>/status", methods=["POST"])
@login_required
@role_required("ADMIN")
def update_user_status(user_id):

    user = User.query.get_or_404(user_id)

    action = request.form.get("action")

    ALLOWED_ACTIONS = {
        "freeze",
        "unfreeze",
        "delete",
        "restore"
    }

    if action not in ALLOWED_ACTIONS:
        abort(400, "Invalid action")

    # -----------------------------
    # PREVENT SELF-DESTRUCT
    # -----------------------------
    if user.id == current_user.id and action in {
        "freeze",
        "delete"
    }:
        flash(
            "You cannot freeze or delete your own account.",
            "warning"
        )
        return redirect(url_for("admin.list_users"))

    meta = get_request_meta()

    try:

        # -----------------------------
        # BEFORE STATE
        # -----------------------------
        before = {
            "is_active": user.is_active,
            "is_frozen": user.is_frozen,
            "is_deleted": user.is_deleted,
            "email": user.email,
            "phone_number": user.phone_number
        }

        # =====================================================
        # FREEZE
        # =====================================================
        if action == "freeze":

            if user.is_deleted:
                flash("Deleted users cannot be frozen.", "warning")
                return redirect(url_for("admin.list_users"))

            user.is_frozen = True
            user.is_active = False

        # =====================================================
        # UNFREEZE
        # =====================================================
        elif action == "unfreeze":

            if user.is_deleted:
                flash("Deleted users cannot be unfrozen.", "warning")
                return redirect(url_for("admin.list_users"))

            user.is_frozen = False
            user.is_active = True

            user.failed_attempts = 0
            user.locked_until = None

        # =====================================================
        # DELETE (SOFT DELETE)
        # =====================================================
        elif action == "delete":

            if user.is_deleted:
                flash("User already deleted.", "warning")
                return redirect(url_for("admin.list_users"))

            user.is_deleted = True
            user.is_active = False
            user.is_frozen = True

            # prevent uniqueness conflicts
            user.email = f"deleted_{user.id}_{user.email}"

            if user.phone_number:
                user.phone_number = (
                    f"deleted_{user.id}_{user.phone_number}"
                )

            # remove branch assignments
            BranchStaff.query.filter_by(
                user_id=user.id
            ).delete()

        # =====================================================
        # RESTORE
        # =====================================================
        elif action == "restore":

            if not user.is_deleted:
                flash("User is not deleted.", "warning")
                return redirect(url_for("admin.list_users"))

            user.is_deleted = False
            user.is_active = True
            user.is_frozen = False

            # NOTE:
            # email restoration should be manual if needed
            # because original email may already be reused

        # -----------------------------
        # AFTER STATE
        # -----------------------------
        after = {
            "is_active": user.is_active,
            "is_frozen": user.is_frozen,
            "is_deleted": user.is_deleted,
            "email": user.email,
            "phone_number": user.phone_number
        }

        # -----------------------------
        # AUDIT LOG
        # -----------------------------
        log_action(
            user_id=current_user.id,
            action=f"{action.upper()} USER",
            entity_type="User",
            entity_id=user.id,
            ip_address=meta["ip"],
            user_agent=meta["user_agent"],
            meta_data={
                "before": before,
                "after": after
            }
        )

        db.session.commit()

        flash(
            f"User {action}d successfully.",
            "success"
        )

        return redirect(url_for("admin.list_users"))

    except Exception as e:

        db.session.rollback()

        print(e)

        flash(
            "Failed to update user status.",
            "danger"
        )

        return redirect(url_for("admin.list_users"))

# =====================================================
# ACTIVATE / DEACTIVATE USER
# =====================================================
@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@role_required("ADMIN")
def toggle_user_active(user_id):

    user = User.query.get_or_404(user_id)

    action = request.form.get("action")

    if action not in {"activate", "deactivate"}:
        abort(400, "Invalid action")

    # -----------------------------
    # PREVENT SELF-DEACTIVATION
    # -----------------------------
    if user.id == current_user.id and action == "deactivate":
        flash("You cannot deactivate your own account.", "warning")
        return redirect(url_for("admin.list_users"))

    meta = get_request_meta()

    try:

        old_value = user.is_active

        # -----------------------------
        # TOGGLE ACTIVE STATE
        # -----------------------------
        if action == "activate":
            user.is_active = True

        else:
            user.is_active = False

            # Optional security reset
            user.reset_security_state()

        new_value = user.is_active

        # -----------------------------
        # AUDIT LOG
        # -----------------------------
        log_action(
            user_id=current_user.id,
            action=f"{action.upper()} USER",
            entity_type="User",
            entity_id=user.id,
            ip_address=meta["ip"],
            user_agent=meta["user_agent"],
            meta_data={
                "before": {
                    "is_active": old_value
                },
                "after": {
                    "is_active": new_value
                }
            }
        )

        db.session.commit()

        flash(f"User {action}d successfully.", "success")

        return redirect(url_for("admin.list_users"))

    except Exception as e:

        db.session.rollback()

        print(e)

        flash("Failed to update user status.", "danger")

        return redirect(url_for("admin.list_users"))



# =====================================================
# LIST STORES (TAB STYLE)
# =====================================================
@admin_bp.route("/stores")
@login_required
@role_required("ADMIN")
def list_stores():
    page = request.args.get("page", 1, type=int)
    tab = request.args.get("tab", "all")

    query = StoreBranch.query.filter_by(is_deleted=False)

    # -----------------------------
    # TAB FILTERING
    # -----------------------------
    if tab == "active":
        query = query.filter(StoreBranch.is_active == True)

    elif tab == "delivery":
        query = query.filter(StoreBranch.allows_delivery == True)

    # default = all

    stores = query.order_by(StoreBranch.id.desc()).paginate(
        page=page,
        per_page=25
    )

    return render_template(
        "admin/stores.html",
        stores=stores,
        current_tab=tab
    )

# =====================================================
# CREATE STORE
# =====================================================
@admin_bp.route("/stores/createstore", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def create_store():

    if request.method == "POST":

        try:

            # =====================================================
            # FORM DATA
            # =====================================================

            name = request.form.get("name", "").strip()
            address = request.form.get("address", "").strip()
            city = request.form.get("city", "").strip()

            latitude = request.form.get("latitude")
            longitude = request.form.get("longitude")

            allows_delivery = (
                request.form.get("allowsdelivery") == "true"
            )

            meta = get_request_meta()

            # =====================================================
            # VALIDATION
            # =====================================================

            if not all([name, address, city]):

                flash("Missing required fields", "warning")

                return redirect(
                    url_for("admin.create_store")
                )

            # =====================================================
            # SAFE FLOAT PARSER
            # =====================================================

            def safe_float(value):

                try:
                    return (
                        float(value)
                        if value not in (None, "")
                        else None
                    )

                except (ValueError, TypeError):
                    return None

            # =====================================================
            # CREATE STORE
            # =====================================================

            store = StoreBranch(
                name=name,
                address=address,
                city=city,
                latitude=safe_float(latitude),
                longitude=safe_float(longitude),
                allows_delivery=allows_delivery,
                is_active=True,
                is_deleted=False
            )

            db.session.add(store)

            # Ensures store.id exists
            db.session.flush()

            # =====================================================
            # AUDIT LOG
            # =====================================================

            log_action(
                user_id=current_user.id,
                email=current_user.email,
                action="Store created",
                entity_type="StoreBranch",
                entity_id=store.id,
                ip_address=meta["ip"],
                user_agent=meta["user_agent"],
                meta_data={
                    "store_name": store.name,
                    "address": store.address,
                    "city": store.city,
                    "latitude": store.latitude,
                    "longitude": store.longitude,
                    "allows_delivery": store.allows_delivery
                }
            )

            # =====================================================
            # COMMIT EVERYTHING
            # =====================================================

            db.session.commit()

            flash(
                "Store created successfully",
                "success"
            )

            return redirect(
                url_for("admin.list_stores")
            )

        except Exception as e:

            db.session.rollback()

            import traceback
            traceback.print_exc()

            flash(
                "Failed to create store",
                "danger"
            )

            return redirect(
                url_for("admin.create_store")
            )

    return render_template(
        "admin/createstore.html"
    )

# =====================================================
# EDIT STORE (WITH AUDIT DIFF)
# =====================================================
@admin_bp.route("/stores/<int:store_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def update_store(store_id):

    store = StoreBranch.query.get_or_404(store_id)

    if request.method == "POST":

        try:

            name = request.form.get("name", "").strip()
            address = request.form.get("address", "").strip()
            city = request.form.get("city")

            latitude = request.form.get("latitude")
            longitude = request.form.get("longitude")

            allows_delivery = (
                request.form.get("allows_delivery") == "true"
            )

            meta = get_request_meta()

            if not all([name, address, city]):
                flash("Missing required fields", "warning")
                return redirect(request.url)

            def safe_float(v):
                try:
                    return float(v) if v not in (None, "") else None
                except ValueError:
                    return None

            # -----------------------------
            # BEFORE
            # -----------------------------
            before = {
                "name": store.name,
                "address": store.address,
                "city": store.city,
                "latitude": store.latitude,
                "longitude": store.longitude,
                "allows_delivery": store.allows_delivery,
            }

            # -----------------------------
            # UPDATE
            # -----------------------------
            store.name = name
            store.address = address
            store.city = city
            store.latitude = safe_float(latitude)
            store.longitude = safe_float(longitude)
            store.allows_delivery = allows_delivery

            db.session.commit()

            # -----------------------------
            # AFTER
            # -----------------------------
            after = {
                "name": store.name,
                "address": store.address,
                "city": store.city,
                "latitude": store.latitude,
                "longitude": store.longitude,
                "allows_delivery": store.allows_delivery,
            }

            # -----------------------------
            # DIFF
            # -----------------------------
            diff = {
                k: {"old": before[k], "new": after[k]}
                for k in before
                if before[k] != after[k]
            }

            # IMPORTANT: ensure clean session state
            db.session.expire_all()

            # -----------------------------
            # AUDIT LOG (NEW CLEAN WRITE)
            # -----------------------------
            log_action(
                user_id=current_user.id,
                email=current_user.email,
                action="Updated store",
                entity_type="StoreBranch",
                entity_id=store.id,
                ip_address=meta["ip"],
                user_agent=meta["user_agent"],
                meta_data={"changes": diff}
            )

            db.session.commit()

            flash("Store updated successfully", "success")

            return redirect(url_for("admin.list_stores"))

        except Exception as e:
            db.session.rollback()

            import traceback
            traceback.print_exc()

            flash("Failed to update store", "danger")
            return redirect(request.url)

    return render_template("admin/editstore.html", store=store)


# =====================================================
# STORE STATUS MANAGEMENT
# activate | deactivate | delete | restore
# =====================================================
@admin_bp.route("/stores/<int:store_id>/toggle", methods=["POST"])
@login_required
@role_required("ADMIN")
def toggle_store_status(store_id):

    store = StoreBranch.query.get_or_404(store_id)

    action = request.form.get("action")

    if action not in {"activate", "deactivate", "delete", "restore"}:
        abort(400, "Invalid action")

    meta = get_request_meta()

    try:
        # -----------------------------
        # PREVIOUS STATE
        # -----------------------------
        before = {
            "is_active": store.is_active,
            "is_deleted": store.is_deleted
        }

        # -----------------------------
        # ACTIVATE
        # -----------------------------
        if action == "activate":

            if store.is_deleted:
                flash("Cannot activate a deleted store", "warning")
                return redirect(url_for("admin.list_stores"))

            store.is_active = True

        # -----------------------------
        # DEACTIVATE
        # -----------------------------
        elif action == "deactivate":

            if store.is_deleted:
                flash("Cannot deactivate a deleted store", "warning")
                return redirect(url_for("admin.list_stores"))

            store.is_active = False

        # -----------------------------
        # SOFT DELETE
        # -----------------------------
        elif action == "delete":

            if store.is_deleted:
                flash("Store already deleted", "warning")
                return redirect(url_for("admin.list_stores"))

            store.is_deleted = True
            store.is_active = False

        # -----------------------------
        # RESTORE
        # -----------------------------
        elif action == "restore":

            if not store.is_deleted:
                flash("Store is not deleted", "warning")
                return redirect(url_for("admin.list_stores"))

            store.is_deleted = False
            store.is_active = True

        # -----------------------------
        # NEW STATE
        # -----------------------------
        after = {
            "is_active": store.is_active,
            "is_deleted": store.is_deleted
        }

        db.session.commit()

        # -----------------------------
        # AUDIT LOG
        # -----------------------------
        log_action(
            user_id=current_user.id,
            action=f"{action.upper()} store {store.id}",
            entity_type="StoreBranch",
            entity_id=store.id,
            ip_address=meta["ip"],
            user_agent=meta["user_agent"],
            meta_data={
                "before": before,
                "after": after
            }
        )

        flash(f"Store {action} successful", "success")
        return redirect(url_for("admin.list_stores"))

    except Exception as e:
        db.session.rollback()
        print(e)
        abort(500)
        

# =====================================================
# ORDERS
# =====================================================
@admin_bp.route("/orders")
@login_required
@role_required("ADMIN")
def list_orders():
    page = request.args.get("page", 1, type=int)
    tab = request.args.get("tab", "all")

    query = Order.query.options(
        joinedload(Order.user)
    )

    # -----------------------------
    # TAB FILTERS
    # -----------------------------
    if tab == "delivery":
        query = query.filter(Order.is_delivery == True)

    elif tab == "pickup":
        query = query.filter(Order.is_delivery == False)

    orders = query.order_by(Order.created_at.desc()).paginate(
        page=page,
        per_page=25
    )

    return render_template(
        "admin/orders.html",
        orders=orders,
        current_tab=tab
    )

# =====================================================
# ORDER DETAILS
# =====================================================

@admin_bp.route("/orders/<int:order_id>")
@login_required
@role_required("ADMIN")
def order_detail(order_id):

    order = Order.query.options(
        joinedload(Order.user),
        joinedload(Order.items),
        joinedload(Order.branch),
        joinedload(Order.delivery).joinedload(Delivery.courier)
    ).filter_by(id=order_id).first_or_404()

    return render_template(
        "admin/orderdetails.html",
        order=order
    )




# =====================================================
# ANALYTICS
# =====================================================
@admin_bp.route("/analytics")
@login_required
@role_required("ADMIN")
def analytics():

    # =================================================
    # RANGE FILTER
    # =================================================
    days = request.args.get("range", 30, type=int)
    start_date = datetime.utcnow() - timedelta(days=days)

    # =================================================
    # FILTERED ORDERS
    # =================================================
    orders_q = Order.query.filter(
        Order.created_at >= start_date
    )

    total_orders = orders_q.count()

    total_gmv = (
        db.session.query(func.sum(Order.subtotal_amount))
        .filter(Order.created_at >= start_date)
        .scalar()
    ) or 0

    avg_order_value = (
        total_gmv / total_orders
        if total_orders else 0
    )

    # =================================================
    # CUSTOMER COUNT
    # =================================================
    customer_count = (
        db.session.query(User.id)
        .join(User.roles)
        .filter(Role.name == "CUSTOMER")
        .distinct()
        .count()
    )

    # =================================================
    # DELIVERY SUCCESS
    # =================================================
    total_deliveries = (
        Delivery.query.filter(
            Delivery.created_at >= start_date
        ).count()
    )

    successful_deliveries = (
        Delivery.query.filter(
            Delivery.created_at >= start_date,
            Delivery.status == DeliveryStatus.DELIVERED
        ).count()
    )

    delivery_success = round(
        (successful_deliveries / total_deliveries) * 100,
        1
    ) if total_deliveries else 0

    # =================================================
    # KPIs
    # =================================================
    kpis = {
        "revenue": round(float(total_gmv), 2),
        "orders": total_orders,
        "customers": customer_count,
        "delivery_success": delivery_success,
        "avg_order_value": round(float(avg_order_value), 2)
    }

    # =================================================
    # TOP SELLING PRODUCTS
    # =================================================
    top_products = (
        db.session.query(
            Product.name.label("name"),
            StoreBranch.name.label("store"),
            func.count(OrderItem.id).label("orders"),
            func.sum(OrderItem.total_price).label("revenue")
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(StoreBranch, StoreBranch.id == OrderItem.branch_id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.created_at >= start_date)
        .group_by(Product.id, StoreBranch.id)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(10)
        .all()
    )

    # =================================================
    # MOST SEARCHED PRODUCTS
    # =================================================
    searched_products = (
        db.session.query(
            ProductSearch.query.label("name"),
            func.count(ProductSearch.id).label("search_count")
        )
        .filter(ProductSearch.query.isnot(None))
        .group_by(ProductSearch.query)
        .order_by(func.count(ProductSearch.id).desc())
        .limit(10)
        .all()
    )

    # =================================================
    # TOP STORES
    # =================================================
    top_stores = (
        db.session.query(
            StoreBranch.name.label("name"),
            func.sum(Order.subtotal_amount).label("revenue"),
            func.count(Order.id).label("orders")
        )
        .join(Order, Order.branch_id == StoreBranch.id)
        .filter(Order.created_at >= start_date)
        .group_by(StoreBranch.id)
        .order_by(func.sum(Order.subtotal_amount).desc())
        .limit(10)
        .all()
    )

    # =================================================
    # COURIER PERFORMANCE
    # =================================================
    courier_stats = (
        db.session.query(
            CourierProfile.first_name.label("first_name"),
            CourierProfile.last_name.label("last_name"),
            func.count(Delivery.id).label("deliveries")
        )
        .join(User, User.id == CourierProfile.user_id)
        .join(Delivery, Delivery.courier_id == User.id)
        .filter(Delivery.created_at >= start_date)
        .group_by(CourierProfile.id)
        .order_by(func.count(Delivery.id).desc())
        .limit(10)
        .all()
    )

    # =================================================
    # TOP CUSTOMERS
    # =================================================
    top_customers = (
        db.session.query(
            CustomerProfile.first_name.label("first_name"),
            CustomerProfile.last_name.label("last_name"),
            func.count(Order.id).label("orders"),
            func.sum(Order.subtotal_amount).label("spend")
        )
        .join(User, User.id == CustomerProfile.user_id)
        .join(Order, Order.user_id == User.id)
        .filter(Order.created_at >= start_date)
        .group_by(CustomerProfile.id)
        .order_by(func.sum(Order.subtotal_amount).desc())
        .limit(10)
        .all()
    )

    # =================================================
    # RETURN TEMPLATE
    # =================================================
    return render_template(
        "admin/analytics.html",

        kpis=kpis,
        selected_range=days,

        top_products=top_products,
        searched_products=searched_products,
        top_stores=top_stores,
        courier_stats=courier_stats,
        top_customers=top_customers
    )






# =====================================================
# DELIVERIES LIST
# =====================================================
@admin_bp.route("/deliveries")
@login_required
@role_required("ADMIN")
def deliveries():

    page = request.args.get("page", 1, type=int)
    filter_type = request.args.get("filter", "all")

    query = Delivery.query.options(
        joinedload(Delivery.order).joinedload(Order.user),
        joinedload(Delivery.courier)
    )

    # -----------------------------
    # FILTERS
    # -----------------------------
    if filter_type == "unassigned":
        query = query.filter(Delivery.courier_id.is_(None))

    elif filter_type == "assigned":
        query = query.filter(Delivery.courier_id.isnot(None))

    deliveries = query.order_by(
        Delivery.created_at.desc()
    ).paginate(
        page=page,
        per_page=25
    )

    return render_template(
        "admin/deliveries.html",
        deliveries=deliveries,
        current_filter=filter_type
    )


# =====================================================
# DELIVERY DETAILS
# =====================================================
@admin_bp.route("/deliveries/<int:delivery_id>")
@login_required
@role_required("ADMIN")
def delivery_detail(delivery_id):

    delivery = Delivery.query.options(
        joinedload(Delivery.order).joinedload(Order.user),
        joinedload(Delivery.order).joinedload(Order.items),
        joinedload(Delivery.courier),
        joinedload(Delivery.branch)
    ).filter_by(id=delivery_id).first_or_404()

    return render_template(
        "admin/deliverydetails.html",
        delivery=delivery
    )


# =====================================================
# ACTIVITY
# =====================================================
@admin_bp.route("/activity")
@login_required
@role_required("ADMIN")
def activity():

    # -----------------------------
    # PAGINATION
    # -----------------------------
    page = request.args.get("page", 1, type=int)
    per_page = 25

    # -----------------------------
    # QUERY AUDIT LOGS
    # -----------------------------
    activity_logs = (
        AuditLog.query
        .order_by(desc(AuditLog.timestamp))
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        "admin/activity.html",
        activity_logs=activity_logs
    )