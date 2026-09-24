from flask import Flask
from app.config import Config
from app.extensions import db, login_manager

from flask_migrate import Migrate 

import stripe
import os
from dotenv import load_dotenv

# MODELS

from app.models.audit import AuditLog
from app.models.branchproduct import BranchProduct
from app.models.branchstaff import BranchStaff
from app.models.cart import Cart
from app.models.cartitem import CartItem
from app.models.courierprofile import CourierProfile
from app.models.customerprofile import CustomerProfile
from app.models.delivery import Delivery
from app.models.deliveryotp import DeliveryOtp
from app.models.deliveryzone import DeliveryZone
from app.models.inventory import Inventory
from app.models.inventoryreservation import InventoryReservation
from app.models.order import Order
from app.models.orderitem import OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.productimages import ProductImage
from app.models.productvariant import ProductVariant
from app.models.role import Role
from app.models.staffprofile import StaffProfile
from app.models.storebranch import StoreBranch
from app.models.user import User
from app.models.userrole import UserRole

# BLUEPRINTS
from app.auth.routes import auth_bp
from app.admin.routes import admin_bp
from app.courier.routes import courier_bp
from app.customer.routes import customer_bp
from app.deliverymanager.routes import deliverymanager_bp
from app.inventorymanager.routes import inventorymanager_bp
from app.payment.routes import payment_bp
from app.staff.routes import staff_bp
from app.storemanager.routes import storemanager_bp
from app.main.routes import main_bp
from app.checkout.routes import checkout_bp
from app.productmanager.routes import productmanager_bp
from app.systemmanager.routes import systemmanager_bp
from app.deliverysupervisor.routes import deliverysupervisor_bp

# INIT EXTENSIONS
migrate = Migrate()

# =========================
# LOGIN MANAGER
# =========================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# =========================
# STRIPE
# =========================
def init_stripe(app):
    stripe.api_key = app.config["STRIPE_SECRET_KEY"]

# =========================
# CREATE APP
# =========================
def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(Config)
    # =========================
    # ENV CONFIG
    # =========================
    app.config["STRIPE_SECRET_KEY"] = os.getenv("STRIPE_SECRET_KEY")
    app.config["STRIPE_WEBHOOK_SECRET"] = os.getenv("STRIPE_WEBHOOK_SECRET")
    # Fail fast 
    if not app.config["STRIPE_SECRET_KEY"]:
        raise ValueError("STRIPE_SECRET_KEY is not set")
    # =========================
    # INIT EXTENSIONS
    # =========================
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    init_stripe(app)
    # =========================
    # REGISTER BLUEPRINTS
    # =========================
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(payment_bp, url_prefix="/payment")
    app.register_blueprint(main_bp)
    app.register_blueprint(customer_bp, url_prefix="/customer")
    app.register_blueprint(storemanager_bp, url_prefix="/storemanager")
    app.register_blueprint(deliverymanager_bp, url_prefix="/deliverymanager")
    app.register_blueprint(inventorymanager_bp, url_prefix="/inventorymanager")
    app.register_blueprint(courier_bp, url_prefix="/courier")
    app.register_blueprint(staff_bp, url_prefix="/staff")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(checkout_bp, url_prefix="/checkout")
    app.register_blueprint(productmanager_bp, url_prefix="/productmanager")
    app.register_blueprint(systemmanager_bp, url_prefix="/systemmanager")
    app.register_blueprint(deliverysupervisor_bp, url_prefix="/deliverysupervisor")

    return app