# app/scripts/seed_roles.py

from app import create_app
from app.extensions import db
from app.models.role import Role
from app.util.audit_helper import log_action


DEFAULT_ROLES = [
    "ADMIN",
    "CUSTOMER",

    # SuperStore staff roles
    "SYSTEMMANAGER",
    "STOREMANAGER",
    "PRODUCTMANAGER",
    "DELIVERYMANAGER",
    "DELIVERYSUPERVISOR",
    "COURIER",
    "STAFF"
]

def seed_roles():
    app = create_app()

    with app.app_context():
        print("=== Seeding Roles ===")

        created = []
        existing = []

        for role_name in DEFAULT_ROLES:
            role = Role.query.filter_by(name=role_name).first()

            if role:
                existing.append(role_name)
                continue

            db.session.add(Role(name=role_name))
            created.append(role_name)

        log_action(
            user_id=None,
            action=f"Role seeding completed | created={created} | existing={existing}"
        )

        db.session.commit()

        print(f"Created roles: {created}")
        print(f"Existing roles: {existing}")
        print("Role seeding complete")

if __name__ == "__main__":
    seed_roles()