# app/routes/store_manager.py

from flask import Blueprint, render_template, redirect, url_for, request, abort, flash, current_app
from flask_login import login_required, current_user

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.security.decorators import role_required
from app.util.audit_helper import log_action, get_request_meta

from app.models.branchstaff import BranchStaff
from app.models.storebranch import StoreBranch
from app.models.branchproduct import BranchProduct
from app.models.product import Product

from app.models.audit import AuditLog
from app.models.order import Order, OrderStatus
from app.models.productvariant import ProductVariant
from app.models.delivery import Delivery, DeliveryStatus

from app.models.user import User
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone, timedelta
from app.models.orderitem import OrderItem
from app.util.storemanager_helper import get_manager_branch
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
from app.models.branchproductvariant import BranchProductVariant
from app.services.product_filters import apply_product_tab_filter
from app.services.storemanagerservice import StoreManagerService


storemanager_bp = Blueprint("storemanager", __name__, url_prefix="/storemanager")

# =====================================================
# STORE MANAGER DASHBOARD
# =====================================================
@storemanager_bp.route("/dashboard")
@login_required
@role_required("STOREMANAGER")
def dashboard():

    user = current_user
    staff = user.staff_profile

    branch_staff = BranchStaff.query.filter_by(
        user_id=user.id,
        role="STOREMANAGER"
    ).first()

    if not branch_staff:
        abort(403, "Store assignment missing")

    branch = branch_staff.branch

    if not branch:
        abort(404, "Store not found")

    # =====================================================
    # BASE FILTER (reuse for all queries)
    # =====================================================
    branch_id = branch.id

    # =====================================================
    # KPI METRICS
    # =====================================================

    products_count = (
        BranchProduct.query
        .filter_by(branch_id=branch_id)
        .count()
    )

    staff_count = (
        BranchStaff.query
        .filter(
            BranchStaff.branch_id == branch_id,
            BranchStaff.role != "COURIER"
        )
        .count()
    )

    orders_count = (
        Order.query
        .filter_by(branch_id=branch_id)
        .count()
    )

    pending_orders_count = (
        Order.query
        .filter_by(
            branch_id=branch_id,
            status="PENDING"
        )
        .count()
    )

    unassigneddeliveries_count = (
        Delivery.query
        .filter_by(
            branch_id=branch_id,
            courier_id=None
        )
        .count()
    )

    # =====================================================
    # LOW STOCK (FIXED INVENTORY PATH)
    # =====================================================

    low_stock_count = (
        db.session.query(Product.id)
        .join(Product.variants)
        .join(ProductVariant.branch_variants)
        .join(BranchProductVariant.inventory)
        .filter(
            BranchProductVariant.branch_product.has(
                branch_id=branch_id
            )
        )
        .group_by(Product.id)
        .having(db.func.sum(Inventory.quantity) <= 5)
        .count()
    )

    # =====================================================
    # FILTERED ACTIVITY LOGS (ONLY RELEVANT BUSINESS EVENTS)
    # =====================================================

    activity_logs = (
        AuditLog.query
        .filter(
            AuditLog.branch_id == branch_id,
            db.or_(
                AuditLog.action.ilike("%PRODUCT%"),
                AuditLog.action.ilike("%ORDER%"),
                AuditLog.action.ilike("%STAFF%"),
            )
        )
        .order_by(AuditLog.timestamp.desc())
        .limit(20)
        .all()
    )

    # =====================================================
    # RENDER
    # =====================================================

    return render_template(
        "storemanager/dashboard.html",
        branch=branch,
        staff=staff,
        products_count=products_count,
        staff_count=staff_count,
        orders_count=orders_count,
        pending_orders_count=pending_orders_count,
        unassigneddeliveries_count=unassigneddeliveries_count,
        low_stock_count=low_stock_count,
        activity_logs=activity_logs
    )





