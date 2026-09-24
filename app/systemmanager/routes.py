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

systemmanager_bp = Blueprint("systemmanager", __name__, url_prefix="/systemmanager")

ph = PasswordHasher()

# =====================================================
# DASHBOARD
# =====================================================
@systemmanager_bp.route("/dashboard")
@login_required
@role_required("SYSTEMMANAGER")
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
        .filter(Role.name.in_([
            "STAFF", 
            "STOREMANAGER", 
            "DELIVERYMANAGER",
            "PRODUCTMANAGER", 
            "DELIVERYSUPERVISOR",
            "COURIER"
            ])
        )
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
        .filter(Role.name == "SYSTEMMANAGER")
        .distinct()
        .count()
    )
    # -----------------------------
    # ACTIVITY LOGS (RECENT FEED)
    # -----------------------------
    activity_logs = (
        AuditLog.query
        .join(User, AuditLog.user_id == User.id)
        .filter(
            ~User.roles.any(Role.name == "ADMIN")
        )
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
        "systemmanager/dashboard.html",
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
@systemmanager_bp.route("/users")
@login_required
@role_required("SYSTEMMANAGER")
def users():
    page = request.args.get("page", 1, type=int)
    tab = request.args.get("tab", "all")
    query = User.query.filter(
        ~User.roles.any(Role.name == "ADMIN")
    )
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
        "systemmanager/users.html",
        users=users,
        current_tab=tab
    )
 

# =====================================================
# VIEW COURIER PROFILE
# =====================================================
@systemmanager_bp.route("/couriers/<int:user_id>")
@login_required
@role_required("SYSTEMMANAGER")
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
        "systemmanager/courierprofile.html",
        user=user,
        courier=courier,
        completed_deliveries=completed_deliveries
    )


# =====================================================
# VIEW CUSTOMER PROFILE
# =====================================================
@systemmanager_bp.route("/customers/<int:user_id>")
@login_required
@role_required("SYSTEMMANAGER")
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
        "systemmanager/customerprofile.html",
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
@systemmanager_bp.route("/staff/<int:user_id>")
@login_required
@role_required("SYSTEMMANAGER")
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
        "systemmanager/staffprofile.html",
        user=user,
        staff=staff,
        assignments=assignments
    )


# =====================================================
# VIEW STORE PROFILE
# =====================================================
@systemmanager_bp.route("/stores/<int:store_id>")
@login_required
@role_required("SYSTEMMANAGER")
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
            joinedload(StoreBranch.branch_products),
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
    total_products = len(storebranch.branch_products) if storebranch.branch_products else 0
    # revenue placeholder (replace with real aggregation later)
    total_revenue = 0
    # -----------------------------
    # RETURN
    # -----------------------------
    return render_template(
        "systemmanager/storeprofile.html",
        store=storebranch,
        manager=manager,
        total_orders=total_orders,
        total_products=total_products,
        total_revenue=total_revenue
    )


