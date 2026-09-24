# app/routes/auth.py

from flask import render_template, request, redirect, url_for, session, flash, abort
from flask_login import login_user, logout_user, current_user, login_required

from datetime import datetime, timezone
import re

from app.extensions import db
from app.models.user import User
from app.models.role import Role
from app.models.audit import AuditLog

from app.security.rate_limit import limiter
from app.util.audit_helper import log_action, get_request_meta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from . import auth_bp

from app.util.redirect import redirect_by_role
from app.models.customerprofile import CustomerProfile
from app.util.idgenerator import generate_public_id
from app.models.storebranch import StoreBranch

ph = PasswordHasher()

# -----------------------------
# CONFIG
# -----------------------------
MAX_LOGIN_ATTEMPTS = 5


# -----------------------------
# HELPERS
# -----------------------------
def is_valid_email(email: str) -> bool:
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


def is_strong_password(password: str) -> bool:
    return len(password) >= 8

@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    # -----------------------------
    # AVAILABLE LOCATIONS
    # -----------------------------
    locations_query = (
        db.session.query(StoreBranch.city)
        .filter(
            StoreBranch.is_active.is_(True),
            StoreBranch.is_deleted.is_(False),
            StoreBranch.city.isnot(None)
        )
        .distinct()
        .order_by(StoreBranch.city.asc())
        .all()
    )

    locations = [row[0] for row in locations_query]

    if request.method == "POST":

        # -----------------------------
        # FORM DATA
        # -----------------------------
        first_name = request.form.get("firstName", "").strip()
        last_name = request.form.get("lastName", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        country_code = request.form.get("countryCode", "").strip()
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()

        # -----------------------------
        # FORMAT PHONE
        # -----------------------------
        phone = phone.replace(" ", "").replace("-", "")
        full_phone = f"{country_code}{phone}" if phone else None

        meta = get_request_meta()

        # -----------------------------
        # VALIDATION
        # -----------------------------
        if not all([first_name, last_name, email, password, full_phone, location]):
            flash("All fields are required.", "warning")
            return redirect(url_for("auth.register"))

        if not is_valid_email(email):
            flash("Invalid email format.", "warning")
            return redirect(url_for("auth.register"))

        if not is_strong_password(password):
            flash("Password must be at least 8 characters.", "warning")
            return redirect(url_for("auth.register"))

        # -----------------------------
        # VALIDATE LOCATION
        # -----------------------------
        if location not in locations:
            flash("Invalid location selected.", "warning")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("Account already exists.", "warning")
            return redirect(url_for("auth.login"))

        if User.query.filter_by(phone_number=full_phone).first():
            flash("Phone already registered", "warning")
            return redirect(url_for("auth.register"))

        # -----------------------------
        # GET CUSTOMER ROLE
        # -----------------------------
        role = Role.query.filter_by(name="CUSTOMER").first()

        if not role:
            abort(500, "Customer role missing")

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

            user.password = password
            user.roles.append(role)

            db.session.add(user)
            db.session.flush()

            # -----------------------------
            # GENERATE PUBLIC ID
            # -----------------------------
            public_id = generate_public_id(
                CustomerProfile,
                "cus",
                db.session
            )

            # -----------------------------
            # CREATE PROFILE
            # -----------------------------
            profile = CustomerProfile(
                user_id=user.id,
                public_id=public_id,
                first_name=first_name,
                last_name=last_name,
                city=location
            )

            db.session.add(profile)

            # -----------------------------
            # AUDIT LOG
            # -----------------------------
            log_action(
                user_id=user.id,
                email=user.email,
                action="USER_REGISTERED",
                ip_address=meta["ip"],
                user_agent=meta["user_agent"]
            )

            # -----------------------------
            # COMMIT
            # -----------------------------
            db.session.commit()

            flash("Account created successfully.", "success")

            return redirect(url_for("auth.login"))

        except Exception as e:
            db.session.rollback()
            print("Registration error:", e)
            abort(500)

    return render_template(
        "auth/register.html",
        locations=locations
    )


# -----------------------------
# LOGIN
# -----------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        meta = get_request_meta()

        user = User.query.filter_by(email=email).first()

        # -----------------------------
        # LOCK CHECK
        # -----------------------------
        if user and user.is_locked:
            log_action(
                user_id=user.id,
                email=user.email,
                action="LOGIN_BLOCKED_LOCKED",
                ip_address=meta["ip"],
                user_agent=meta["user_agent"]
            )

            db.session.commit()

            flash("Account locked. Try later.", "danger")
            return redirect(url_for("auth.login"))

        # -----------------------------
        # AUTH CHECK (FAIL CASE)
        # -----------------------------
        if not user or not user.check_password(password):

            if user:
                user.register_failed_login()

            log_action(
                user_id=user.id if user else None,
                email=email,
                action="LOGIN_FAILED",
                ip_address=meta["ip"],
                user_agent=meta["user_agent"]
            )

            db.session.commit()

            flash("Invalid email or password.", "danger")
            return redirect(url_for("auth.login"))

        # -----------------------------
        # ACCESS CHECKS
        # -----------------------------
        if not user.can_login():
            log_action(
                user_id=user.id,
                email=user.email,
                action="LOGIN_BLOCKED_ACCESS_DENIED",
                ip_address=meta["ip"],
                user_agent=meta["user_agent"]
            )

            db.session.commit()

            flash("Account access restricted.", "danger")
            return redirect(url_for("auth.login"))

        if not user.roles:
            log_action(
                user_id=user.id,
                email=user.email,
                action="LOGIN_BLOCKED_NO_ROLES",
                ip_address=meta["ip"],
                user_agent=meta["user_agent"]
            )

            db.session.commit()

            flash("Account misconfigured.", "danger")
            return redirect(url_for("auth.login"))

        # -----------------------------
        # SUCCESS LOGIN
        # -----------------------------
        user.on_successful_login()
        login_user(user)

        log_action(
            user_id=user.id,
            email=user.email,
            action="LOGIN_SUCCESS",
            ip_address=meta["ip"],
            user_agent=meta["user_agent"]
        )

        db.session.commit()

        return redirect_by_role(user)

    return render_template("auth/login.html")




# -----------------------------
# LOGOUT
# -----------------------------
@auth_bp.route("/logout")
@login_required
def logout():

    user_id = current_user.id
    email = current_user.email

    meta = get_request_meta()

    log_action(
        user_id=user_id,
        email=email,
        action="LOGOUT",
        ip_address=meta["ip"],
        user_agent=meta["user_agent"]
    )

    db.session.commit()

    logout_user()

    flash("Logged out successfully.", "info")
    return redirect(url_for("auth.login"))