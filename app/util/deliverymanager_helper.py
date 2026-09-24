from flask import abort
from app.models.branchstaff import BranchStaff
from flask_login import current_user

# =====================================================
# GET MANAGER BRANCH
# =====================================================
def get_deliverymanager_branch():

    branch_staff = BranchStaff.query.filter_by(
        user_id=current_user.id,
        role="DELIVERYMANAGER"
    ).first()

    if not branch_staff:
        abort(403)

    if not branch_staff.branch:
        abort(404)

    return branch_staff.branch