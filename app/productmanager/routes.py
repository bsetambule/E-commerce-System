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
from app.models.order import Order, OrderStatus
from app.models.delivery import Delivery, DeliveryStatus
from app.models.storebranch import StoreBranch
from app.models.orderitem import OrderItem
from app.models.branchproductvariant import BranchProductVariant
from app.models.productpromotions import ProductPromotion

productmanager_bp = Blueprint("productmanager", __name__, url_prefix="/productmanager")

# =====================================================
# PRODUCT MANAGER DASHBOARD
# =====================================================
@productmanager_bp.route("/dashboard")
@login_required
@role_required("PRODUCTMANAGER")
def dashboard():
    user = current_user
    # =====================================================
    # PROFILE (SAFE)
    # =====================================================
    staff = getattr(user, "staff_profile", None)
    # =====================================================
    # BRANCH (OPTIONAL FOR GLOBAL ROLE)
    # =====================================================
    branch_staff = (
        BranchStaff.query
        .filter_by(user_id=user.id)
        .first()
    )
    branch = branch_staff.branch if branch_staff else None
    # =====================================================
# GLOBAL VIEW MODE
# =====================================================
    if not branch:

        products_count = (
            Product.query
            .filter(Product.is_deleted.is_(False))
            .count()
        )

        drafts_count = (
            Product.query
            .filter(
                Product.is_deleted.is_(False),
                Product.is_active.is_(False)
            )
            .count()
        )

        promotions_count = (
            ProductPromotion.query
            .filter(
                ProductPromotion.is_active.is_(True)
            )
            .count()
        )

        return render_template(
            "productmanager/dashboard.html",
            branch=None,
            staff=staff,
            products_count=products_count,
            promotions_count=promotions_count,
            drafts_count=drafts_count,
            staff_count=0,
            orders_count=0,
            pending_orders_count=0,
            unassigneddeliveries_count=0,
            low_stock_count=0,
            activity_logs=[]
        )
    # =====================================================
    # ACTIVITY LOGS
    # =====================================================
    # =====================================================
# PRODUCT RELATED ACTIVITY ONLY
# =====================================================

    product_actions = [
        "PRODUCT_CREATED",
        "PRODUCT_UPDATED",
        "PRODUCT_DELETED",
        "PRODUCT_VARIANT_CREATED",
        "PRODUCT_VARIANT_UPDATED",
        "PRODUCT_VARIANT_DELETED",
        "INVENTORY_UPDATED",
        "ORDER_CREATED",
        "ORDER_CANCELLED",
        "ORDER_COMPLETED",
        "ANALYTICS_VIEWED"
    ]

    activity_logs = (
        AuditLog.query
        .filter(
            AuditLog.action.in_(product_actions)
        )
        .order_by(AuditLog.timestamp.desc())
        .limit(20)
        .all()
    )
    # =====================================================
    # RENDER
    # =====================================================
    return render_template(
        "productmanager/dashboard.html",
        branch=branch,
        staff=staff,
        products_count=products_count,
        promotions_count=promotions_count,
        drafts_count=drafts_count,
        activity_logs=activity_logs
    )


# =====================================================
# LIST STORES (PRODUCT COVERAGE)
# =====================================================
@productmanager_bp.route("/stores")
@login_required
@role_required("PRODUCTMANAGER")
def stores():

    page = request.args.get("page", 1, type=int)
    tab = request.args.get("tab", "all")

    # =====================================================
    # TOTAL GLOBAL PRODUCTS
    # =====================================================

    total_products = Product.query.count()

    # =====================================================
    # BASE STORE QUERY
    # =====================================================

    stores_query = (
        StoreBranch.query
        .filter_by(is_deleted=False)
        .order_by(StoreBranch.id.desc())
    )

    stores_pagination = stores_query.paginate(
        page=page,
        per_page=25,
        error_out=False
    )

    # =====================================================
    # ENRICH STORE OBJECTS
    # =====================================================

    filtered_items = []

    for store in stores_pagination.items:

        # products assigned to this branch
        covered_products = (
            BranchProduct.query
            .filter_by(branch_id=store.id)
            .count()
        )

        missing_products = max(
            total_products - covered_products,
            0
        )

        coverage_percent = (
            round((covered_products / total_products) * 100)
            if total_products else 0
        )

        # dynamic attributes for template
        store.total_products = total_products
        store.covered_products = covered_products
        store.missing_products = missing_products
        store.coverage_percent = coverage_percent

        # =====================================================
        # TAB FILTERING
        # =====================================================

        include = False

        if tab == "all":
            include = True

        elif tab == "complete":
            include = missing_products == 0

        elif tab == "gaps":
            include = missing_products > 0

        elif tab == "lowcoverage":
            include = coverage_percent < 50

        if include:
            filtered_items.append(store)

    # replace pagination items
    stores_pagination.items = filtered_items

    # =====================================================
    # RENDER
    # =====================================================

    return render_template(
        "productmanager/stores.html",
        stores=stores_pagination,
        current_tab=tab
    )




