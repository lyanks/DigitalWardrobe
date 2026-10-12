from flask import Blueprint, current_app, render_template, send_from_directory
from flask_login import login_required

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html", title="Home")


@bp.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    # uploads/ is outside static/, so Flask doesn't serve it automatically.
    # send_from_directory refuses paths like "../config.py", so users can
    # only ever get files that are inside the uploads folder.
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
