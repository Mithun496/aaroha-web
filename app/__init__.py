import os

import click
from flask import Flask, jsonify, render_template, request, session
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from app.extensions import csrf, db, limiter

migrate = Migrate()


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    from app.routes.admin import admin_bp
    from app.routes.auth import auth_bp
    from app.routes.home import home_bp
    from app.routes.partner import partner_bp
    from app.routes.non_guide_partner import partner_onboarding_bp
    from app.routes.traveler import traveler_bp
    from app.routes.health import health_bp
    from app.routes.marketplace import marketplace_bp
    from app.routes.media import media_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(partner_bp)
    app.register_blueprint(partner_onboarding_bp)
    app.register_blueprint(traveler_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(media_bp)

    from app.models import AuditLog, Booking, Destination, DestinationImage, GuideApplication, Notification, PartnerApplication, PaymentTransaction, PaymentWebhookEvent, Review, SOSIncident, TravelerProfile, User  # noqa: F401

    @app.cli.command("seed-destinations")
    def seed_destinations_command():
        from app.services.seed import seed_destinations

        count = seed_destinations()
        click.echo(f"Seeded {count} destinations.")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        from app.services.seed import seed_demo_data

        count = seed_demo_data()
        click.echo(f"Created or retained {count} demo records. No customer reviews were seeded.")

    with app.app_context():
        app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
        app.config["AUTO_CREATE_TABLES"] = os.getenv("AUTO_CREATE_TABLES", "false").strip().lower() in {"1", "true", "yes", "on"}
        if app.config.get("AUTO_CREATE_TABLES") and app.config["ENVIRONMENT"] != "production":
            db.create_all()

    @app.context_processor
    def inject_notification_context():
        unread_count = 0
        if session.get("authenticated") and session.get("account_type") == "traveler":
            unread_count = Notification.query.filter_by(recipient_phone=session.get("phone_number"), is_read=False).count()
        return {"notification_unread_count": unread_count}

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(self), microphone=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; object-src 'none'; "
            "frame-ancestors 'self'; form-action 'self'; "
            "img-src 'self' data: https:; font-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https:; "
            "script-src 'self' 'unsafe-inline' https://checkout.razorpay.com https://api.razorpay.com; "
            "connect-src 'self' https:; "
            "frame-src 'self' https://api.razorpay.com https://checkout.razorpay.com",
        )
        if app.config["ENVIRONMENT"] == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.errorhandler(404)
    def not_found(_error):
        if request.accept_mimetypes.best == "application/json":
            return jsonify({"error": "not_found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    return app
