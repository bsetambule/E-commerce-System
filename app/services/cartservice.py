from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.cart import Cart
from app.models.cartitem import CartItem
from app.models.storebranch import StoreBranch
from app.models.product import Product
from app.models.productvariant import ProductVariant
from app.models.branchproduct import BranchProduct
from app.models.branchproductvariant import BranchProductVariant


class CartService:

    @staticmethod
    def get_or_create_cart(user_id):

        cart = Cart.get_active_cart(user_id)

        if not cart:
            cart = Cart(
                user_id=user_id,
                is_active=True,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
            )
            db.session.add(cart)
            db.session.flush()

        else:
            cart.items.clear()
            cart.is_active = True

        cart.extend_expiry()
        return cart

    @staticmethod
    def add_item(user_id, product_id, variant_id, branch_id, quantity):

        quantity = max(quantity, 1)

        product = Product.query.filter_by(id=product_id, is_deleted=False).first_or_404()

        variant = ProductVariant.query.filter_by(
            id=variant_id,
            product_id=product.id
        ).first()

        if not variant:
            raise ValueError("Invalid variant")

        branch = StoreBranch.query.filter_by(
            id=branch_id,
            is_active=True,
            is_deleted=False
        ).first()

        if not branch:
            raise ValueError("Invalid branch")

        branch_product = BranchProduct.query.filter_by(
            branch_id=branch.id,
            product_id=product.id,
            is_visible=True
        ).first()

        if not branch_product:
            raise ValueError("Product unavailable")

        branch_variant = BranchProductVariant.query.filter_by(
            branch_product_id=branch_product.id,
            variant_id=variant.id,
            is_available=True
        ).first()

        if not branch_variant:
            raise ValueError("Variant unavailable")

        inventory = branch_variant.inventory

        if not inventory or inventory.available_quantity < quantity:
            raise ValueError("Insufficient stock")

        cart = CartService.get_or_create_cart(user_id)

        existing_item = CartItem.query.filter_by(
            cart_id=cart.id,
            branch_variant_id=branch_variant.id
        ).first()

        if existing_item:

            new_qty = existing_item.quantity + quantity

            if inventory.available_quantity < new_qty:
                raise ValueError("Not enough stock")

            existing_item.quantity = new_qty

        else:

            db.session.add(
                CartItem(
                    cart_id=cart.id,
                    variant_id=variant.id,
                    branch_id=branch.id,
                    branch_variant_id=branch_variant.id,
                    quantity=quantity,
                    unit_price_snapshot=variant.selling_price,
                    currency="GBP"
                )
            )

        db.session.commit()