# app/scripts/create_admin.py

import getpass

from app import create_app
from app.extensions import db

from app.models.user import User
from app.models.role import Role

from app.util.audit_helper import log_action


# =====================================================
# VALIDATION HELPERS
# =====================================================

def is_valid_email(email: str) -> bool:
    return "@" in email and "." in email


# =====================================================
# CREATE ADMIN SCRIPT
# =====================================================

def create_admin():

    app = create_app()

    with app.app_context():

        print("=== Create Admin User ===")

        try:

            # =====================================================
            # ENSURE ADMIN ROLE EXISTS
            # =====================================================

            admin_role = Role.query.filter_by(name="ADMIN").first()

            if not admin_role:
                print("ADMIN role missing.")
                print("Run seed_roles.py first.")
                return

            # =====================================================
            # EMAIL INPUT
            # =====================================================

            email = input("Enter admin email: ").strip().lower()

            if not email:
                print("Email is required.")
                return

            if not is_valid_email(email):
                print("Invalid email format.")
                return

            # =====================================================
            # EXISTING USER CHECK
            # =====================================================

            existing_user = User.query.filter_by(email=email).first()

            if existing_user:
                print("User already exists.")
                return

            # =====================================================
            # PASSWORD INPUT
            # =====================================================

            password = getpass.getpass("Enter admin password: ")

            confirm_password = getpass.getpass(
                "Confirm admin password: "
            )

            if password != confirm_password:
                print("Passwords do not match.")
                return

            if len(password) < 8:
                print("Password must be at least 8 characters.")
                return

            # =====================================================
            # CREATE USER
            # FOLLOW USER MODEL FLOW
            # =====================================================

            new_admin = User(
                email=email,
                is_active=True,
                email_verified=True,
                is_frozen=False,
                is_deleted=False,
                is_flagged=False
            )

            # Uses User.password setter
            new_admin.password = password

            # Assign ADMIN role
            new_admin.roles.append(admin_role)

            db.session.add(new_admin)

            # Ensures ID exists before audit log
            db.session.flush()

            # =====================================================
            # AUDIT LOG
            # =====================================================

            log_action(
                user_id=new_admin.id,
                email=new_admin.email,
                action="Admin account created",
                entity_type="User",
                entity_id=new_admin.id,
                user_agent="system-script",
                meta_data={
                    "roles": ["ADMIN"],
                    "email_verified": True,
                    "script": "create_admin.py"
                }
            )

            # =====================================================
            # COMMIT TRANSACTION
            # =====================================================

            db.session.commit()

            print("")
            print("===================================")
            print("Admin user created successfully")
            print(f"Email: {new_admin.email}")
            print(f"User ID: {new_admin.id}")
            print("===================================")

        except Exception as e:

            db.session.rollback()

            print("")
            print("===================================")
            print("FAILED TO CREATE ADMIN")
            print("===================================")
            print(str(e))
            print("===================================")


# =====================================================
# ENTRY POINT
# =====================================================

if __name__ == "__main__":
    create_admin()