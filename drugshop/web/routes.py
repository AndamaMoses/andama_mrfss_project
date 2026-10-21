"""Page routes: index, login, staff."""
from flask import Blueprint, current_app, render_template, send_from_directory

from drugshop.apps import registry
from drugshop.apps.service import entitled_app_ids_or_all

bp = Blueprint("web", __name__)


def _tender_only_install():
    """True when the only sellable app active is Tender Copilot."""
    active = entitled_app_ids_or_all()
    return "tender" in active and not (active & set(registry.PHARMACY_APP_IDS))


@bp.route("/")
def index():
    return send_from_directory(current_app.template_folder, "index.html")


@bp.route("/login")
def login_page():
    # The login form is shared auth. Tender-only installs get the Tender
    # Copilot brand and default post-login destination instead of pharmacy copy.
    return render_template("login.html", tender_only=_tender_only_install())


@bp.route("/staff")
def staff_page():
    return send_from_directory(current_app.template_folder, "staff.html")
