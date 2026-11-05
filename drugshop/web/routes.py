"""Page routes: index, login, staff."""
from flask import Blueprint, current_app, redirect, render_template, url_for

from drugshop.apps import registry
from drugshop.apps.service import entitled_app_ids_or_all
from drugshop.auth.guards import current_user

bp = Blueprint("web", __name__)


def _tender_only_install():
    """True when the only sellable app active is Tender Copilot."""
    active = entitled_app_ids_or_all()
    return "tender" in active and not (active & set(registry.PHARMACY_APP_IDS))


@bp.route("/")
def index():
    # Do not hand the pharmacy SPA shell to anonymous visitors; boot.js would
    # only bounce them after the shell flashed. Signed-in users still get the
    # normal workspace.
    if not current_user():
        return redirect(url_for("web.login_page"))
    return render_template(
        "index.html",
        demo_mode=bool(current_app.config.get("DEMO_MODE")),
    )


@bp.route("/login")
def login_page():
    # The login form is shared auth. Tender-only installs get the Tender
    # Copilot brand and default post-login destination instead of pharmacy copy.
    return render_template("login.html", tender_only=_tender_only_install())


@bp.route("/staff")
def staff_page():
    if not current_user():
        return redirect(url_for("web.login_page"))
    # The staff view is a separate template (not the SPA), so it needs the
    # plan flags at render time instead of the client-side app catalog.
    active = entitled_app_ids_or_all()
    return render_template(
        "staff.html",
        show_patients="patients" in active,
        show_finance="finance" in active,
    )
