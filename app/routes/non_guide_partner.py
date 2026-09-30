from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.platform import PartnerApplication

partner_onboarding_bp = Blueprint("partner_onboarding", __name__, url_prefix="/auth/partner")

CATEGORY_META = {
    "bike_rental": {
        "title": "Bike Rental Partner",
        "subtitle": "List the bikes and scooters travelers can rent from you.",
        "business_label": "Rental business name",
        "details": [
            ("fleet_size", "Approximate fleet size", "number"),
            ("vehicle_types", "Vehicle types", "text"),
            ("pickup_point", "Pickup point", "text"),
        ],
    },
    "auto_driver": {
        "title": "Auto Driver Partner",
        "subtitle": "Offer local point-to-point transportation to travelers.",
        "business_label": "Name shown to travelers",
        "details": [
            ("vehicle_number", "Vehicle number", "text"),
            ("vehicle_type", "Vehicle type", "text"),
            ("service_area", "Service area", "text"),
            ("languages", "Languages you speak", "text"),
        ],
    },
    "coracle_operator": {
        "title": "Coracle Operator Partner",
        "subtitle": "List authentic coracle rides and the operating details travelers need.",
        "business_label": "Operator / business name",
        "details": [
            ("boat_capacity", "Typical passenger capacity", "number"),
            ("operating_area", "Operating area", "text"),
            ("safety_equipment", "Safety equipment available", "text"),
            ("operating_season", "Operating season / hours", "text"),
        ],
    },
    "resort_owner": {
        "title": "Resort Owner Partner",
        "subtitle": "Create a trusted resort listing. Online resort booking will be added later.",
        "business_label": "Resort name",
        "details": [
            ("whatsapp", "WhatsApp contact", "text"),
            ("amenities", "Amenities", "textarea"),
            ("menu", "Menu / dining information", "textarea"),
            ("room_types", "Room types", "textarea"),
            ("photos", "Photo links (one per line for MVP)", "textarea"),
        ],
    },
}


def allowed_category(category):
    return category in CATEGORY_META


@partner_onboarding_bp.route("/<category>", methods=["GET", "POST"])
def register(category):
    if not session.get("authenticated") or session.get("account_type") != "partner":
        return redirect(url_for("auth.account_type"))
    if not allowed_category(category):
        return redirect(url_for("auth.partner_category"))

    meta = CATEGORY_META[category]
    if request.method == "POST":
        owner_name = request.form.get("owner_name", "").strip()
        business_name = request.form.get("business_name", "").strip()
        location = request.form.get("location", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        description = request.form.get("description", "").strip()

        if not owner_name or not business_name or not location:
            return render_template("auth/partner_registration.html", meta=meta, category=category, error="Owner name, business name and location are required.")

        details = {}
        for key, _, _type in meta["details"]:
            details[key] = request.form.get(key, "").strip()

        application = PartnerApplication(
            phone_number=session.get("phone_number", ""),
            category=category,
            owner_name=owner_name,
            business_name=business_name,
            location=location,
            whatsapp=whatsapp,
            description=description,
            details=details,
            status="pending",
            submitted_at=datetime.now(timezone.utc),
        )
        db.session.add(application)
        db.session.commit()
        session["partner_application_id"] = application.id
        flash("Your partner application has been submitted for verification.", "success")
        return redirect(url_for("partner_onboarding.submitted", category=category, application_id=application.id))

    return render_template("auth/partner_registration.html", meta=meta, category=category)


@partner_onboarding_bp.route("/<category>/submitted/<int:application_id>")
def submitted(category, application_id):
    if not session.get("authenticated") or session.get("account_type") != "partner":
        return redirect(url_for("auth.account_type"))
    application = PartnerApplication.query.filter_by(id=application_id, phone_number=session.get("phone_number", "")).first_or_404()
    return render_template("auth/partner_application_submitted.html", application=application)