# =====================================================
# STORE MANAGER LIST USERS
# =====================================================
@storemanager_bp.route("/users")
@login_required
@role_required("STOREMANAGER")
def list_users():

    branch = get_manager_branch()

    page = request.args.get("page", 1, type=int)
    tab = request.args.get("tab", "all")

    # =================================================
    # BASE QUERY
    # =================================================
    query = (
        User.query
        .options(
            joinedload(User.customer_profile),
            joinedload(User.staff_profile),
            joinedload(User.courier_profile),
            joinedload(User.branch_staff)
            .joinedload(BranchStaff.branch)
        )
        .filter(User.is_deleted == False)
    )

    # =================================================
    # FILTERS
    # =================================================

    # -----------------------------
    # CUSTOMERS
    # -----------------------------
    if tab == "customers":

        query = query.filter(
            User.customer_profile.has()
        )

    # -----------------------------
    # STAFF (ONLY CURRENT BRANCH)
    # -----------------------------
    elif tab == "staff":

        query = (
            query
            .join(BranchStaff)
            .filter(
                BranchStaff.branch_id == branch.id
            )
        )

    # -----------------------------
    # COURIERS
    # -----------------------------
    elif tab == "couriers":

        query = query.filter(
            User.courier_profile.has()
        )

    # -----------------------------
    # ALL
    # (Customers + Branch Staff + Couriers)
    # -----------------------------
    else:

        query = query.filter(
            or_(
                User.customer_profile.has(),

                User.courier_profile.has(),

                User.branch_staff.any(
                    BranchStaff.branch_id == branch.id
                )
            )
        )

    # =================================================
    # PAGINATION
    # =================================================
    users = (
        query
        .order_by(User.created_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )

    return render_template(
        "storemanager/list_users.html",
        branch=branch,
        users=users,
        current_tab=tab
    )

# =====================================================
# STORE MANAGER VIEW CUSTOMER
# =====================================================
@storemanager_bp.route("/customers/<int:user_id>")
@login_required
@role_required("STOREMANAGER")
def view_customer(user_id):

    branch = get_manager_branch()

    user = (
        User.query
        .options(
            joinedload(User.customer_profile),
            joinedload(User.orders)
        )
        .filter_by(id=user_id)
        .first_or_404()
    )

    if not user.customer_profile:
        abort(404)

    profile = user.customer_profile

    # =================================================
    # CUSTOMER ORDERS
    # =================================================
    orders = (
        Order.query
        .filter_by(
            user_id=user.id,
            branch_id=branch.id
        )
        .order_by(Order.created_at.desc())
        .limit(10)
        .all()
    )

    total_orders = len(orders)

    total_spent = sum(
        float(order.subtotal_amount or 0)
        for order in orders
    )

    last_order_date = (
        orders[0].created_at
        if orders else None
    )

    return render_template(
        "storemanager/customer_details.html",
        user=user,
        profile=profile,
        orders=orders,
        total_orders=total_orders,
        total_spent=round(total_spent, 2),
        last_order_date=last_order_date
    )

# =====================================================
# STORE MANAGER VIEW STAFF
# =====================================================
@storemanager_bp.route("/staff/<int:user_id>")
@login_required
@role_required("STOREMANAGER")
def view_staff(user_id):

    branch = get_manager_branch()

    user = (
        User.query
        .options(
            joinedload(User.staff_profile),
            joinedload(User.branch_staff)
            .joinedload(BranchStaff.branch)
        )
        .filter_by(id=user_id)
        .first_or_404()
    )

    if not user.staff_profile:
        abort(404)

    # =================================================
    # SECURITY:
    # STAFF MUST BELONG TO THIS BRANCH
    # =================================================
    assignment = (
        BranchStaff.query
        .filter_by(
            user_id=user.id,
            branch_id=branch.id
        )
        .first()
    )

    if not assignment:
        abort(403)

    assignments = (
        BranchStaff.query
        .options(
            joinedload(BranchStaff.branch)
        )
        .filter_by(user_id=user.id)
        .all()
    )

    return render_template(
        "storemanager/user_details.html",
        user=user,
        staff=user.staff_profile,
        assignments=assignments
    )

# =====================================================
# VIEW COURIER PROFILE
# =====================================================
@storemanager_bp.route("/couriers/<int:user_id>")
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
# STORE MANAGER LIST ORDERS (REFINED)
# =====================================================
@storemanager_bp.route("/orders")
@login_required
@role_required("STOREMANAGER")
def list_orders():

    branch = get_manager_branch()

    page = request.args.get("page", 1, type=int)
    tab = request.args.get("tab", "all")

    query = (
        Order.query
        .options(
            joinedload(Order.user),
            joinedload(Order.items),
            joinedload(Order.delivery)
        )
        .filter(Order.branch_id == branch.id)
    )

    # =====================================================
    # TAB FILTERING (CORE LOGIC)
    # =====================================================
    if tab == "pickup":
        query = query.filter(Order.is_delivery.is_(False))

    elif tab == "delivery":
        query = query.filter(Order.is_delivery.is_(True))

    elif tab == "pending":
        query = query.filter(Order.status.in_([
            OrderStatus.PENDING_PAYMENT,
            OrderStatus.PROCESSING
        ]))

    # "all" = no extra filter

    # =====================================================
    # PAGINATION
    # =====================================================
    orders = (
        query
        .order_by(Order.created_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )

    return render_template(
        "storemanager/list_orders.html",
        branch=branch,
        orders=orders,
        current_tab=tab
    )

# =====================================================
# STORE MANAGER ORDER DETAIL
# =====================================================
@storemanager_bp.route("/orders/<int:order_id>")
@login_required
@role_required("STOREMANAGER")
def order_detail(order_id):

    branch = get_manager_branch()

    order = (
        Order.query
        .options(
            joinedload(Order.user),
            joinedload(Order.items).joinedload(OrderItem.product),
            joinedload(Order.items).joinedload(OrderItem.variant),
            joinedload(Order.delivery).joinedload(Delivery.courier),
            joinedload(Order.branch)
        )
        .filter(
            Order.id == order_id,
            Order.branch_id == branch.id   # 🔒 CRITICAL SECURITY CHECK
        )
        .first_or_404()
    )

    return render_template(
        "storemanager/order_details.html",
        order=order,
        branch=branch
    )


# =====================================================
# STORE MANAGER LIST DELIVERIES
# =====================================================
@storemanager_bp.route("/deliveries")
@login_required
@role_required("STOREMANAGER")
def list_deliveries():

    branch = get_manager_branch()

    status = request.args.get("status")  # optional filter

    # -----------------------------
    # BASE QUERY (SCOPED TO BRANCH)
    # -----------------------------
    query = Delivery.query.filter_by(branch_id=branch.id)

    # -----------------------------
    # OPTIONAL FILTERS
    # -----------------------------
    if status:
        query = query.filter(Delivery.status == status)

    deliveries = (
        query
        .order_by(Delivery.created_at.desc())
        .all()
    )

    # -----------------------------
    # KPIS (BRANCH ONLY)
    # -----------------------------
    total_deliveries = len(deliveries)
    pending_deliveries = sum(1 for d in deliveries if d.status == "PENDING")
    assigned_deliveries = sum(1 for d in deliveries if d.status == "ASSIGNED")
    completed_deliveries = sum(1 for d in deliveries if d.status == "DELIVERED")

    return render_template(
        "storemanager/deliveries.html",
        branch=branch,
        deliveries=deliveries,
        total_deliveries=total_deliveries,
        pending_deliveries=pending_deliveries,
        assigned_deliveries=assigned_deliveries,
        completed_deliveries=completed_deliveries,
        selected_status=status
    )

# =====================================================
# STORE MANAGER DELIVERY DETAIL
# =====================================================
@storemanager_bp.route("/deliveries/<int:delivery_id>")
@login_required
@role_required("STOREMANAGER")
def delivery_detail(delivery_id):

    branch = get_manager_branch()

    delivery = (
        Delivery.query
        .options(
            joinedload(Delivery.order)
                .joinedload(Order.user)
                .joinedload(User.customer_profile),

            joinedload(Delivery.order)
                .joinedload(Order.items),

            joinedload(Delivery.courier)
                .joinedload(User.courier_profile),

            joinedload(Delivery.branch)
        )
        .filter(
            Delivery.id == delivery_id,
            Delivery.branch_id == branch.id   # 🔒 CRITICAL: prevents cross-store access
        )
        .first_or_404()
    )

    return render_template(
        "storemanager/delivery_detail.html",
        delivery=delivery,
        branch=branch
    )


# =====================================================
# STORE MANAGER ANALYTICS
# =====================================================
@storemanager_bp.route("/analytics")
@login_required
@role_required("STOREMANAGER")
def analytics():

    from sqlalchemy import func
    from sqlalchemy.orm import joinedload

    # =================================================
    # CURRENT BRANCH
    # =================================================
    branch = get_manager_branch()

    # =================================================
    # DATE RANGE
    # =================================================
    days = request.args.get("range", 30, type=int)

    if days not in [7, 30, 90]:
        days = 30

    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # =================================================
    # BASE ORDERS QUERY
    # =================================================
    orders_query = (
        Order.query
        .options(
            joinedload(Order.user)
            .joinedload(User.customer_profile)
        )
        .filter(
            Order.branch_id == branch.id,
            Order.created_at >= start_date
        )
    )

    all_orders = orders_query.all()

    # =================================================
    # KPI DATA
    # =================================================
    total_orders = len(all_orders)

    total_revenue = sum(
        float(order.subtotal_amount or 0)
        for order in all_orders
        if order.status != OrderStatus.CANCELLED
    )

    completed_orders = sum(
        1 for order in all_orders
        if order.status == OrderStatus.DELIVERED
    )

    pending_orders = sum(
        1 for order in all_orders
        if order.status == OrderStatus.PENDING_PAYMENT
    )

    cancelled_orders = sum(
        1 for order in all_orders
        if order.status == OrderStatus.CANCELLED
    )

    avg_order_value = (
        total_revenue / total_orders
        if total_orders else 0
    )

    # =================================================
    # CUSTOMER COUNT
    # =================================================
    customer_count = (
        db.session.query(Order.user_id)
        .filter(
            Order.branch_id == branch.id,
            Order.created_at >= start_date
        )
        .distinct()
        .count()
    )

    # =================================================
    # DELIVERY SUCCESS
    # =================================================
    deliveries_query = (
        Delivery.query
        .filter(
            Delivery.branch_id == branch.id,
            Delivery.created_at >= start_date
        )
    )

    total_deliveries = deliveries_query.count()

    successful_deliveries = (
        deliveries_query
        .filter(Delivery.status == DeliveryStatus.DELIVERED)
        .count()
    )

    delivery_success = (
        (successful_deliveries / total_deliveries) * 100
        if total_deliveries else 0
    )

    # =================================================
    # TOP PRODUCTS
    # =================================================
    top_products_query = (
        db.session.query(
            Product.name.label("name"),

            func.count(OrderItem.id).label("orders"),

            func.coalesce(
                func.sum(OrderItem.total_price),
                0
            ).label("revenue")
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.branch_id == branch.id,
            Order.created_at >= start_date
        )
        .group_by(Product.id, Product.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(10)
        .all()
    )

    top_products = [
        {
            "name": p.name,
            "orders": p.orders,
            "revenue": round(float(p.revenue or 0), 2)
        }
        for p in top_products_query
    ]

    # =================================================
    # MOST SEARCHED PRODUCTS
    # PLACEHOLDER
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
    # ORDER PERFORMANCE
    # =================================================
    top_stores = [
        {
            "name": branch.name,
            "revenue": round(total_revenue, 2),
            "orders": total_orders,
            "refund_rate": 0
        }
    ]

    # =================================================
    # COURIER PERFORMANCE
    # =================================================
    courier_query = (
        db.session.query(
            User,
            func.count(Delivery.id).label("deliveries")
        )
        .join(Delivery, Delivery.courier_id == User.id)
        .options(joinedload(User.courier_profile))
        .filter(
            Delivery.branch_id == branch.id,
            Delivery.created_at >= start_date
        )
        .group_by(User.id)
        .all()
    )

    courier_stats = []

    for user, deliveries in courier_query:

        if user.courier_profile:

            courier_stats.append({
                "name": (
                    f"{user.courier_profile.first_name} "
                    f"{user.courier_profile.last_name}"
                ),
                "deliveries": deliveries,
                "on_time": 100,   # placeholder
                "avg_time": 25    # placeholder
            })

    # =================================================
    # TOP CUSTOMERS
    # =================================================
    customer_query = (
        db.session.query(
            User,
            func.count(Order.id).label("orders"),

            func.coalesce(
                func.sum(Order.subtotal_amount),
                0
            ).label("spend")
        )
        .join(Order, Order.user_id == User.id)
        .options(joinedload(User.customer_profile))
        .filter(
            Order.branch_id == branch.id,
            Order.created_at >= start_date
        )
        .group_by(User.id)
        .order_by(func.sum(Order.subtotal_amount).desc())
        .limit(10)
        .all()
    )

    top_customers = []

    for user, orders_count, spend in customer_query:

        if user.customer_profile:

            top_customers.append({
                "name": (
                    f"{user.customer_profile.first_name} "
                    f"{user.customer_profile.last_name}"
                ),
                "orders": orders_count,
                "spend": round(float(spend or 0), 2)
            })

    # =================================================
    # SALES SUMMARY
    # =================================================
    sales = {
        "avg_order_value": round(avg_order_value, 2),
        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "cancelled_orders": cancelled_orders
    }

    # =================================================
    # KPI BLOCK
    # =================================================
    kpis = {
        "revenue": round(total_revenue, 2),
        "orders": total_orders,
        "customers": customer_count,
        "delivery_success": round(delivery_success, 2)
    }

    # =================================================
    # RENDER
    # =================================================
    return render_template(
        "storemanager/store_analytics.html",

        branch=branch,
        selected_range=days,

        kpis=kpis,
        sales=sales,

        top_products=top_products,
        searched_products=searched_products,

        top_stores=top_stores,
        courier_stats=courier_stats,
        top_customers=top_customers
    )



# =====================================================
# STORE MANAGER LIST PRODUCTS
# =====================================================
@storemanager_bp.route("/products")
@login_required
@role_required("STOREMANAGER")
def list_products():

    branch = get_manager_branch()

    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    tab = request.args.get("tab", "all")

    branch_id = branch.id

    # =========================================
    # BASE QUERY
    # =========================================
    query = (
        Product.query
        .options(
            joinedload(Product.images),
            joinedload(Product.variants)
            .joinedload(ProductVariant.branch_variants)
            .joinedload(BranchProductVariant.branch_product),
            joinedload(Product.variants)
            .joinedload(ProductVariant.branch_variants)
            .joinedload(BranchProductVariant.inventory)
        )
        .filter(
            Product.is_active.is_(True),
            Product.is_deleted.is_(False)
        )
    )

    # =========================================
    # SEARCH
    # =========================================
    if search:
        query = query.filter(
            db.or_(
                Product.name.ilike(f"%{search}%"),
                Product.category.ilike(f"%{search}%"),
                Product.brand.ilike(f"%{search}%")
            )
        )

    # =========================================
    # TAB FILTERS (IMPORTANT FIX)
    # =========================================
    query = apply_product_tab_filter(query, tab, branch_id)

    # =========================================
    # PAGINATION
    # =========================================
    products = query.order_by(
        Product.created_at.desc()
    ).paginate(
        page=page,
        per_page=20,
        error_out=False
    )

    # =========================================
    # UI SNAPSHOTS ONLY (NO LOGIC FILTERING)
    # =========================================
 
    branch_variant_map = {}


    for product in products.items:

        product.primary_image = next(
            (img for img in product.images if img.is_primary),
            None
        )

        for variant in product.variants:

            branch_variant = next(
                (
                    bv for bv in variant.branch_variants
                    if bv.branch_product
                    and bv.branch_product.branch_id == branch.id
                ),
                None
            )

            branch_variant_map[variant.id] = branch_variant


    return render_template(
        "storemanager/list_products.html",
        branch=branch,
        products=products,
        search=search,
        current_tab=tab,
        branch_variant_map=branch_variant_map
    )


# =====================================================
# STORE MANAGER VIEW PRODUCT
# =====================================================
@storemanager_bp.route("/products/<int:product_id>")
@login_required
@role_required("STOREMANAGER")
def view_product(product_id):

    branch = get_manager_branch()

    product = (
        Product.query
        .options(
            joinedload(Product.images),
            joinedload(Product.variants)
            .joinedload(ProductVariant.branch_variants)
            .joinedload(BranchProductVariant.inventory)
        )
        .filter(
            Product.id == product_id,
            Product.is_deleted.is_(False)
        )
        .first_or_404()
    )

    branch_product = BranchProduct.query.filter_by(
        branch_id=branch.id,
        product_id=product.id
    ).first()

    variant_data = []

    for variant in product.variants:

        branch_variant = next(
            (
                bv for bv in variant.branch_variants
                if bv.branch_product and bv.branch_product.branch_id == branch.id
            ),
            None
        )

        inventory = branch_variant.inventory if branch_variant else None

        variant_data.append({
            "variant": variant,
            "inventory": inventory,
            "stock": inventory.quantity if inventory else 0
        })

    total_stock = sum(v["stock"] for v in variant_data)

    primary_image = next(
        (img for img in product.images if img.is_primary),
        None
    )

    is_available = any(
        bv.is_available and bv.branch_product.branch_id == branch.id
        for v in product.variants
        for bv in v.branch_variants
    )

    return render_template(
        "storemanager/view_product.html",
        product=product,
        branch_product=branch_product,
        variant_data=variant_data,
        total_stock=total_stock,
        primary_image=primary_image,
        is_available=is_available,
        branch=branch
    )



# =====================================================
# STORE MANAGER UPDATE VARIANT STATUS
# =====================================================
@storemanager_bp.route("/variant/status", methods=["POST"])
@login_required
@role_required("STOREMANAGER")
def update_variant_status():
    branch = get_manager_branch()
    variant_id = request.form.get("variant_id", type=int)
    branch_id = request.form.get("branch_id", type=int)

    if not variant_id or not branch_id:
        flash("Missing data", "danger")
        return redirect(request.referrer)

    variant = ProductVariant.query.get_or_404(variant_id)

    branch_variant = (
        BranchProductVariant.query
        .join(BranchProduct)
        .filter(
            BranchProduct.branch_id == branch.id,
            BranchProduct.product_id == variant.product_id,
            BranchProductVariant.variant_id == variant.id
        )
        .first()
    )

    # Auto-create if missing
    if not branch_variant:
        branch_product = BranchProduct.query.filter_by(
            branch_id=branch.id,
            product_id=variant.product_id
        ).first()
        if not branch_product:
            flash("Attach product first", "warning")
            return redirect(request.referrer)
        branch_variant = BranchProductVariant(
            branch_product_id=branch_product.id,
            variant_id=variant.id,
            is_available=True
        )
        db.session.add(branch_variant)

    # Update status
    is_available = "is_available" in request.form

    branch_variant.is_available = is_available

    inventory = Inventory.query.filter_by(branch_variant_id=branch_variant.id).first()

    if not inventory:
        inventory = Inventory(
            branch_variant_id=branch_variant.id,
            quantity=0,
            reserved_quantity=0
        )
        db.session.add(inventory)
    else:
        inventory.reserved_quantity = inventory.reserved_quantity or 0

    db.session.commit()
    flash("Variant status updated", "success")
    return redirect(request.referrer or url_for("storemanager.list_products"))



# =====================================================
# STORE MANAGER TOGGLE PICKUP
# =====================================================
@storemanager_bp.route(
    "/products/<int:product_id>/toggle-pickup",
    methods=["POST"]
)
@login_required
@role_required("STOREMANAGER")
def toggle_pickup(product_id):

    branch = get_manager_branch()

    variant_id = request.form.get(
        "variant_id",
        type=int
    )

    branch_variant = (
        BranchProductVariant.query
        .join(BranchProduct)
        .filter(
            BranchProduct.branch_id == branch.id,
            BranchProduct.product_id == product_id,
            BranchProductVariant.variant_id == variant_id
        )
        .first()
    )

    if not branch_variant:
        flash("Attach product first", "warning")
        return redirect(request.referrer)

    branch_variant.allows_pickup = (
        "allows_pickup" in request.form
    )

    db.session.commit()

    return redirect(
        request.referrer
        or url_for("storemanager.list_products")
    )

# =====================================================
# STORE MANAGER TOGGLE DELIVERY
# =====================================================
@storemanager_bp.route(
    "/products/<int:product_id>/toggle-delivery",
    methods=["POST"]
)
@login_required
@role_required("STOREMANAGER")
def toggle_delivery(product_id):

    branch = get_manager_branch()

    variant_id = request.form.get(
        "variant_id",
        type=int
    )

    branch_variant = (
        BranchProductVariant.query
        .join(BranchProduct)
        .filter(
            BranchProduct.branch_id == branch.id,
            BranchProduct.product_id == product_id,
            BranchProductVariant.variant_id == variant_id
        )
        .first()
    )

    if not branch_variant:
        flash("Attach product first", "warning")
        return redirect(request.referrer)

    branch_variant.allows_delivery = (
        "allows_delivery" in request.form
    )

    db.session.commit()

    return redirect(
        request.referrer
        or url_for("storemanager.list_products")
    )


# =====================================================
# STORE MANAGER ATTACH PRODUCT
# =====================================================
@storemanager_bp.route("/products/attach", methods=["POST"])
@login_required
@role_required("STOREMANAGER")
def attach_product():
    branch = get_manager_branch()
    try:
        product_id = request.form.get("product_id", type=int)
        variant_id = request.form.get("variant_id", type=int)
        stock = request.form.get("stock", type=int) or 0
        
        product = Product.query.get_or_404(product_id)
        variant = ProductVariant.query.filter_by(id=variant_id, product_id=product.id).first_or_404()

        # Branch product
        branch_product = BranchProduct.query.filter_by(branch_id=branch.id, product_id=product.id).first()
        if not branch_product:
            branch_product = BranchProduct(
                branch_id=branch.id,
                product_id=product.id,
                is_visible=True
            )
            db.session.add(branch_product)
            db.session.flush()
        else:
            branch_product.is_visible = True

        # Branch variant
        branch_variant = BranchProductVariant.query.filter_by(
            branch_product_id=branch_product.id,
            variant_id=variant.id
        ).first()
        if not branch_variant:
            branch_variant = BranchProductVariant(
                branch_product_id=branch_product.id,
                variant_id=variant.id,
                is_available=True,  
                allows_pickup=True,
                allows_delivery=True
            )
            db.session.add(branch_variant)
            db.session.flush()
        else:
            branch_variant.is_available = True
            branch_variant.allows_pickup = True
            branch_variant.allows_delivery = True

        # Inventory
        inventory = Inventory.query.filter_by(branch_variant_id=branch_variant.id).first()

        if not inventory:
            inventory = Inventory(
                branch_variant_id=branch_variant.id,
                quantity=stock or 0,
                reserved_quantity=0
            )
            db.session.add(inventory)
        else:
            inventory.quantity = stock or 0
            inventory.reserved_quantity = inventory.reserved_quantity or 0

        db.session.commit()
        flash("Product attached successfully.", "success")
    except Exception as e:
        db.session.rollback()
        print(str(e))
        flash("Failed to attach product.", "danger")

    return redirect(url_for("storemanager.list_products"))



# =====================================================
# STORE MANAGER BULK CREATE
# =====================================================
@storemanager_bp.route("/products/bulk-create", methods=["GET", "POST"])
@login_required
@role_required("STOREMANAGER")
def bulk_create_products():
    branch = get_manager_branch()

    if request.method == "GET":
        return render_template("storemanager/bulk_create_products.html", branch=branch)

    # Handle Excel upload
    excel_file = request.files.get("excel_file")
    if not excel_file or not excel_file.filename.endswith(".xlsx"):
        flash("Please upload a valid Excel (.xlsx) file.", "danger")
        return redirect(url_for("storemanager.bulk_create_products"))

    try:
        wb = load_workbook(excel_file)
        ws = wb.active

        # Map images by row (0-based)
        images_map = {}
        for img in ws._images:
            try:
                row_position = img.anchor._from.row + 1
                col_position = img.anchor._from.col + 1

                images_map[(row_position, col_position)] = img
            except Exception as e:
                print(f"[IMAGE MAP ERROR]: {str(e)}")    

        created_count = 0
        skipped_rows = []

        for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=False), start=2):
            try:
                name = str(row[0].value or "").strip()
               # COLUMN B
                category = str(row[1].value or "").strip()
                # COLUMN C
                description = str(row[2].value or "").strip()
                # COLUMN F
                sku = str(row[5].value or "").strip()
                # COLUMN H
                status = str(row[7].value or "Yes").strip().lower()

                # Price & stock
                try:
                    raw_price = str(row[3].value or "0").replace(",",".")
                    price = Decimal(raw_price)
                except InvalidOperation:
                    skipped_rows.append(f"Row {idx}: Invalid price")
                    continue

                try:
                    stock = int(row[4].value or 0)
                except ValueError:
                    skipped_rows.append(f"Row {idx}: Invalid stock")
                    continue

                # Validation
                if not all([name, category, sku]) or price <= 0 or stock < 0:
                    skipped_rows.append(f"Row {idx}: Missing/invalid data")
                    continue

                # SKU uniqueness
                if ProductVariant.query.filter_by(sku=sku).first():
                    skipped_rows.append(f"Row {idx}: SKU already exists")
                    continue

                is_available = status == "yes"

                # Handle embedded image
                img = images_map.get((idx, 7)) 
                image_url = None
                if img:
                    try:
                        image_bytes = img._data()
                        img_bytes = BytesIO(image_bytes)
                        img_bytes.seek(0)
                        image_url = save_bulk_image(img_bytes)
                    except Exception as img_error:
                        print(
                            f"[ROW {idx} IMAGE ERROR]: {str(img_error)}"
                        )
                        skipped_rows.append(
                            f"Row {idx}: Failed to process image"
                        )    


                # Create Product
                product = Product(name=name, category=category, description=description)
                db.session.add(product)
                db.session.flush()

                # Variant
                variant = ProductVariant(
                    product_id=product.id,
                    name="Standard",
                    value=name,
                    sku=sku,
                    price=price,
                    is_default=True
                )
                db.session.add(variant)
                db.session.flush()

                # Branch product
                branch_product = BranchProduct(branch_id=branch.id, product_id=product.id, is_available=is_available)
                db.session.add(branch_product)

                # Inventory
                inventory = Inventory(branch_id=branch.id, variant_id=variant.id, quantity=stock)
                db.session.add(inventory)

                # Product image
                if image_url:
                    product_image = ProductImage(product_id=product.id, image_url=image_url, is_primary=True)
                    db.session.add(product_image)

                # Audit log
                meta = get_request_meta()
                log_action(
                    user_id=current_user.id,
                    email=current_user.email,
                    action="BULK_CREATE_PRODUCT",
                    entity_type="PRODUCT",
                    entity_id=product.id,
                    ip_address=meta["ip"],
                    user_agent=meta["user_agent"],
                    meta_data={
                        "product_name": product.name,
                        "category": category,
                        "sku": sku,
                        "price": str(price),
                        "stock": stock,
                        "branch_id": branch.id
                    }
                )

                created_count += 1

            except Exception as row_err:
                skipped_rows.append(f"Row {idx}: {str(row_err)}")

        db.session.commit()

        flash(f"{created_count} products uploaded successfully.", "success")
        if skipped_rows:
            flash("Some rows were skipped.", "warning")
            for err in skipped_rows[:10]:
                flash(err, "danger")

        return redirect(url_for("storemanager.list_products"))

    except Exception as e:
        db.session.rollback()
        print(f"[BULK PRODUCT ERROR]: {str(e)}")
        flash("Failed to upload bulk products.", "danger")
        return redirect(url_for("storemanager.bulk_create_products"))
    
