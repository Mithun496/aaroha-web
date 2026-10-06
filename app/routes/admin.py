from datetime import datetime, timezone
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)

from werkzeug.security import check_password_hash

from app.extensions import db, limiter
from app.models.guide import GuideApplication
from app.models.platform import AuditLog, PaymentTransaction
from app.services.payment import PaymentError, refund_payment
from app.services.storage import get_private_file, get_private_file_bytes


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin"
)


# =========================================================
# ADMIN AUTHENTICATION DECORATOR
# =========================================================

def admin_required(view_function):

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):

        if not session.get("admin_authenticated"):

            return redirect(
                url_for("admin.login")
            )

        return view_function(
            *args,
            **kwargs
        )

    return wrapped_view


def audit(action, object_type, object_id, metadata=None):
    db.session.add(AuditLog(
        actor_email=session.get("admin_email", "unknown"),
        action=action,
        object_type=object_type,
        object_id=object_id,
        metadata_json=metadata or {},
    ))


# =========================================================
# ADMIN LOGIN
# =========================================================

@admin_bp.route(
    "/login",
    methods=["GET", "POST"]
)
@limiter.limit("5 per minute")
def login():

    if session.get("admin_authenticated"):

        return redirect(
            url_for("admin.dashboard")
        )

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        # ---------------------------------------------
        # Development admin credentials
        #
        # These will come from environment variables.
        # ---------------------------------------------

        import os

        admin_email = os.getenv(
            "ADMIN_EMAIL",
            ""
        ).strip().lower()

        admin_password_hash = os.getenv(
            "ADMIN_PASSWORD_HASH",
            ""
        )

        if (
            email == admin_email
            and admin_password_hash
            and check_password_hash(
                admin_password_hash,
                password
            )
        ):
            session.clear()
            session["admin_authenticated"] = True

            session["admin_email"] = email

            return redirect(
                url_for("admin.dashboard")
            )

        return render_template(
            "admin/login.html",
            error="Invalid administrator credentials."
        )

    return render_template(
        "admin/login.html"
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@admin_bp.route("/logout", methods=["GET", "POST"])
def logout():
    if not session.get("admin_authenticated"):
        return redirect(url_for("admin.login"))
    if request.method == "GET":
        return render_template("admin/logout.html")

    session.clear()

    return redirect(
        url_for("admin.login")
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@admin_bp.route(
    "/dashboard"
)
@admin_required
def dashboard():

    total_guides = (
        db.session.query(
            GuideApplication
        ).count()
    )

    pending_guides = (
        db.session.query(
            GuideApplication
        )
        .filter(
            GuideApplication.status == "pending"
        )
        .count()
    )

    approved_guides = (
        db.session.query(
            GuideApplication
        )
        .filter(
            GuideApplication.status == "approved"
        )
        .count()
    )

    rejected_guides = (
        db.session.query(
            GuideApplication
        )
        .filter(
            GuideApplication.status == "rejected"
        )
        .count()
    )

    needs_changes_guides = (
        db.session.query(
            GuideApplication
        )
        .filter(
            GuideApplication.status == "needs_changes"
        )
        .count()
    )

    recent_applications = (
        GuideApplication.query
        .order_by(
            GuideApplication.created_at.desc()
        )
        .limit(10)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        total_guides=total_guides,
        pending_guides=pending_guides,
        approved_guides=approved_guides,
        rejected_guides=rejected_guides,
        needs_changes_guides=needs_changes_guides,
        recent_applications=recent_applications,
    )

# =========================================================
# GUIDE APPLICATION DETAILS
# =========================================================

@admin_bp.route(
    "/guide/<int:application_id>",
    methods=["GET"]
)
@admin_required
def guide_application(application_id):

    application = (
        GuideApplication.query
        .filter_by(id=application_id)
        .first_or_404()
    )

    return render_template(
        "admin/guide_application.html",
        application=application,
    )

    # =========================================================
# GUIDE APPLICATION DECISION
# =========================================================

@admin_bp.route(
    "/guide/<int:application_id>/decision",
    methods=["POST"]
)
@admin_required
def guide_application_decision(application_id):

    application = (
        GuideApplication.query
        .filter_by(id=application_id)
        .first_or_404()
    )

    action = request.form.get(
        "action",
        ""
    ).strip().lower()

    allowed_actions = {
        "approve": "approved",
        "changes": "needs_changes",
        "reject": "rejected",
    }

    if action not in allowed_actions:

        flash(
            "Invalid application decision.",
            "error"
        )

        return redirect(
            url_for(
                "admin.guide_application",
                application_id=application.id
            )
        )

    # Only applications that are awaiting review
    # should receive a final decision.
    if application.status not in [
        "pending",
        "under_review",
        "needs_changes",
    ]:

        flash(
            "This application cannot be changed in its current status.",
            "error"
        )

        return redirect(
            url_for(
                "admin.guide_application",
                application_id=application.id
            )
        )

    application.status = allowed_actions[action]

    application.reviewed_at = datetime.now(timezone.utc)
    audit("guide_application_decision", "guide_application", application.id, {"decision": action})

    try:

        db.session.commit()

    except Exception as error:

        db.session.rollback()

        print(
            "GUIDE DECISION DATABASE ERROR:",
            error
        )

        flash(
            "Unable to update the application.",
            "error"
        )

        return redirect(
            url_for(
                "admin.guide_application",
                application_id=application.id
            )
        )

    messages = {
        "approve": "Guide application approved.",
        "changes": "Guide application marked as needing changes.",
        "reject": "Guide application rejected.",
    }

    flash(
        messages[action],
        "success"
    )

    return redirect(
        url_for(
            "admin.guide_application",
            application_id=application.id
        )
    )
# =========================================================
# OTHER PARTNER APPLICATIONS
# =========================================================

@admin_bp.route("/partners")
@admin_required
def partner_applications():
    from app.models.platform import PartnerApplication
    applications = PartnerApplication.query.order_by(PartnerApplication.created_at.desc()).limit(50).all()
    return render_template("admin/partner_applications.html", applications=applications)


@admin_bp.route("/partner/<int:application_id>")
@admin_required
def partner_application(application_id):
    from app.models.platform import PartnerApplication
    application = PartnerApplication.query.filter_by(id=application_id).first_or_404()
    return render_template("admin/partner_application.html", application=application)


@admin_bp.route("/partner/<int:application_id>/decision", methods=["POST"])
@admin_required
def partner_application_decision(application_id):
    from app.models.platform import AutoCaptain, CoracleOperator, PartnerApplication, RentalPartner, ResortListing
    application = PartnerApplication.query.filter_by(id=application_id).first_or_404()
    action = request.form.get("action", "").strip().lower()
    mapping = {"approve": "approved", "changes": "needs_changes", "reject": "rejected"}
    if action not in mapping:
        flash("Invalid partner decision.", "error")
        return redirect(url_for("admin.partner_application", application_id=application.id))
    if application.status not in {"pending", "needs_changes"}:
        flash("This application cannot be changed in its current status.", "error")
        return redirect(url_for("admin.partner_application", application_id=application.id))
    application.status = mapping[action]
    application.reviewed_at = datetime.now(timezone.utc)
    audit("partner_application_decision", "partner_application", application.id, {"decision": action, "category": application.category})
    if action == "approve":
        if application.category == "bike_rental":
            partner = RentalPartner.query.filter_by(phone_number=application.phone_number).first()
            if partner is None:
                partner = RentalPartner(
                    phone_number=application.phone_number,
                    owner_name=application.owner_name,
                    business_name=application.business_name,
                    location=application.location,
                    whatsapp=application.whatsapp or application.phone_number,
                    description=application.description,
                    status="approved",
                )
                db.session.add(partner)
                db.session.flush()
        elif application.category == "resort_owner":
            listing = ResortListing.query.filter_by(provider_phone=application.phone_number).first()
            if listing is None:
                listing = ResortListing(
                    provider_phone=application.phone_number,
                    provider_id=application.id,
                    name=application.business_name,
                    description=application.description or "Resort listing approved by admin.",
                    address=application.location,
                    contact=application.whatsapp or application.phone_number,
                    whatsapp=application.whatsapp,
                    amenities=application.details.get("amenities", []).splitlines() if isinstance(application.details.get("amenities"), str) else [],
                    room_info=application.details.get("room_types", []).splitlines() if isinstance(application.details.get("room_types"), str) else [],
                    photos=[line.strip() for line in str(application.details.get("photos", "")).splitlines() if line.strip()],
                    status="approved",
                )
                db.session.add(listing)
        elif application.category == "auto_driver":
            captain = AutoCaptain.query.filter_by(phone_number=application.phone_number).first()
            if captain is None:
                captain = AutoCaptain(
                    phone_number=application.phone_number,
                    owner_name=application.owner_name,
                    full_name=application.owner_name,
                    location=application.location,
                    vehicle_number=application.details.get("vehicle_number", ""),
                    vehicle_type=application.details.get("vehicle_type", ""),
                    status="approved",
                    is_online=True,
                )
                db.session.add(captain)
        elif application.category == "coracle_operator":
            operator = CoracleOperator.query.filter_by(phone_number=application.phone_number).first()
            if operator is None:
                operator = CoracleOperator(
                    phone_number=application.phone_number,
                    business_name=application.business_name,
                    location=application.location,
                    boat_capacity=int(application.details.get("boat_capacity", 0) or 0),
                    price=0.0,
                    status="approved",
                )
                db.session.add(operator)
    db.session.commit()
    flash("Partner application updated.", "success")
    return redirect(url_for("admin.partner_application", application_id=application.id))


@admin_bp.route("/audit-logs")
@admin_required
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin/audit_logs.html", logs=logs)


@admin_bp.route("/operations")
@admin_required
def operations():
    from app.models.destination import Destination
    from app.models.platform import (
        AutoCaptain,
        BikeVehicle,
        Booking,
        CoracleOperator,
        EmergencyContact,
        Notification,
        PartnerApplication,
        PaymentTransaction,
        RentalPartner,
        ResortListing,
        Review,
        SOSIncident,
        TravelerProfile,
    )
    from app.models.user import User

    def display(value):
        if value is None or value == "":
            return "—"
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d %H:%M UTC")
        return str(value)

    def section(title, headers, model, fields):
        records = model.query.order_by(model.created_at.desc()).limit(50).all()
        return {
            "title": title,
            "headers": headers,
            "rows": [[display(getattr(record, field)) for field in fields] for record in records],
        }

    datasets = [
        section("Users", ["ID", "Phone", "Role", "Status", "Created"], User, ["id", "phone_number", "role", "is_active", "created_at"]),
        section("Traveler profiles", ["ID", "Phone", "Name", "Country", "Created"], TravelerProfile, ["id", "phone_number", "first_name", "country", "created_at"]),
        section("Destinations", ["ID", "Name", "Slug", "Published", "Updated"], Destination, ["id", "name", "slug", "is_published", "updated_at"]),
        section("Bookings", ["ID", "Reference", "Traveler", "Provider", "Type", "Status", "Payment", "Created"], Booking, ["id", "booking_reference", "traveler_phone", "provider_name", "booking_type", "status", "payment_status", "created_at"]),
        section("Guide applications", ["ID", "Guide", "Phone", "Status", "Submitted"], GuideApplication, ["id", "first_name", "phone_number", "status", "submitted_at"]),
        section("Partner applications", ["ID", "Business", "Phone", "Category", "Status", "Submitted"], PartnerApplication, ["id", "business_name", "phone_number", "category", "status", "submitted_at"]),
        section("Rental partners", ["ID", "Business", "Phone", "Status", "Created"], RentalPartner, ["id", "business_name", "phone_number", "status", "created_at"]),
        section("Bike vehicles", ["ID", "Vehicle", "Provider ID", "Active", "Updated"], BikeVehicle, ["id", "name", "provider_id", "is_active", "updated_at"]),
        section("Resorts", ["ID", "Name", "Provider phone", "Status", "Updated"], ResortListing, ["id", "name", "provider_phone", "status", "updated_at"]),
        section("Auto captains", ["ID", "Name", "Phone", "Status", "Online", "Updated"], AutoCaptain, ["id", "full_name", "phone_number", "status", "is_online", "updated_at"]),
        section("Coracle operators", ["ID", "Business", "Phone", "Capacity", "Status", "Updated"], CoracleOperator, ["id", "business_name", "phone_number", "boat_capacity", "status", "updated_at"]),
        section("SOS incidents", ["ID", "Traveler", "Mode", "Status", "Location text", "Created"], SOSIncident, ["id", "traveler_phone", "mode", "status", "location_text", "created_at"]),
        section("Reviews", ["ID", "Booking ID", "Traveler", "Provider ID", "Rating", "Review", "Created"], Review, ["id", "booking_id", "traveler_phone", "provider_id", "rating", "text", "created_at"]),
        section("Notifications", ["ID", "Recipient", "Type", "Title", "Message", "Read", "Created"], Notification, ["id", "recipient_phone", "notification_type", "title", "message", "is_read", "created_at"]),
        section("Payment transactions", ["ID", "Booking reference", "Amount", "Currency", "Payment reference", "Status", "Refund status", "Created"], PaymentTransaction, ["id", "booking_reference", "amount", "currency", "gateway_reference", "status", "refund_status", "created_at"]),
        section("Emergency contacts", ["ID", "Traveler", "Contact", "Phone", "Relationship", "Created"], EmergencyContact, ["id", "user_phone", "name", "phone", "relationship", "created_at"]),
        section("Audit logs", ["ID", "Actor", "Action", "Object", "Created"], AuditLog, ["id", "actor_email", "action", "object_type", "created_at"]),
    ]
    return render_template("admin/operations.html", datasets=datasets)


@admin_bp.route("/payments/<int:transaction_id>/refund", methods=["POST"])
@admin_required
def refund_payment_action(transaction_id):
    transaction = db.session.get(PaymentTransaction, transaction_id)
    if transaction is None:
        return render_template("errors/404.html"), 404
    try:
        before_status = transaction.refund_status
        refund_payment(transaction, session.get("admin_email", "unknown"))
        if before_status:
            flash("A refund is already in progress or has been completed.", "info")
        else:
            flash("Refund submitted to the configured payment provider.", "success")
    except PaymentError as error:
        flash(str(error), "error")
    return redirect(url_for("admin.operations"))


@admin_bp.route("/private-file/<path:relative_path>")
@admin_required
def private_file(relative_path):
    from flask import send_file
    from io import BytesIO
    from pathlib import PurePosixPath

    try:
        if current_app.config.get("STORAGE_PROVIDER") == "s3":
            response = send_file(
                BytesIO(get_private_file_bytes(relative_path, current_app.config["UPLOAD_DIR"])),
                download_name="private-file",
                as_attachment=True,
            )
        else:
            path = get_private_file(relative_path, current_app.config["UPLOAD_DIR"])
            response = send_file(path, download_name=PurePosixPath(relative_path).name, as_attachment=True)
    except (FileNotFoundError, ValueError, RuntimeError):
        return render_template("errors/404.html"), 404
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    return response
