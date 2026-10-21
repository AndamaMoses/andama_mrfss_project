"""Page routes: index, login, staff."""
from flask import Blueprint, current_app, send_from_directory

bp = Blueprint("web", __name__)


@bp.route("/")
def index():
    return send_from_directory(current_app.template_folder, "index.html")


@bp.route("/login")
def login_page():
    return send_from_directory(current_app.template_folder, "login.html")


@bp.route("/staff")
def staff_page():
    return send_from_directory(current_app.template_folder, "staff.html")