# =====================================================
# VIEW STORE COVERAGE
# =====================================================
@productmanager_bp.route("/stores/<int:store_id>")
@login_required
@role_required("PRODUCTMANAGER")
def view_store(store_id):

    # =====================================================
    # STORE
    # =====================================================

    store = StoreBranch.query.filter_by(
        id=store_id,
        is_deleted=False
    ).first_or_404()

    # =====================================================
    # TOTAL PRODUCTS
    # =====================================================

    total_products = (
        Product.query
        .filter_by(is_deleted=False)
        .count()
    )

    # =====================================================
    # PRODUCTS AVAILABLE IN STORE
    # =====================================================

    branch_products = (
        BranchProduct.query
        .filter_by(
            branch_id=store.id,
            is_available=True
        )
        .all()
    )

    available_product_ids = [
        bp.product_id
        for bp in branch_products
    ]

    available_products = len(available_product_ids)

    # =====================================================
    # MISSING PRODUCTS
    # =====================================================

    if available_product_ids:

        missing_products_query = (
            Product.query
            .filter(
                Product.is_deleted == False,
                ~Product.id.in_(available_product_ids)
            )
            .all()
        )

    else:

        missing_products_query = (
            Product.query
            .filter_by(is_deleted=False)
            .all()
        )

    missing_products_count = len(
        missing_products_query
    )

    # =====================================================
    # LOW STOCK PRODUCTS
    # =====================================================

    low_stock_products = (
        db.session.query(Product.id)
        .join(Product.variants)
        .join(ProductVariant.branch_variants)
        .join(
            BranchProduct,
            BranchProduct.id ==
            BranchProductVariant.branch_product_id
        )
        .join(
            Inventory,
            Inventory.branch_variant_id ==
            BranchProductVariant.id
        )
        .filter(
            BranchProduct.branch_id == store.id,
            Inventory.quantity <= 5
        )
        .group_by(Product.id)
        .count()
    )

    # =====================================================
    # COVERAGE %
    # =====================================================

    coverage_percentage = (
        round(
            (available_products / total_products) * 100
        )
        if total_products else 0
    )

    store.coverage_percentage = (
        coverage_percentage
    )

    # =====================================================
    # TOP SELLING PRODUCTS
    # =====================================================

    top_products = (
        db.session.query(
            Product.name.label("name"),
            db.func.sum(
                OrderItem.quantity
            ).label("sales_count")
        )
        .join(
            OrderItem,
            OrderItem.product_id == Product.id
        )
        .join(
            Order,
            Order.id == OrderItem.order_id
        )
        .filter(
            Order.branch_id == store.id
        )
        .group_by(
            Product.id,
            Product.name
        )
        .order_by(
            db.func.sum(
                OrderItem.quantity
            ).desc()
        )
        .limit(10)
        .all()
    )

    # =====================================================
    # STATS
    # =====================================================

    stats = {
        "total_products": total_products,
        "available_products": available_products,
        "missing_products": missing_products_count,
        "low_stock_products": low_stock_products,
    }

    # =====================================================
    # RENDER
    # =====================================================

    return render_template(
        "productmanager/storeprofile.html",
        store=store,
        stats=stats,
        missing_products=missing_products_query,
        top_products=top_products
    )


