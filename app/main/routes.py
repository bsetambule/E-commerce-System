from flask import Blueprint, render_template
from flask_login import current_user
from app.util.redirect import redirect_by_role  # adjust path if needed

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def home():
    return render_template("landingpage/landingpage.html")