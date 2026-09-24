from flask import redirect, url_for, flash
from flask_login import logout_user
from app.util.audit_helper import log_action


ROLE_REDIRECTS = {
    "ADMIN": "admin.dashboard",
    "SYSTEMMANAGER": "systemmanager.dashboard",
    "PRODUCTMANAGER": "productmanager.dashboard",
    "STOREMANAGER": "storemanager.dashboard",
    "DELIVERYMANAGER": "deliverymanager.dashboard",
    "DELIVERYSUPERVISOR": "deliverysupervisor.dashboard",
    "STAFF": "staff.dashboard",
    "COURIER": "courier.dashboard",
    "CUSTOMER": "customer.shop"
}


def redirect_by_role(user):
    for role in ROLE_REDIRECTS:
        if user.has_role(role):
            return redirect(url_for(ROLE_REDIRECTS[role]))

    log_action(user.id, f"Invalid RBAC state | roles={[r.name for r in user.roles]}")
    logout_user()
    flash("Account error. Contact support.", "danger")

    return redirect(url_for("auth.login"))