# =====================================================
# CREATE USER 
# =====================================================
@systemmanager_bp.route("/users/createuser", methods=["GET", "POST"])
@login_required
@role_required("SYSTEMMANAGER")
def create_user():

    branches = StoreBranch.query.filter_by(
        is_deleted=False
    ).all()

    if request.method == "POST":

        first_name = request.form.get(
            "firstName", ""
        ).strip()

        last_name = request.form.get(
            "lastName", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        country_code = request.form.get(
            "countryCode", ""
        ).strip()

        phone = request.form.get(
            "phone", ""
        ).strip()

        role_name = request.form.get("role")

        branch_id = request.form.get("branch_id")

        full_phone = (
            f"{country_code}{phone}"
            if phone else None
        )

        meta = get_request_meta()

        # =====================================================
        # VALIDATION
        # =====================================================

        if not all([
            first_name,
            last_name,
            email,
            role_name
        ]):
            flash("Missing required fields", "warning")
            return redirect(
                url_for("systemmanager.create_user")
            )

        if User.query.filter_by(email=email).first():
            flash("Email already exists", "warning")
            return redirect(
                url_for("systemmanager.create_user")
            )

        if (
            full_phone and
            User.query.filter_by(
                phone_number=full_phone
            ).first()
        ):
            flash("Phone already exists", "warning")
            return redirect(
                url_for("systemmanager.create_user")
            )

        role = Role.query.filter_by(
            name=role_name
        ).first()

        if not role:
            flash("Invalid role selected", "danger")
            return redirect(
                url_for("systemmanager.create_user")
            )

        if role_name not in ALLOWED_ASSIGNABLE_ROLES:
            flash("Role not assignable", "danger")
            return redirect(
                url_for("systemmanager.create_user")
            )

        requires_branch = (
            role_name in BRANCH_REQUIRED_ROLES
        )

        if requires_branch and not branch_id:
            flash(
                "Branch is required for this role",
                "warning"
            )
            return redirect(
                url_for("systemmanager.create_user")
            )

        try:

            # =====================================================
            # CREATE USER
            # =====================================================

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

            # =====================================================
            # PROFILE
            # =====================================================

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

            # =====================================================
            # BRANCH ASSIGNMENT
            # =====================================================

            if requires_branch:

                branch = StoreBranch.query.get(branch_id)

                if not branch or branch.is_deleted:
                    flash("Branch not found", "danger")
                    return redirect(
                        url_for("systemmanager.create_user")
                    )

                branch_staff = BranchStaff(
                    user_id=user.id,
                    branch_id=branch.id,
                    role=role_name
                )

                db.session.add(branch_staff)

            # =====================================================
            # COMMIT USER FIRST
            # =====================================================

            db.session.commit()

            # =====================================================
            # AUDIT LOG (SEPARATE SAFE BLOCK)
            # =====================================================

            try:

                log_action(
                    user_id=current_user.id,
                    email=current_user.email,
                    action="Created user",
                    entity_type="User",
                    entity_id=user.id,
                    ip_address=meta["ip"],
                    user_agent=meta["user_agent"],
                    meta_data={
                        "created_user_email": email,
                        "role": role_name,
                        "branch_id": int(branch_id)
                        if branch_id else None
                    }
                )

                db.session.commit()

            except Exception as audit_error:

                db.session.rollback()

                print(
                    "AUDIT LOG FAILED:",
                    audit_error
                )

            flash(
                "User created successfully",
                "success"
            )

            return redirect(
                url_for("systemmanager.users")
            )

        except Exception as e:

            db.session.rollback()

            import traceback
            traceback.print_exc()

            flash(
                "Failed to create user",
                "danger"
            )

            return redirect(
                url_for("systemmanager.create_user")
            )

    return render_template(
        "systemmanager/createuser.html",
        branches=branches
    )




# =====================================================
# EDIT USER
# =====================================================
@systemmanager_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("SYSTEMMANAGER")
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
            return redirect(url_for("systemmanager.users"))

        except Exception as e:
            db.session.rollback()
            print(e)
            abort(500)
    return render_template("systemmanager/edituser.html", user=user, branches=branches)


# =====================================================
# USER STATUS MANAGEMENT
# freeze | unfreeze | delete | restore
# =====================================================
@systemmanager_bp.route("/users/<int:user_id>/status", methods=["POST"])
@login_required
@role_required("SYSTEMMANAGER")
def update_user_status(user_id):
    user = User.query.get_or_404(user_id)
    action = request.form.get("action")
    ALLOWED_ACTIONS = {"freeze", "unfreeze", "delete", "restore"}
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
        return redirect(url_for("systemmanager.users"))

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
                return redirect(url_for("systemmanager.users"))
            user.is_frozen = True
            user.is_active = False
        # =====================================================
        # UNFREEZE
        # =====================================================
        elif action == "unfreeze":
            if user.is_deleted:
                flash("Deleted users cannot be unfrozen.", "warning")
                return redirect(url_for("systemmanager.users"))
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
                return redirect(url_for("systemmanager.users"))
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
                return redirect(url_for("systemmanager.users"))
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
        return redirect(url_for("systemmanager.users"))

    except Exception as e:
        db.session.rollback()
        print(e)
        flash(
            "Failed to update user status.",
            "danger"
        )
        return redirect(url_for("systemmanager.users"))

# =====================================================
# ACTIVATE / DEACTIVATE USER
# =====================================================
@systemmanager_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@role_required("SYSTEMMANAGER")
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
        return redirect(url_for("systemmanager.users"))
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
        return redirect(url_for("systemmanager.users"))
    except Exception as e:
        db.session.rollback()
        print(e)
        flash("Failed to update user status.", "danger")
        return redirect(url_for("systemmanager.users"))


# =====================================================
# LIST STORES (TAB STYLE)
# =====================================================
@systemmanager_bp.route("/stores")
@login_required
@role_required("SYSTEMMANAGER")
def stores():
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
        "systemmanager/stores.html",
        stores=stores,
        current_tab=tab
    )

