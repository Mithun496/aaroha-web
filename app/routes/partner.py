from datetime import datetime, timezone
from functools import wraps
import math

from flask import (
    Blueprint,
    flash,
    render_template,
    redirect,
    request,
    url_for,
    session,
)
from app.extensions import db
from app.models.guide import GuideApplication
from app.models.platform import BikeVehicle, Booking, RentalPartner


partner_bp = Blueprint(
    "partner",
    __name__,
    url_prefix="/partner"
)

def _current_guide_application():
    application_id = session.get("guide_application_id")
    phone = session.get("phone_number")
    if application_id and phone:
        application = GuideApplication.query.filter_by(id=application_id, phone_number=phone).first()
        if application:
            return application
    if phone:
        return GuideApplication.query.filter_by(phone_number=phone).order_by(GuideApplication.id.desc()).first()
    return None


def _current_rental_partner():
    phone = session.get("phone_number")
    if not phone:
        return None
    return RentalPartner.query.filter_by(phone_number=phone, status="approved").order_by(RentalPartner.id.desc()).first()



# =========================================================
# PARTNER AUTHENTICATION
# =========================================================

def partner_required(view_function):

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):

        if not session.get("authenticated"):
            return redirect(
                url_for("auth.account_type")
            )

        if session.get("account_type") != "partner":
            return redirect(
                url_for("home.index")
            )

        return view_function(
            *args,
            **kwargs
        )

    return wrapped_view


# =========================================================
# GUIDE DASHBOARD
# =========================================================

@partner_bp.route(
    "/dashboard",
    methods=["GET"]
)
@partner_required
def dashboard():

    if session.get("partner_category") == "bike_rental":
        partner = _current_rental_partner()
        if partner is None:
            return redirect(url_for("auth.partner_category"))
        vehicles = BikeVehicle.query.filter_by(provider_id=partner.id).order_by(BikeVehicle.name.asc()).all()
        vehicle_ids = [vehicle.id for vehicle in vehicles]
        bookings = []
        if vehicle_ids:
            bookings = (
                Booking.query
                .filter(
                    Booking.booking_type == "bike",
                    Booking.provider_id == partner.id,
                    Booking.service_id.in_(vehicle_ids),
                )
                .order_by(Booking.booking_date.is_(None), Booking.booking_date.asc(), Booking.created_at.desc())
                .all()
            )
        return render_template("partner/bike_dashboard.html", partner=partner, vehicles=vehicles, bookings=bookings)

    if session.get("partner_category") != "guide":
        return redirect(
            url_for("auth.partner_category")
        )

    application = _current_guide_application()

    if not application:
        return redirect(
            url_for(
                "auth.guide_application_status"
            )
        )

    # Only approved guides can access
    # the active partner dashboard.
    if application.status != "approved":

        return redirect(
            url_for(
                "auth.guide_application_status"
            )
        )

    bookings = (
        Booking.query
        .filter_by(provider_id=application.id, booking_type="guide")
        .order_by(Booking.booking_date.is_(None), Booking.booking_date.asc(), Booking.created_at.desc())
        .all()
    )

    return render_template(
        "partner/dashboard.html",
        application=application,
        bookings=bookings,
    )


