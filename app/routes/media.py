from io import BytesIO
from pathlib import PurePosixPath

from flask import Blueprint, current_app, abort, send_file

from app.services.storage import CONTENT_TYPES, get_public_media_bytes


media_bp = Blueprint("media", __name__)


@media_bp.route("/media/<path:relative_path>")
def public_media(relative_path):
    try:
        body = get_public_media_bytes(relative_path, current_app.config["UPLOAD_DIR"])
    except (FileNotFoundError, ValueError):
        abort(404)
    extension = PurePosixPath(relative_path).suffix.lower().lstrip(".")
    response = send_file(BytesIO(body), mimetype=CONTENT_TYPES[extension], max_age=31536000)
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response