# =====================================================
# CREATE STORE
# =====================================================
@systemmanager_bp.route("/stores/createstore", methods=["GET", "POST"])
@login_required
@role_required("SYSTEMMANAGER")
def create_store():
    if request.method == "POST":
        try:

            # =====================================================
            # FORM DATA (UPDATED TO MATCH NEW FORM)
            # =====================================================
            name = request.form.get("name", "").strip()

            phone_number = request.form.get("phone", "").strip()
            country_code = request.form.get("countryCode", "").strip()

            email = request.form.get("email", "").strip()

            plot_number = request.form.get("plot_number", "").strip()
            area = request.form.get("area", "").strip()
            town = request.form.get("town", "").strip()
            city = request.form.get("city", "").strip()
            country = request.form.get("country", "").strip()

            latitude = request.form.get("latitude")
            longitude = request.form.get("longitude")

            opening_time = request.form.get("opening_time")
            closing_time = request.form.get("closing_time")

            allows_delivery = request.form.get("allows_delivery") == "true"
            allows_pickup = request.form.get("allows_pickup") == "true"

            meta = get_request_meta()

            # =====================================================
            # VALIDATION
            # =====================================================
            if not all([name, area, town, city]):
                flash("Missing required fields", "warning")
                return redirect(url_for("systemmanager.create_store"))

            # =====================================================
            # SAFE FLOAT PARSER
            # =====================================================
            def safe_float(value):
                try:
                    return float(value) if value not in (None, "") else None
                except (ValueError, TypeError):
                    return None

            # =====================================================
            # BUILD FULL PHONE NUMBER
            # =====================================================
            full_phone = None
            if country_code and phone_number:
                full_phone = f"{country_code}{phone_number}"

            # =====================================================
            # OPERATING HOURS JSON
            # =====================================================
            operating_hours = None
            if opening_time and closing_time:
                operating_hours = {
                    "monday": {
                        "open": opening_time,
                        "close": closing_time
                    }
                }

            # =====================================================
            # CREATE STORE
            # =====================================================
            store = StoreBranch(
                name=name,

                phone_number=full_phone,
                email=email or None,

                plot_number=plot_number or None,
                area=area,
                town=town,
                city=city,
                country=country or "Botswana",

                latitude=safe_float(latitude),
                longitude=safe_float(longitude),

                allows_delivery=allows_delivery,
                allows_pickup=allows_pickup,

                operating_hours=operating_hours,

                is_active=True,
                is_deleted=False
            )

            db.session.add(store)
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
                    "phone_number": store.phone_number,
                    "area": store.area,
                    "town": store.town,
                    "city": store.city,
                    "plot_number": store.plot_number,
                    "latitude": store.latitude,
                    "longitude": store.longitude,
                    "allows_delivery": store.allows_delivery,
                    "allows_pickup": store.allows_pickup
                }
            )

            db.session.commit()

            flash("Store created successfully", "success")
            return redirect(url_for("systemmanager.stores"))

        except Exception as e:
            db.session.rollback()
            import traceback
            traceback.print_exc()

            flash("Failed to create store", "danger")
            return redirect(url_for("systemmanager.create_store"))

    return render_template("systemmanager/createstore.html")



