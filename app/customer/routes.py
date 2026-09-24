# app/routes/customer.py
from flask import Blueprint, render_template, request, current_app, abort, redirect, flash, url_for, jsonify, session
from flask_login import login_required, current_user
from sqlalchemy import or_, asc, desc
from app.models.product import Product
from app.models.productvariant import ProductVariant
from app.models.productimages import ProductImage
from app.util.audit_helper import log_action
from app.extensions import db
from app.models.cart import Cart
from app.models.orderitem import OrderItem
from app.models.order import Order
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.cartitem import CartItem
from app.models.order import OrderStatus

from app.models.inventory import Inventory
from app.models.deliveryzone import DeliveryZone
from app.models.orderaddress import OrderAddress
from app.models.inventoryreservation import InventoryReservation
from datetime import datetime, timedelta, timezone

from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError
import secrets
from app.security.decorators import role_required
from app.models.storebranch import StoreBranch
from app.models.productsearch import ProductSearch
from app.util.initials_helper import get_user_initials
from app.models.branchproduct import BranchProduct
from app.models.branchproductvariant import BranchProductVariant
from sqlalchemy import func, or_
from app.services.cartservice import CartService

customer_bp = Blueprint("customer", __name__, url_prefix="/customer")

# =====================================================
# CUSTOMER SHOP
# =====================================================
@customer_bp.route("/shop", methods=["GET"])
def shop():

    # =================================================
    # PARAMS
    # =================================================
    search_query = request.args.get("search", "", type=str).strip()
    category_filter = request.args.get("category", "all")
    price_sort = request.args.get("sort", "default")
    fulfillment = request.args.get("fulfillment", "delivery")
    selected_branch_id = request.args.get("branch_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = 12

    # =================================================
    # BRANCHES
    # =================================================
    branches = StoreBranch.query.filter(
        StoreBranch.is_active.is_(True),
        StoreBranch.is_deleted.is_(False)
    ).order_by(StoreBranch.name.asc()).all()

    if not selected_branch_id and branches:
        selected_branch_id = branches[0].id

    if not selected_branch_id:
        return render_template(
            "customer/shop.html",
            products=[],
            pagination=None,
            items_count=0,
            search_query=search_query,
            category_filter=category_filter,
            price_sort=price_sort,
            fulfillment=fulfillment,
            branches=branches,
            selected_branch_id=None,
            user_initials=get_user_initials(current_user)
        )

    # =================================================
    # BASE QUERY (VARIANT-CENTERED — FIXED)
    # =================================================
    query = (
        db.session.query(BranchProductVariant)
        .join(BranchProduct)
        .join(Product)
        .join(
            ProductVariant,
            BranchProductVariant.variant_id == ProductVariant.id
        )
        .join(
            Inventory,
            Inventory.branch_variant_id == BranchProductVariant.id
        )
        .filter(
            Product.is_active.is_(True),
            Product.is_deleted.is_(False),


            BranchProduct.branch_id == selected_branch_id,
            BranchProduct.is_visible.is_(True),

            BranchProductVariant.is_available.is_(True),

            Inventory.quantity > 0,

        )
    )

    # =================================================
    # FULFILLMENT (CORRECT LEVEL)
    # =================================================
    if fulfillment == "pickup":
        query = query.filter(BranchProductVariant.allows_pickup.is_(True))

    elif fulfillment == "delivery":
        query = query.filter(BranchProductVariant.allows_delivery.is_(True))

    # =================================================
    # SEARCH
    # =================================================
    if search_query:
        query = query.filter(
            or_(
                Product.name.ilike(f"%{search_query}%"),
                Product.description.ilike(f"%{search_query}%")
            )
        )

    # =================================================
    # CATEGORY
    # =================================================
    if category_filter != "all":
        query = query.filter(Product.category == category_filter)

    # =================================================
    # SORT
    # =================================================
    if price_sort == "low-high":
        query = query.order_by(ProductVariant.selling_price.asc())
    elif price_sort == "high-low":
        query = query.order_by(ProductVariant.selling_price.desc())
    else:
        query = query.order_by(Product.created_at.desc())
    
    print(query.count())
    # =================================================
    # PAGINATION
    # =================================================
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # =================================================
    # GROUP RESULTS (IMPORTANT FIX)
    # =================================================
    product_map = {}

    for bpv in pagination.items:

        product = bpv.branch_product.product
        variant = bpv.variant

        if product.id not in product_map:
            primary_img = next(
                (img for img in product.images if img.is_primary),
                product.images[0] if product.images else None
            )

            product_map[product.id] = {
                "id": product.id,
                "name": product.name,
                "category": product.category or "Uncategorized",
                "image": primary_img.image_url.split("/")[-1] if primary_img else None,
                "variants": []
            }

        product_map[product.id]["variants"].append({
            "variant_id": variant.id,
            "price": float(variant.selling_price),
            "allows_pickup": bpv.allows_pickup,
            "allows_delivery": bpv.allows_delivery
        })

    # flatten for template (pick cheapest variant as display)
    product_list = []
    for p in product_map.values():
        cheapest = min(p["variants"], key=lambda v: v["price"])

        product_list.append({
            "id": p["id"],
            "name": p["name"],
            "category": p["category"],
            "price": cheapest["price"],
            "variant_id": cheapest["variant_id"],
            "image": p["image"]
        })

    # =================================================
    # RENDER
    # =================================================
    return render_template(
        "customer/shop.html",
        products=product_list,
        pagination=pagination,
        items_count=len(product_list),
        search_query=search_query,
        category_filter=category_filter,
        price_sort=price_sort,
        fulfillment=fulfillment,
        branches=branches,
        selected_branch_id=selected_branch_id,
        user_initials=get_user_initials(current_user)
    )




# -----------------------------
# PRODUCT DETAIL ROUTE
# -----------------------------
@customer_bp.route("/product/<int:product_id>")
def product_detail(product_id):

    product = Product.query.filter_by(
        id=product_id,
        is_deleted=False,
        is_active=True
    ).first_or_404()

    selected_branch_id = request.args.get("branch_id", type=int)

    branches = StoreBranch.query.filter(
        StoreBranch.is_active.is_(True),
        StoreBranch.is_deleted.is_(False)
    ).order_by(StoreBranch.name.asc()).all()

    if not selected_branch_id and branches:
        selected_branch_id = branches[0].id

    default_variant = next(
        (v for v in product.variants if v.is_default),
        product.variants[0] if product.variants else None
    )

    primary_image = next(
        (img for img in product.images if img.is_primary),
        product.images[0] if product.images else None
    )

    if primary_image and primary_image.image_url:
        filename = primary_image.image_url.split("/")[-1]
        product_image_url = f"uploads/{filename}"
    else:
        product_image_url = "images/logo4.jpeg"

    similar_products = Product.query.filter(
        Product.category == product.category,
        Product.id != product.id,
        Product.is_deleted.is_(False),
        Product.is_active.is_(True)
    ).limit(4).all()

    return render_template(
        "customer/productdetail.html",
        product=product,
        default_variant=default_variant,
        product_image_url=product_image_url,
        similar_products=similar_products,
        branches=branches,
        selected_branch_id=selected_branch_id,
        user_initials=get_user_initials(current_user)
    )






# -----------------------------
# CART ROUTE
# -----------------------------
@customer_bp.route("/cart", methods=["GET"])
@login_required
@role_required("CUSTOMER")
def cart():

    cart = Cart.get_active_cart(current_user.id)

    cart_items = []
    
    subtotal_total = 0.0
    shipping = 5.00

    if cart and not cart.is_expired():
        cart_items = []
        for item in cart.items:
            variant = item.variant
            if not variant:
                continue
            product = variant.product
            if not product or product.is_deleted:
                continue

            # -------------------------
            # IMAGE
            # -------------------------
            primary_img = next(
                (
                    img for img in product.images
                    if img.is_primary
                ),
                product.images[0]
                if product.images else None
            )

            image = (
                primary_img.image_url.split("/")[-1]
                if primary_img else None
            )

            # -------------------------
            # PRICE
            # -------------------------
            price = float(variant.selling_price)
            subtotal = price * item.quantity
            subtotal_total += subtotal

            # -------------------------
            # BUILD ITEM
            # -------------------------
            cart_items.append({
                "id": item.id,
                "product_id": product.id,
                "name": product.name,
                "image": image,
                "variant_name": variant.name,
                "variant_value": variant.value,
                "variant_id": variant.id,
                "price": price,
                "quantity": item.quantity,
                "subtotal": subtotal
            })
    total = subtotal_total + shipping

    return render_template(
        "customer/cart.html",
        cart_items=cart_items,
        subtotal=subtotal_total,
        shipping=shipping,
        total=total,
        user_initials=get_user_initials(current_user)
    )

# -----------------------------
# ADD TO CART ROUTE
# -----------------------------
@customer_bp.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
@role_required("CUSTOMER")
def add_to_cart(product_id):

    variant_id = request.form.get("variant_id", type=int)
    branch_id = request.form.get("branch_id", type=int)
    quantity = request.form.get("quantity", type=int) or 1

    try:
        CartService.add_item(
            user_id=current_user.id,
            product_id=product_id,
            variant_id=variant_id,
            branch_id=branch_id,
            quantity=quantity
        )

        flash("Item added to cart", "success")

    except ValueError as e:
        flash(str(e), "error")

    return redirect(url_for("customer.cart"))    


# -----------------------------
# UPDATE QUANTITY ROUTE
# -----------------------------
@customer_bp.route("/cart/update/<int:cart_item_id>", methods=["POST"])
@login_required
@role_required("CUSTOMER")
def update_cart(cart_item_id):

    quantity = request.form.get("quantity", type=int) or 1
    quantity = max(1, quantity)

    # ---------------------------------------
    # GET CART ITEM (SECURE OWNERSHIP CHECK)
    # ---------------------------------------
    cart_item = (
        CartItem.query
        .join(Cart)
        .filter(
            Cart.user_id == current_user.id,
            CartItem.id == cart_item_id
        )
        .first_or_404()
    )

    # ---------------------------------------
    # RESOLVE INVENTORY SAFELY
    # (NO RELIANCE ON missing relationship)
    # ---------------------------------------
    from app.models import BranchProductVariant

    branch_variant = BranchProductVariant.query.get(
        cart_item.branch_variant_id
    )

    if not branch_variant:
        return jsonify({
            "success": False,
            "message": "Variant not found"
        }), 404

    inventory = branch_variant.inventory

    # ---------------------------------------
    # STOCK VALIDATION
    # ---------------------------------------
    if not inventory or inventory.available_quantity < quantity:
        return jsonify({
            "success": False,
            "message": "Insufficient stock"
        }), 400

    # ---------------------------------------
    # UPDATE ITEM
    # ---------------------------------------
    cart_item.quantity = quantity
    db.session.commit()

    # ---------------------------------------
    # ITEM TOTAL (use snapshot price)
    # ---------------------------------------
    subtotal = float(cart_item.unit_price_snapshot) * quantity

    # ---------------------------------------
    # CART TOTAL
    # ---------------------------------------
    cart = cart_item.cart

    total = sum(
        float(item.unit_price_snapshot) * item.quantity
        for item in cart.items
    )

    return jsonify({
        "success": True,
        "subtotal": subtotal,
        "total": total
    })





# -----------------------------
# REMOVE ITEM ROUTE
# -----------------------------
@customer_bp.route("/cart/remove/<int:cart_item_id>", methods=["POST"])
@login_required
@role_required("CUSTOMER")
def remove_from_cart(cart_item_id):

    cart_item = CartItem.query.join(Cart).filter(
        Cart.user_id == current_user.id,
        CartItem.id == cart_item_id
    ).first_or_404()

    db.session.delete(cart_item)

    db.session.commit()

    flash("Item removed from cart.", "success")

    return redirect(url_for("customer.cart"))

# -----------------------------
# ORDER HISTORY ROUTE
# -----------------------------
@customer_bp.route("/orders")
@login_required
@role_required("CUSTOMER")
def orders():

    tab = request.args.get("tab", "all")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = Order.query.filter_by(user_id=current_user.id)

    if tab == "ongoing":
        query = query.filter(
            Order.status.in_([
                OrderStatus.READY_FOR_PICKUP,
                OrderStatus.PROCESSING,
                OrderStatus.SHIPPED
            ])
        )
    query = query.order_by(Order.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template(
        "customer/orderhistory.html",
        orders=pagination,
        current_tab=tab,
        user_initials=get_user_initials(current_user)
    )

# -----------------------------
# ORDER DETAIL ROUTE
# -----------------------------
@customer_bp.route("/orders/<int:order_id>")
@login_required
@role_required("CUSTOMER")
def order_detail(order_id):

    order = (
        Order.query
        .filter_by(
            id=order_id,
            user_id=current_user.id
        )
        .first_or_404()
    )

    return render_template(
        "customer/orderdetail.html",
        order=order,
        user_initials=get_user_initials(current_user)
    )

# -----------------------------
# ORDER SUCCESS ROUTE
# -----------------------------
@customer_bp.route("/order/confirmation/<int:order_id>")
@login_required
def order_confirmation(order_id):
    
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()

    return render_template("customer/ordersuccess.html", order=order, user_initials=get_user_initials(current_user))

# -----------------------------
# ACCOUNT ROUTE
# -----------------------------
@customer_bp.route("/account", methods=["GET", "POST"])
@login_required
@role_required("CUSTOMER")
def account():
    if request.method == "POST":
        
        phone = request.form.get("phone")
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")

        if phone:
            current_user.phone = phone

        # Update password only if provided and matches confirmation
        if password:
            if password != password_confirm:
                flash("Passwords do not match.", "danger")
                return redirect(url_for('customer.account'))
            current_user.password = generate_password_hash(password)

        try:
            db.session.commit()
            flash("Account updated successfully!", "success")
        except Exception:
            db.session.rollback()
            flash("Failed to update account. Try again.", "danger")

        return redirect(url_for('customer.account'))

    # GET request renders account page
    return render_template("customer/account.html", user=current_user)