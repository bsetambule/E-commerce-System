from functools import wraps
from flask_login import current_user
from flask import abort, request
from datetime import datetime, timezone

from app.util.audit_helper import log_action


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):

            if not current_user.is_authenticated:
                abort(401)

            if not current_user.is_active:
                abort(403)

            if not any(current_user.has_role(r) for r in roles):

                log_action(
                    user_id=current_user.id,
                    email=current_user.email,
                    action="UNAUTHORISED_ROLE_ACCESS",
                    entity_type="endpoint",
                    entity_id=request.path,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get("User-Agent"),
                    meta_data={
                        "required_roles": roles,
                        "endpoint": request.endpoint,
                        "method": request.method,
                    }
                   
                )

                abort(403)

            return f(*args, **kwargs)

        return wrapper

    return decorator