# =====================================================
# PRODUCT PERFORMANCE
# =====================================================
@productmanager_bp.route("/orders")
@login_required
@role_required("PRODUCTMANAGER")
def productperformance():

    # =================================================
    # QUERY PARAMS
    # =================================================
    page = request.args.get("page", 1, type=int)

    tab = request.args.get("tab", "all").strip().lower()

    # =================================================
    # BASE QUERY
    # =================================================
    query = (
        db.session.query(
            Product.id.label("product_id"),

            Product.name.label("name"),

            db.func.coalesce(
                db.func.sum(OrderItem.quantity),
                0
            ).label("units_sold"),

            db.func.coalesce(
                db.func.sum(OrderItem.total_price),
                0
            ).label("revenue")
        )
        .join(
            OrderItem,
            OrderItem.product_id == Product.id
        )
        .join(
            Order,
            Order.id == OrderItem.order_id
        )
        .filter(
            Order.status != OrderStatus.CANCELLED
        )
        .group_by(
            Product.id,
            Product.name
        )
    )

    # =================================================
    # TAB FILTERS
    # =================================================
    if tab == "top":

        query = query.order_by(
            db.func.sum(OrderItem.quantity).desc()
        )

    elif tab == "low":

        query = query.order_by(
            db.func.sum(OrderItem.quantity).asc()
        )

    else:
        # =================================================
        # DEFAULT = ALL
        # =================================================
        tab = "all"

        query = query.order_by(
            db.func.sum(OrderItem.quantity).desc()
        )

    # =================================================
    # PAGINATION
    # =================================================
    pagination = query.paginate(
        page=page,
        per_page=20,
        error_out=False
    )

    # =================================================
    # FORMAT DATA
    # =================================================
    products = []

    for item in pagination.items:

        units_sold = int(item.units_sold or 0)

        revenue = round(
            float(item.revenue or 0),
            2
        )

        # =================================================
        # SIMPLE TREND LOGIC
        # =================================================
        if units_sold >= 100:
            trend = "up"

        elif units_sold <= 10:
            trend = "down"

        else:
            trend = "stable"

        products.append({
            "id": item.product_id,
            "name": item.name,
            "units_sold": units_sold,
            "revenue": revenue,
            "trend": trend
        })

    # =================================================
    # RENDER
    # =================================================
    return render_template(
        "productmanager/productperformance.html",
        products=products,
        pagination=pagination,
        current_tab=tab
    )