# =====================================================
# EDIT STORE
# =====================================================
@systemmanager_bp.route("/stores/<int:store_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("SYSTEMMANAGER")
def update_store(store_id):

    store = StoreBranch.query.get_or_404(store_id)

    if request.method == "POST":

        try:
            # =====================================================
            # FORM DATA
            # =====================================================
            name = request.form.get("name", "").strip()

            country_code = request.form.get("countryCode", "").strip()
            phone = request.form.get("phone", "").strip()
            full_phone = f"{country_code}{phone}" if phone else None

            email = request.form.get("email", "").strip()

            plot_number = request.form.get("plot_number", "").strip()
            area = request.form.get("area", "").strip()
            town = request.form.get("town", "").strip()
            city = request.form.get("city", "").strip()
            country = request.form.get("country", "").strip()

            latitude = request.form.get("latitude", "").strip()
            longitude = request.form.get("longitude", "").strip()

            opening_time = request.form.get("opening_time")
            closing_time = request.form.get("closing_time")

            allows_delivery = request.form.get("allows_delivery") == "true"
            allows_pickup = request.form.get("allows_pickup") == "true"

            meta = get_request_meta()

            # =====================================================
            # VALIDATION
            # =====================================================
            if not all([name, area, town, city]):
                flash("Missing required fields", "warning")
                return redirect(request.url)

            # =====================================================
            # SAFE FLOAT
            # =====================================================
            def safe_float(value):
                try:
                    return float(value) if value else None
                except (TypeError, ValueError):
                    return None

            # =====================================================
            # BEFORE STATE
            # =====================================================
            before = {
                "name": store.name,
                "phone_number": store.phone_number,
                "email": store.email,
                "plot_number": store.plot_number,
                "area": store.area,
                "town": store.town,
                "city": store.city,
                "country": store.country,
                "latitude": store.latitude,
                "longitude": store.longitude,
                "allows_delivery": store.allows_delivery,
                "allows_pickup": store.allows_pickup,
                "operating_hours": store.operating_hours,
            }

            # =====================================================
            # OPERATING HOURS
            # =====================================================
            operating_hours = store.operating_hours or {}

            if opening_time and closing_time:
                operating_hours["monday"] = {
                    "open": opening_time,
                    "close": closing_time
                }

            # =====================================================
            # UPDATE STORE
            # =====================================================
            store.name = name
            store.phone_number = full_phone
            store.email = email or None

            store.plot_number = plot_number or None
            store.area = area
            store.town = town
            store.city = city
            store.country = country or "Botswana"

            store.latitude = safe_float(latitude)
            store.longitude = safe_float(longitude)

            store.allows_delivery = allows_delivery
            store.allows_pickup = allows_pickup

            store.operating_hours = operating_hours

            # =====================================================
            # AFTER STATE
            # =====================================================
            after = {
                "name": store.name,
                "phone_number": store.phone_number,
                "email": store.email,
                "plot_number": store.plot_number,
                "area": store.area,
                "town": store.town,
                "city": store.city,
                "country": store.country,
                "latitude": store.latitude,
                "longitude": store.longitude,
                "allows_delivery": store.allows_delivery,
                "allows_pickup": store.allows_pickup,
                "operating_hours": store.operating_hours,
            }

            # =====================================================
            # DIFF
            # =====================================================
            diff = {
                key: {
                    "old": before[key],
                    "new": after[key]
                }
                for key in before
                if before[key] != after[key]
            }

            # =====================================================
            # AUDIT LOG
            # =====================================================
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

            # =====================================================
            # SINGLE COMMIT
            # =====================================================
            db.session.commit()

            flash("Store updated successfully", "success")

            return redirect(url_for("systemmanager.stores"))

        except Exception as e:
            db.session.rollback()

            import traceback
            traceback.print_exc()

            print(f"UPDATE STORE ERROR: {e}")

            flash("Failed to update store", "danger")

            return redirect(request.url)

    return render_template(
        "systemmanager/editstore.html",
        store=store
    )


# =====================================================
# STORE STATUS MANAGEMENT
# activate | deactivate | delete | restore
# =====================================================
@systemmanager_bp.route("/stores/<int:store_id>/toggle", methods=["POST"])
@login_required
@role_required("SYSTEMMANAGER")
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
                return redirect(url_for("systemmanager.stores"))
            store.is_active = True
        # -----------------------------
        # DEACTIVATE
        # -----------------------------
        elif action == "deactivate":
            if store.is_deleted:
                flash("Cannot deactivate a deleted store", "warning")
                return redirect(url_for("systemmanager.stores"))
            store.is_active = False
        # -----------------------------
        # SOFT DELETE
        # -----------------------------
        elif action == "delete":
            if store.is_deleted:
                flash("Store already deleted", "warning")
                return redirect(url_for("systemmanager.stores"))
            store.is_deleted = True
            store.is_active = False
        # -----------------------------
        # RESTORE
        # -----------------------------
        elif action == "restore":
            if not store.is_deleted:
                flash("Store is not deleted", "warning")
                return redirect(url_for("systemmanager.stores"))
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
        return redirect(url_for("systemmanager.stores"))
    except Exception as e:
        db.session.rollback()
        print(e)
        abort(500)
        

# =====================================================
# ACTIVITY
# =====================================================
@systemmanager_bp.route("/activity")
@login_required
@role_required("SYSTEMMANAGER")
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
        .join(User, AuditLog.user_id == User.id)
        .filter(
            ~User.roles.any(Role.name == "ADMIN")
        )
        .order_by(desc(AuditLog.timestamp))
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return render_template(
        "systemmanager/systemlogs.html",
        activity_logs=activity_logs
    )        