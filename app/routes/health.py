from flask import Blueprint, jsonify
from sqlalchemy import text

from app.extensions import db

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "database": "ok", "service": "aaroha"}), 200
    except Exception:
        return jsonify({"status": "degraded", "database": "error", "service": "aaroha"}), 503