# =====================================================
# PRODUCT MANAGER GLOBAL ANALYTICS
# =====================================================
@productmanager_bp.route("/analytics")
@login_required
@role_required("PRODUCTMANAGER")
def analytics():

    # =================================================
    # DATE RANGE
    # =================================================
    days = request.args.get("range", 30, type=int)

    if days not in [7, 30, 90]:
        days = 30

    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # =================================================
    # BASE ORDERS QUERY (GLOBAL)
    # =================================================
    orders_query = (
        Order.query
        .options(
            joinedload(Order.user)
            .joinedload(User.customer_profile)
        )
        .filter(
            Order.created_at >= start_date
        )
    )

    all_orders = orders_query.all()

    # =================================================
    # KPI DATA (GLOBAL)
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
    # CUSTOMER COUNT (GLOBAL)
    # =================================================
    customer_count = (
        db.session.query(Order.user_id)
        .filter(Order.created_at >= start_date)
        .distinct()
        .count()
    )

    # =================================================
    # DELIVERY SUCCESS (GLOBAL)
    # =================================================
    deliveries_query = (
        Delivery.query.filter(
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
    # TOP PRODUCTS (GLOBAL)
    # =================================================
    top_products_query = (
        db.session.query(
            Product.name.label("name"),
            func.count(OrderItem.id).label("orders"),
            func.coalesce(func.sum(OrderItem.total_price), 0).label("revenue")
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.created_at >= start_date)
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
    # MOST SEARCHED PRODUCTS (GLOBAL)
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
    # TOP STORES (GLOBAL INSTEAD OF SINGLE BRANCH)
    # =================================================
    top_stores_query = (
        db.session.query(
            StoreBranch.name.label("name"),
            func.count(Order.id).label("orders"),
            func.coalesce(func.sum(Order.subtotal_amount), 0).label("revenue")
        )
        .join(Order, Order.branch_id == StoreBranch.id)
        .filter(Order.created_at >= start_date)
        .group_by(StoreBranch.id, StoreBranch.name)
        .order_by(func.sum(Order.subtotal_amount).desc())
        .limit(10)
        .all()
    )

    top_stores = [
        {
            "name": s.name,
            "revenue": round(float(s.revenue or 0), 2),
            "orders": s.orders,
            "refund_rate": 0
        }
        for s in top_stores_query
    ]

    # =================================================
    # COURIER PERFORMANCE (GLOBAL)
    # =================================================
    courier_query = (
        db.session.query(
            User,
            func.count(Delivery.id).label("deliveries")
        )
        .join(Delivery, Delivery.courier_id == User.id)
        .options(joinedload(User.courier_profile))
        .filter(Delivery.created_at >= start_date)
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
                "on_time": 100,
                "avg_time": 25
            })

    # =================================================
    # TOP CUSTOMERS (GLOBAL)
    # =================================================
    customer_query = (
        db.session.query(
            User,
            func.count(Order.id).label("orders"),
            func.coalesce(func.sum(Order.subtotal_amount), 0).label("spend")
        )
        .join(Order, Order.user_id == User.id)
        .options(joinedload(User.customer_profile))
        .filter(Order.created_at >= start_date)
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
        "productmanager/analytics.html",
        branch=None,
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
# PRODUCT MANAGER LIST PRODUCTS
# MASTER CATALOG VIEW
# =====================================================
@productmanager_bp.route("/products")
@login_required
@role_required("PRODUCTMANAGER")
def products():

    # =================================================
    # QUERY PARAMS
    # =================================================
    page = request.args.get("page", 1, type=int)

    # Default tab = ALL
    tab = request.args.get("tab", "all").strip().lower()

    search = request.args.get("search", "").strip()

    # =================================================
    # BASE QUERY
    # =================================================
    query = (
        Product.query
        .options(
            joinedload(Product.images),
            joinedload(Product.variants)
        )
    )

    # =================================================
    # SEARCH
    # =================================================
    if search:

        query = (
            query.outerjoin(
                ProductVariant,
                ProductVariant.product_id == Product.id
            )
            .filter(
                db.or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.category.ilike(f"%{search}%"),
                    Product.brand.ilike(f"%{search}%"),
                    ProductVariant.sku.ilike(f"%{search}%")
                )
            )
        )

    # =================================================
    # TAB FILTERING
    # =================================================
    if tab == "deleted":

        query = query.filter(
            Product.is_deleted.is_(True)
        )

    elif tab == "available":

        query = query.filter(
            Product.is_deleted.is_(False),
            Product.is_active.is_(True)
        )

    elif tab == "draft":

        query = query.filter(
            Product.is_deleted.is_(False),
            Product.is_active.is_(False)
        )

    else:
        # =================================================
        # DEFAULT = ALL NON-DELETED
        # =================================================
        tab = "all"

        query = query.filter(
            Product.is_deleted.is_(False)
        )

    # =================================================
    # REMOVE DUPLICATES
    # =================================================
    query = query.distinct(Product.id)

    # =================================================
    # ORDERING
    # =================================================
    query = query.order_by(
        Product.created_at.desc()
    )

    # =================================================
    # PAGINATION
    # =================================================
    products = query.paginate(
        page=page,
        per_page=20,
        error_out=False
    )

    # =================================================
    # ENRICH PRODUCT DATA
    # =================================================
    for product in products.items:

        # -----------------------------
        # PRIMARY IMAGE
        # -----------------------------
        product.primary_image = next(
            (
                image
                for image in product.images
                if image.is_primary
            ),
            None
        )

        # -----------------------------
        # DEFAULT VARIANT
        # -----------------------------
        product.default_variant = next(
            (
                variant
                for variant in product.variants
                if variant.is_default
            ),
            None
        )

        # -----------------------------
        # FALLBACK VARIANT
        # -----------------------------
        if not product.default_variant and product.variants:

            product.default_variant = product.variants[0]

    # =================================================
    # RENDER
    # =================================================
    return render_template(
        "productmanager/products.html",
        products=products,
        current_tab=tab,
        search=search
    )



# =====================================================
# PRODUCT MANAGER VIEW PRODUCT
# =====================================================
@productmanager_bp.route("/products/<int:product_id>")
@login_required
@role_required("PRODUCTMANAGER")
def view_product(product_id):

    # =================================================
    # LOAD PRODUCT (OPTIMIZED)
    # =================================================
    product = (
        Product.query
        .options(
            joinedload(Product.images),
            joinedload(Product.variants)
                .joinedload(ProductVariant.branch_variants),
            joinedload(Product.branch_products)
                .joinedload(BranchProduct.branch)
        )
        .filter(Product.id == product_id)
        .first_or_404()
    )

    # =================================================
    # PRIMARY IMAGE
    # =================================================
    primary_image = next(
        (img for img in product.images if img.is_primary),
        None
    )

    # =================================================
    # MAP BRANCH PRODUCTS (FAST LOOKUP)
    # =================================================
    branch_product_map = {
        bp.id: bp
        for bp in product.branch_products
    }

    # =================================================
    # VARIANT MATRIX
    # =================================================
    variant_data = []

    for variant in product.variants:

        branch_inventory = []
        total_stock = 0

        # FIX: use branch_variants (NOT inventory_items)
        for bpv in variant.branch_variants:

            quantity = (
                bpv.inventory.quantity
                if bpv.inventory else 0
            )

            total_stock += quantity

            branch_product = branch_product_map.get(
                bpv.branch_product_id
            )

            branch_inventory.append({
                "branch": (
                    bpv.branch_product.branch
                    if bpv.branch_product else None
                ),
                "inventory": bpv.inventory,
                "branch_product": branch_product,
                "stock": quantity
            })

        variant_data.append({
            "variant": variant,
            "branches": branch_inventory,
            "total_stock": total_stock
        })

    # =================================================
    # TOTAL STOCK
    # =================================================
    total_stock = sum(v["total_stock"] for v in variant_data)

    # =================================================
    # ACTIVE BRANCHES
    # =================================================
    active_branches = sum(
        1 for bp in product.branch_products
        if bp.is_available
    )

    # =================================================
    # RENDER
    # =================================================
    return render_template(
        "productmanager/viewproduct.html",
        product=product,
        variant_data=variant_data,
        total_stock=total_stock,
        active_branches=active_branches,
        primary_image=primary_image
    )




# =====================================================
# PRODUCT MANAGER CREATE PRODUCT
# =====================================================
@productmanager_bp.route(
    "/products/create",
    methods=["GET", "POST"]
)
@login_required
@role_required("PRODUCTMANAGER")
def create_product():

    if request.method == "GET":
        return render_template("productmanager/createproduct.html")

    try:

        # =================================================
        # FORM DATA
        # =================================================
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        brand = request.form.get("brand", "").strip()

        sku = request.form.get("sku", "").strip().upper()

        variant_name = request.form.get("variant_name", "Standard").strip()
        variant_value = request.form.get("variant_value", name).strip()

        selling_price = request.form.get("selling_price", type=float)
        compare_at_price = request.form.get("compare_at_price", type=float)

        image = request.files.get("image")

        # =================================================
        # VALIDATION
        # =================================================
        if not name:
            flash("Product name is required.", "danger")
            return redirect(url_for("productmanager.create_product"))

        if not category:
            flash("Category is required.", "danger")
            return redirect(url_for("productmanager.create_product"))

        if not sku:
            flash("SKU is required.", "danger")
            return redirect(url_for("productmanager.create_product"))

        if selling_price is None:
            flash("Selling price is required.", "danger")
            return redirect(url_for("productmanager.create_product"))

        # =================================================
        # SKU UNIQUENESS
        # =================================================
        existing_variant = ProductVariant.query.filter_by(sku=sku).first()

        if existing_variant:
            flash("SKU already exists.", "danger")
            return redirect(url_for("productmanager.create_product"))

        # =================================================
        # CREATE PRODUCT
        # =================================================
        product = Product(
            name=name,
            category=category,
            description=description or None,
            brand=brand or None
        )

        db.session.add(product)
        db.session.flush()  # get product.id

        # =================================================
        # CREATE DEFAULT VARIANT
        # =================================================
        variant = ProductVariant(
            product_id=product.id,
            sku=sku,
            name=variant_name,
            value=variant_value,
            selling_price=selling_price,
            compare_at_price=compare_at_price if compare_at_price else None,
            is_default=True
        )

        db.session.add(variant)

        # =================================================
        # IMAGE (PRIMARY ONLY)
        # =================================================
        if image and image.filename:

            image_url = save_image_secure(image)

            # ensure only one primary exists
            db.session.add(
                ProductImage(
                    product_id=product.id,
                    image_url=image_url,
                    is_primary=True
                )
            )

        # =================================================
        # AUDIT LOG
        # =================================================
        request_meta = get_request_meta()

        log_action(
            user_id=current_user.id,
            email=current_user.email,
            action="CREATE_PRODUCT",
            entity_type="PRODUCT",
            entity_id=product.id,
            ip_address=request_meta["ip"],
            user_agent=request_meta["user_agent"],
            meta_data={
                "product_name": name,
                "category": category,
                "brand": brand,
                "sku": sku,
                "selling_price": selling_price
            }
        )

        # =================================================
        # COMMIT
        # =================================================
        db.session.commit()

        flash("Product created successfully.", "success")

        return redirect(url_for("productmanager.products"))

    except Exception as e:
        db.session.rollback()
        print(f"[PRODUCT CREATE ERROR]: {str(e)}")

        flash("Failed to create product.", "danger")
        return redirect(url_for("productmanager.create_product"))  






# =====================================================
# PRODUCT MANAGER BULK CREATE
# =====================================================
@productmanager_bp.route("/products/bulk-create", methods=["GET", "POST"])
@login_required
@role_required("PRODUCTMANAGER")
def bulk_create_products():

    if request.method == "GET":
        return render_template("productmanager/bulkcreate.html")

    excel_file = request.files.get("excel_file")

    if not excel_file or not excel_file.filename.endswith(".xlsx"):
        flash("Please upload a valid .xlsx file.", "danger")
        return redirect(url_for("productmanager.bulk_create_products"))

    try:
        workbook = load_workbook(excel_file)
        worksheet = workbook.active

        # =================================================
        # MAP EMBEDDED IMAGES
        # =================================================
        images_map = {}
        for image in worksheet._images:
            try:
                row_position = image.anchor._from.row + 1
                col_position = image.anchor._from.col + 1
                images_map[(row_position, col_position)] = image
            except Exception as e:
                print("[IMAGE MAP ERROR]:", str(e))

        created_count = 0
        skipped_rows = []
        request_meta = get_request_meta()

        # =================================================
        # PROCESS ROWS
        # =================================================
        for row_index, row in enumerate(
            worksheet.iter_rows(min_row=2, values_only=False),
            start=2
        ):
            try:
                # =================================================
                # EXCEL COLUMNS (UPDATED)
                # =================================================
                name = str(row[0].value or "").strip()
                category = str(row[1].value or "").strip()
                description = str(row[2].value or "").strip()
                sku = str(row[3].value or "").strip().upper()

                brand = str(row[4].value or "").strip()  # ✅ NEW

                variant_name = str(row[5].value or "Standard").strip()
                variant_value = str(row[6].value or name).strip()

                selling_price = row[7].value
                compare_at_price = row[8].value

                # =================================================
                # VALIDATION
                # =================================================
                if not name:
                    skipped_rows.append(f"Row {row_index}: Missing product name")
                    continue

                if not category:
                    skipped_rows.append(f"Row {row_index}: Missing category")
                    continue

                if not sku:
                    skipped_rows.append(f"Row {row_index}: Missing SKU")
                    continue

                if selling_price is None:
                    skipped_rows.append(f"Row {row_index}: Missing selling price")
                    continue

                # =================================================
                # SKU UNIQUENESS
                # =================================================
                existing_variant = ProductVariant.query.filter_by(sku=sku).first()

                if existing_variant:
                    skipped_rows.append(f"Row {row_index}: SKU {sku} already exists")
                    continue

                # =================================================
                # CREATE PRODUCT
                # =================================================
                product = Product(
                    name=name,
                    category=category,
                    description=description,
                    brand=brand   # ✅ FIXED
                )

                db.session.add(product)
                db.session.flush()

                # =================================================
                # CREATE VARIANT
                # =================================================
                variant = ProductVariant(
                    product_id=product.id,
                    sku=sku,
                    name=variant_name,
                    value=variant_value,
                    selling_price=selling_price,
                    compare_at_price=compare_at_price,
                    is_default=True
                )

                db.session.add(variant)

                # =================================================
                # PROCESS IMAGE (FIXED COLUMN)
                # =================================================
                image = images_map.get((row_index, 10))  # ✅ correct Excel column

                if image:
                    try:
                        image_bytes = image._data()
                        image_stream = BytesIO(image_bytes)
                        image_stream.seek(0)

                        image_url = save_bulk_image(image_stream)

                        product_image = ProductImage(
                            product_id=product.id,
                            image_url=image_url,
                            is_primary=True
                        )

                        db.session.add(product_image)

                    except Exception as image_error:
                        skipped_rows.append(
                            f"Row {row_index}: Image processing failed"
                        )
                        print("[BULK IMAGE ERROR]:", str(image_error))

                # =================================================
                # AUDIT LOG
                # =================================================
                log_action(
                    user_id=current_user.id,
                    email=current_user.email,
                    action="BULK_CREATE_PRODUCT",
                    entity_type="PRODUCT",
                    entity_id=product.id,
                    ip_address=request_meta["ip"],
                    user_agent=request_meta["user_agent"],
                    meta_data={
                        "product_name": name,
                        "category": category,
                        "sku": sku
                    }
                )

                created_count += 1

            except Exception as row_error:
                skipped_rows.append(f"Row {row_index}: {str(row_error)}")

        db.session.commit()

        flash(f"{created_count} products uploaded successfully.", "success")

        if skipped_rows:
            flash(f"{len(skipped_rows)} rows skipped.", "warning")
            for err in skipped_rows[:10]:
                flash(err, "danger")

        return redirect(url_for("productmanager.products"))

    except Exception as e:
        db.session.rollback()
        print("[BULK PRODUCT ERROR]:", str(e))
        flash("Failed to upload products.", "danger")
        return redirect(url_for("productmanager.bulk_create_products"))
    



# =====================================================
# PRODUCT MANAGER EDIT PRODUCT (REFORMATTED)
# =====================================================
@productmanager_bp.route(
    "/products/<int:product_id>/edit",
    methods=["GET", "POST"]
)
@login_required
@role_required("PRODUCTMANAGER")
def edit_product(product_id):

    # =================================================
    # LOAD PRODUCT
    # =================================================
    product = (
        Product.query
        .options(
            joinedload(Product.images),
            joinedload(Product.variants)
        )
        .filter(
            Product.id == product_id,
            Product.is_deleted.is_(False)
        )
        .first_or_404()
    )

    # =================================================
    # DEFAULT VARIANT (single-variant model)
    # =================================================
    variant = next(
        (v for v in product.variants if v.is_default),
        None
    )

    if not variant:
        flash("Default product variant not found.", "danger")
        return redirect(url_for("productmanager.products"))

    # =================================================
    # PRIMARY IMAGE
    # =================================================
    primary_image = next(
        (img for img in product.images if img.is_primary),
        None
    )

    # =================================================
    # GET
    # =================================================
    if request.method == "GET":
        return render_template(
            "productmanager/editproduct.html",
            product=product,
            variant=variant,
            primary_image=primary_image
        )

    # =================================================
    # POST - FORM DATA (MATCH CREATE ROUTE EXACTLY)
    # =================================================
    try:
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        brand = request.form.get("brand", "").strip()

        sku = request.form.get("sku", "").strip().upper()

        variant_name = request.form.get("variant_name", "Standard").strip()
        variant_value = request.form.get("variant_value", name).strip()

        selling_price = request.form.get("selling_price", type=float)
        compare_at_price = request.form.get("compare_at_price", type=float)

        image = request.files.get("image")

        # =================================================
        # VALIDATION
        # =================================================
        if not name:
            flash("Product name is required.", "danger")
            return redirect(url_for("productmanager.edit_product", product_id=product.id))

        if not category:
            flash("Category is required.", "danger")
            return redirect(url_for("productmanager.edit_product", product_id=product.id))

        if not sku:
            flash("SKU is required.", "danger")
            return redirect(url_for("productmanager.edit_product", product_id=product.id))

        if selling_price is None:
            flash("Selling price is required.", "danger")
            return redirect(url_for("productmanager.edit_product", product_id=product.id))

        # =================================================
        # SKU UNIQUENESS CHECK (SAFE)
        # =================================================
        existing_sku = (
            ProductVariant.query
            .filter(
                ProductVariant.sku == sku,
                ProductVariant.id != variant.id
            )
            .first()
        )

        if existing_sku:
            flash("SKU already exists.", "danger")
            return redirect(url_for("productmanager.edit_product", product_id=product.id))

        # =================================================
        # STORE OLD VALUES (FOR AUDIT)
        # =================================================
        old_values = {
            "name": product.name,
            "category": product.category,
            "description": product.description,
            "brand": product.brand,
            "sku": variant.sku,
            "variant_name": variant.name,
            "variant_value": variant.value,
            "selling_price": str(variant.selling_price),
            "compare_at_price": str(variant.compare_at_price)
        }

        # =================================================
        # UPDATE PRODUCT (CORE FIELDS)
        # =================================================
        product.name = name
        product.category = category
        product.description = description or None
        product.brand = brand or None

        # =================================================
        # UPDATE VARIANT (MATCH CREATE LOGIC)
        # =================================================
        variant.sku = sku
        variant.name = variant_name
        variant.value = variant_value
        variant.selling_price = selling_price
        variant.compare_at_price = compare_at_price

        # =================================================
        # IMAGE UPDATE (REPLACE PRIMARY)
        # =================================================
        image_changed = False
        new_image_url = None

        if image and image.filename:
            new_image_url = save_image_secure(image)

            if primary_image:
                primary_image.is_primary = False

            db.session.add(ProductImage(
                product_id=product.id,
                image_url=new_image_url,
                is_primary=True
            ))

            image_changed = True

        # =================================================
        # BUILD NEW VALUES (FOR AUDIT)
        # =================================================
        new_values = {
            "name": name,
            "category": category,
            "description": description,
            "brand": brand,
            "sku": sku,
            "variant_name": variant_name,
            "variant_value": variant_value,
            "selling_price": str(selling_price),
            "compare_at_price": str(compare_at_price)
        }

        # =================================================
        # CHANGE TRACKING
        # =================================================
        changes = {}

        for key in old_values:
            if str(old_values[key]) != str(new_values.get(key)):
                changes[key] = {
                    "before": old_values[key],
                    "after": new_values.get(key)
                }

        if image_changed:
            changes["image"] = {
                "before": primary_image.image_url if primary_image else None,
                "after": new_image_url
            }

        # =================================================
        # AUDIT LOG
        # =================================================
        request_meta = get_request_meta()

        log_action(
            user_id=current_user.id,
            email=current_user.email,
            action="EDIT_PRODUCT",
            entity_type="PRODUCT",
            entity_id=product.id,
            ip_address=request_meta["ip"],
            user_agent=request_meta["user_agent"],
            meta_data={
                "product_id": product.id,
                "changes": changes
            }
        )

        # =================================================
        # COMMIT
        # =================================================
        db.session.commit()

        flash("Product updated successfully.", "success")

        return redirect(
            url_for("productmanager.view_product", product_id=product.id)
        )

    except Exception as e:
        db.session.rollback()
        print(f"[EDIT PRODUCT ERROR]: {str(e)}")

        flash("Failed to update product.", "danger")

        return redirect(
            url_for("productmanager.edit_product", product_id=product.id)
        )
    

    

# =====================================================
# PRODUCT MANAGER SOFT DELETE PRODUCT
# =====================================================
@productmanager_bp.route(
    "/products/<int:product_id>/delete",
    methods=["POST"]
)
@login_required
@role_required("PRODUCTMANAGER")
def delete_product(product_id):

    try:

        # =================================================
        # LOAD PRODUCT
        # =================================================
        product = (
            Product.query
            .filter(
                Product.id == product_id,
                Product.is_deleted.is_(False)
            )
            .first_or_404()
        )

        # =================================================
        # SOFT DELETE
        # =================================================
        product.is_deleted = True

        # =================================================
        # OPTIONAL:
        # DISABLE ALL BRANCH AVAILABILITY
        # =================================================
        BranchProduct.query.filter_by(
            product_id=product.id
        ).update(
            {
                "is_available": False
            },
            synchronize_session=False
        )

        # =================================================
        # AUDIT LOG
        # =================================================
        request_meta = get_request_meta()

        log_action(
            user_id=current_user.id,
            email=current_user.email,
            action="DELETE_PRODUCT",
            entity_type="PRODUCT",
            entity_id=product.id,
            ip_address=request_meta["ip"],
            user_agent=request_meta["user_agent"],
            meta_data={
                "product_id": product.id,
                "product_name": product.name,
                "soft_deleted": True
            }
        )

        # =================================================
        # COMMIT
        # =================================================
        db.session.commit()

        flash(
            "Product deleted successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print(
            f"[DELETE PRODUCT ERROR]: {str(e)}"
        )

        flash(
            "Failed to delete product.",
            "danger"
        )

    return redirect(
        url_for("productmanager.products")
    )



# =====================================================
# PRODUCT MANAGER RESTORE PRODUCT
# =====================================================
@productmanager_bp.route(
    "/products/<int:product_id>/restore",
    methods=["POST"]
)
@login_required
@role_required("PRODUCTMANAGER")
def restore_product(product_id):

    try:

        # =================================================
        # LOAD PRODUCT
        # =================================================
        product = (
            Product.query
            .filter(
                Product.id == product_id
            )
            .first_or_404()
        )

        # =================================================
        # VALIDATION
        # =================================================
        if not product.is_deleted:

            flash(
                "Product is already active.",
                "warning"
            )

            return redirect(
                url_for("productmanager.products")
            )

        # =================================================
        # RESTORE PRODUCT
        # =================================================
        product.is_deleted = False

        # =================================================
        # OPTIONAL:
        # RE-ENABLE BRANCH PRODUCTS
        # ONLY IF YOU WANT AUTO RESTORE
        # =================================================
        BranchProduct.query.filter_by(
            product_id=product.id
        ).update(
            {
                "is_available": True
            },
            synchronize_session=False
        )

        # =================================================
        # AUDIT LOG
        # =================================================
        request_meta = get_request_meta()

        log_action(
            user_id=current_user.id,
            email=current_user.email,
            action="RESTORE_PRODUCT",
            entity_type="PRODUCT",
            entity_id=product.id,
            ip_address=request_meta["ip"],
            user_agent=request_meta["user_agent"],
            meta_data={
                "product_id": product.id,
                "product_name": product.name,
                "restored": True
            }
        )

        # =================================================
        # COMMIT
        # =================================================
        db.session.commit()

        flash(
            "Product restored successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print(
            f"[RESTORE PRODUCT ERROR]: {str(e)}"
        )

        flash(
            "Failed to restore product.",
            "danger"
        )

    return redirect(
        url_for("productmanager.products")
    )