@partner_bp.route("/bike/vehicles", methods=["GET", "POST"])
@partner_required
def bike_vehicles():
    if session.get("partner_category") != "bike_rental":
        return redirect(url_for("auth.partner_category"))

    partner = _current_rental_partner()
    if partner is None:
        return redirect(url_for("auth.partner_category"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        vehicle_type = request.form.get("vehicle_type", "").strip()
        location = request.form.get("location", "").strip()
        price = request.form.get("price", "0").strip()
        if not name or not vehicle_type or not location:
            flash("Vehicle name, type and pickup location are required.", "error")
            return redirect(url_for("partner.bike_vehicles"))
        try:
            rental_price = float(price)
        except ValueError:
            flash("Enter a valid vehicle price.", "error")
            return redirect(url_for("partner.bike_vehicles"))
        if not math.isfinite(rental_price) or rental_price < 0:
            flash("Vehicle price must be a non-negative number.", "error")
            return redirect(url_for("partner.bike_vehicles"))
        vehicle = BikeVehicle(
            provider_id=partner.id,
            name=name,
            vehicle_type=vehicle_type,
            registration_number=request.form.get("registration_number", "").strip(),
            location=location,
            price=rental_price,
            pricing_unit=request.form.get("pricing_unit", "day").strip() or "day",
            is_active=True,
        )
        db.session.add(vehicle)
        db.session.commit()
        flash("Vehicle added to your rental fleet.", "success")
        return redirect(url_for("partner.dashboard"))

    vehicles = BikeVehicle.query.filter_by(provider_id=partner.id).order_by(BikeVehicle.name.asc()).all()
    return render_template("partner/bike_vehicles.html", partner=partner, vehicles=vehicles)


@partner_bp.route("/bike/bookings/<int:booking_id>/decision", methods=["POST"])
@partner_required
def bike_booking_decision(booking_id):
    if session.get("partner_category") != "bike_rental":
        return redirect(url_for("auth.partner_category"))

    partner = _current_rental_partner()
    if partner is None:
        return redirect(url_for("auth.partner_category"))

    booking = Booking.query.filter_by(id=booking_id, booking_type="bike", provider_id=partner.id).first_or_404()
    vehicle = BikeVehicle.query.filter_by(provider_id=partner.id, id=booking.service_id).first()
    if vehicle is None:
        flash("This booking does not belong to your fleet.", "error")
        return redirect(url_for("partner.dashboard"))

    action = request.form.get("action", "").strip().lower()
    mapping = {"accept": "confirmed", "confirm": "confirmed", "reject": "cancelled", "decline": "cancelled"}
    if action not in mapping:
        flash("Choose a valid booking action.", "error")
        return redirect(url_for("partner.dashboard"))

    allowed_next_statuses = {
        "pending": {"confirmed", "cancelled"},
    }
    if mapping[action] not in allowed_next_statuses.get(booking.status, set()):
        flash("That booking transition is not allowed.", "error")
        return redirect(url_for("partner.dashboard"))

    booking.status = mapping[action]
    booking.updated_at = datetime.now(timezone.utc)
    db.session.add(booking)
    db.session.commit()
    flash("Bike booking request updated.", "success")
    return redirect(url_for("partner.dashboard"))


@partner_bp.route(
    "/bookings/<int:booking_id>/decision",
    methods=["POST"]
)
@partner_required
def booking_decision(booking_id):

    if session.get("partner_category") != "guide":
        return redirect(
            url_for("auth.partner_category")
        )

    application = _current_guide_application()
    if not application:
        return redirect(
            url_for("auth.guide_application_status")
        )

    if application.status != "approved":
        return redirect(
            url_for("auth.guide_application_status")
        )

    booking = (
        Booking.query
        .filter_by(id=booking_id, provider_id=application.id, booking_type="guide")
        .first_or_404()
    )

    action = request.form.get("action", "").strip().lower()
    status_map = {
        "accept": "confirmed",
        "confirm": "confirmed",
        "reject": "cancelled",
        "decline": "cancelled",
        "complete": "completed",
    }

    if action not in status_map:
        flash("Choose a valid booking action.", "error")
        return redirect(url_for("partner.dashboard"))

    transitions = {
        "pending": {"confirmed", "cancelled"},
        "confirmed": {"completed", "cancelled"},
    }
    if status_map[action] not in transitions.get(booking.status, set()):
        flash("That booking transition is not allowed.", "error")
        return redirect(url_for("partner.dashboard"))

    booking.status = status_map[action]
    booking.updated_at = datetime.now(timezone.utc)
    db.session.add(booking)
    db.session.commit()

    action_label = {
        "accept": "accepted",
        "confirm": "confirmed",
        "reject": "rejected",
        "decline": "declined",
        "complete": "marked as completed",
    }

    flash(
        f"Booking request {action_label[action]}.",
        "success",
    )
    return redirect(url_for("partner.dashboard"))

# =========================================================
# GUIDE PROFILE EDIT
# =========================================================

@partner_bp.route(
    "/guide/profile/edit",
    methods=["GET", "POST"]
)
@partner_required
def edit_guide_profile():

    if session.get("partner_category") != "guide":
        return redirect(
            url_for("auth.partner_category")
        )

    application = _current_guide_application()

    if not application:
        return redirect(
            url_for("auth.guide_application_status")
        )

    if application.status != "approved":
        return redirect(
            url_for(
                "auth.guide_application_status"
            )
        )

    if request.method == "POST":

        first_name = request.form.get(
            "first_name",
            ""
        ).strip()

        last_name = request.form.get(
            "last_name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        bio = request.form.get(
            "bio",
            ""
        ).strip()

        languages = request.form.getlist(
            "languages"
        )

        if not first_name:
            return render_template(
                "partner/edit_profile.html",
                application=application,
                error="First name is required."
            )

        if not last_name:
            return render_template(
                "partner/edit_profile.html",
                application=application,
                error="Last name is required."
            )

        if not location:
            return render_template(
                "partner/edit_profile.html",
                application=application,
                error="Location is required."
            )

        if not bio:
            return render_template(
                "partner/edit_profile.html",
                application=application,
                error="Bio is required."
            )

        if not languages:
            return render_template(
                "partner/edit_profile.html",
                application=application,
                error="Select at least one language."
            )

        application.first_name = first_name
        application.last_name = last_name
        application.email = email
        application.location = location
        application.bio = bio
        application.languages = languages

        try:

            db.session.commit()

        except Exception as error:

            db.session.rollback()

            print(
                "GUIDE PROFILE UPDATE ERROR:",
                error
            )

            return render_template(
                "partner/edit_profile.html",
                application=application,
                error="Unable to save your profile right now."
            )

        # Keep the active session in sync.
        session["first_name"] = first_name
        session["last_name"] = last_name

        return redirect(
            url_for("partner.dashboard")
        )

    return render_template(
        "partner/edit_profile.html",
        application=application
    )
# =========================================================
# GUIDE SERVICES EDIT
# =========================================================

@partner_bp.route("/guide/services/edit", methods=["GET", "POST"])
@partner_required
def edit_guide_services():
    if session.get("partner_category") != "guide":
        return redirect(url_for("auth.partner_category"))

    application = _current_guide_application()
    if application is None:
        return redirect(url_for("auth.guide_application_status"))

    if application.status != "approved":
        return redirect(url_for("auth.guide_application_status"))

    if request.method == "POST":
        services = request.form.getlist("services")
        areas = request.form.getlist("areas")
        max_group_size = request.form.get("max_group_size", "").strip()
        if not services or not areas:
            return render_template("partner/edit_services.html", application=application, error="Select at least one service and one area.")
        try:
            group_size = int(max_group_size)
        except ValueError:
            return render_template("partner/edit_services.html", application=application, error="Enter a valid maximum group size.")
        if group_size < 1 or group_size > 100:
            return render_template("partner/edit_services.html", application=application, error="Maximum group size must be between 1 and 100.")
        application.services = services
        application.areas = areas
        application.max_group_size = str(group_size)
        db.session.commit()
        return redirect(url_for("partner.dashboard"))

    return render_template("partner/edit_services.html", application=application)


# =========================================================
# GUIDE PRICING EDIT
# =========================================================

@partner_bp.route("/guide/pricing/edit", methods=["GET", "POST"])
@partner_required
def edit_guide_pricing():
    if session.get("partner_category") != "guide":
        return redirect(url_for("auth.partner_category"))

    application = _current_guide_application()
    if application is None:
        return redirect(url_for("auth.guide_application_status"))
    if application.status != "approved":
        return redirect(url_for("auth.guide_application_status"))

    if request.method == "POST":
        pricing_type = request.form.get("pricing_type", "").strip()
        hourly_rate = request.form.get("hourly_rate", "").strip()
        half_day_rate = request.form.get("half_day_rate", "").strip()
        full_day_rate = request.form.get("full_day_rate", "").strip()
        pricing_group_size = request.form.get("pricing_group_size", "").strip()
        minimum_booking_notice = request.form.get("minimum_booking_notice", "").strip()

        if pricing_type not in {"per_person", "per_group"}:
            return render_template("partner/edit_pricing.html", application=application, error="Select a valid pricing model.")

        try:
            hourly = float(hourly_rate)
            half_day = float(half_day_rate)
            full_day = float(full_day_rate)
            group_size = int(pricing_group_size)
            notice = int(minimum_booking_notice)
        except ValueError:
            return render_template("partner/edit_pricing.html", application=application, error="Enter valid numeric pricing values.")

        if min(hourly, half_day, full_day) < 0 or group_size < 1 or notice < 0:
            return render_template("partner/edit_pricing.html", application=application, error="Pricing values must be zero or greater and group size must be at least 1.")

        application.pricing_type = pricing_type
        application.hourly_rate = hourly
        application.half_day_rate = half_day
        application.full_day_rate = full_day
        application.pricing_group_size = group_size
        application.minimum_booking_notice = notice
        db.session.commit()
        return redirect(url_for("partner.dashboard"))

    return render_template("partner/edit_pricing.html", application=application)


# =========================================================
# GUIDE AVAILABILITY EDIT
# =========================================================

@partner_bp.route("/guide/availability/edit", methods=["GET", "POST"])
@partner_required
def edit_guide_availability():
    if session.get("partner_category") != "guide":
        return redirect(url_for("auth.partner_category"))

    application = _current_guide_application()
    if application is None:
        return redirect(url_for("auth.guide_application_status"))
    if application.status != "approved":
        return redirect(url_for("auth.guide_application_status"))

    if request.method == "POST":
        available_days = request.form.getlist("available_days")
        time_slots = request.form.getlist("time_slots")
        booking_notice = request.form.get("booking_notice", "").strip()
        booking_mode = request.form.get("booking_mode", "request").strip()
        if not available_days or not time_slots or not booking_notice:
            return render_template("partner/edit_availability.html", application=application, error="Select available days, a time period and booking notice.")
        if booking_mode not in {"request", "instant"}:
            booking_mode = "request"
        application.available_days = available_days
        application.time_slots = time_slots
        application.booking_notice = booking_notice
        application.booking_mode = booking_mode
        db.session.commit()
        return redirect(url_for("partner.dashboard"))

    return render_template("partner/edit_availability.html", application=application)
