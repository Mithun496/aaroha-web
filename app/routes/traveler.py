from datetime import date, timedelta
import json
from types import SimpleNamespace

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, Response

from app.extensions import db
from app.models.destination import Destination
from app.models.guide import GuideApplication
from app.models.platform import (
    AutoCaptain,
    BikeVehicle,
    Booking,
    CoracleOperator,
    EmergencyContact,
    PartnerApplication,
    RentalPartner,
    ResortListing,
    SOSIncident,
    TravelerProfile,
)
from app.models.platform import Review


traveler_bp = Blueprint("traveler", __name__)

def serialize_destination(destination):
    return {
        "name": destination.name,
        "slug": destination.slug,
        "region": destination.region,
        "category": destination.category,
        "description": destination.description,
        "rules": destination.rules or [],
        "opening": destination.opening_hours or "Opening details are shared locally before the visit.",
        "highlights": destination.highlights or [],
        "latitude": destination.latitude,
        "longitude": destination.longitude,
        "cultural_info": destination.cultural_info,
        "safety_info": destination.safety_info,
    }


def current_phone():
    return session.get("phone_number")


def _booking_dates(start_date, duration_days):
    return {start_date + timedelta(days=offset) for offset in range(max(1, duration_days))}


def _service_is_available(booking_type, service_id, start_date, duration_days):
    requested_dates = _booking_dates(start_date, duration_days)
    existing = Booking.query.filter(
        Booking.booking_type == booking_type,
        Booking.service_id == service_id,
        Booking.status.in_(["pending", "confirmed"]),
    ).all()
    return not any(
        requested_dates.intersection(_booking_dates(booking.booking_date, booking.duration_days or 1))
        for booking in existing
        if booking.booking_date
    )


def traveler_required(view):
    def wrapped(*args, **kwargs):
        if not session.get("authenticated") or session.get("account_type") != "traveler":
            return redirect(url_for("auth.account_type"))
        return view(*args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


@traveler_bp.route("/explore")
def explore():
    query = Destination.query.filter_by(is_published=True)
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    if search:
        q = f"%{search}%"
        query = query.filter(
            db.or_(
                Destination.name.ilike(q),
                Destination.description.ilike(q),
                Destination.region.ilike(q),
            )
        )
    if category:
        query = query.filter(Destination.category.ilike(category))

    destinations = query.order_by(Destination.name.asc()).all()
    destination_map = {destination.slug: serialize_destination(destination) for destination in destinations}
    categories = [row[0] for row in db.session.query(Destination.category).filter_by(is_published=True).distinct().order_by(Destination.category.asc()).all()]
    return render_template("traveler/explore.html", destinations=destination_map, categories=categories, search=search, selected_category=category)


@traveler_bp.route("/destination/<slug>")
def destination(slug):
    destination_entry = Destination.query.filter_by(slug=slug.lower(), is_published=True).first()
    if not destination_entry:
        return render_template("errors/404.html"), 404
    return render_template("traveler/destination.html", destination=serialize_destination(destination_entry), slug=slug)


@traveler_bp.route("/culture-guide")
def culture_guide():
    destinations = Destination.query.filter_by(is_published=True).order_by(Destination.name.asc()).all()
    return render_template("traveler/culture.html", destinations={item.slug: serialize_destination(item) for item in destinations})


@traveler_bp.route("/trip-planner", methods=["GET", "POST"])
def trip_planner():
    result = None
    if request.method == "POST":
        raw_interests = request.form.getlist("interests")
        interests = raw_interests or ["history"]
        try:
            days = max(1, min(14, float(request.form.get("days", "2.5"))))
        except ValueError:
            days = 2.5
        try:
            budget = max(1000, float(request.form.get("budget", "15000")))
        except ValueError:
            budget = 15000

        slots = [
            ("09:00", "Heritage start", "Virupaksha Temple"),
            ("11:00", "Local context", "Hampi heritage walk with a local guide"),
            ("13:00", "Lunch", "Local Karnataka meal"),
            ("15:00", "Monument visit", "Vijaya Vittala Temple"),
            ("17:30", "Sunset", "Hemakuta Hill or a safe viewpoint"),
            ("19:00", "Dinner", "Local restaurant or resort dining"),
        ]
        if "nature" in interests or "photography" in interests:
            slots[4] = ("17:30", "Golden hour", "Sanapur Lake / nearby viewpoint")
        if "spiritual" in interests:
            slots[0] = ("08:30", "Temple visit", "Virupaksha Temple")
        if "food" in interests:
            slots[2] = ("13:00", "Local food stop", "Regional thali and local specialties")

        day_count = int(days) + (1 if days % 1 else 0)
        itinerary_days = []
        for idx in range(day_count):
            itinerary_days.append({
                "day": idx + 1,
                "title": "Heritage & local life" if idx == 0 else "Explore beyond the core",
                "items": slots if idx == 0 else [
                    ("08:30", "Morning", "Anegundi village or Kamalapura"),
                    ("11:30", "Culture", "Museum / heritage interpretation"),
                    ("13:30", "Lunch", "Local meal"),
                    ("16:00", "Riverside / nature", "Tungabhadra area, subject to conditions"),
                    ("18:00", "Sunset", "Choose a safe, permitted viewpoint"),
                ],
            })
        result = {
            "days": days,
            "budget": budget,
            "interests": interests,
            "itinerary_days": itinerary_days,
            "notes": [
                "This planner is a deterministic MVP and does not yet fetch live traffic, opening hours or weather.",
                "Always confirm monument hours and local conditions before a timed visit.",
            ],
        }
    return render_template("traveler/trip_planner.html", result=result)


@traveler_bp.route("/guides")
def guides():
    guides = GuideApplication.query.filter_by(status="approved").order_by(GuideApplication.first_name.asc()).all()
    rating_rows = (
        db.session.query(Review.provider_id, db.func.avg(Review.rating), db.func.count(Review.id))
        .join(Booking, Review.booking_id == Booking.id)
        .filter(Booking.booking_type == "guide")
        .group_by(Review.provider_id)
        .all()
    )
    ratings = {provider_id: {"average": round(float(average), 1), "count": count} for provider_id, average, count in rating_rows}
    return render_template("traveler/guides.html", guides=guides, ratings=ratings)


@traveler_bp.route("/bikes")
def bikes():
    rental_partners = RentalPartner.query.filter_by(status="approved").order_by(RentalPartner.business_name.asc()).all()
    fallback_partners = PartnerApplication.query.filter_by(category="bike_rental", status="approved").order_by(PartnerApplication.business_name.asc()).all()
    if rental_partners:
        partners = rental_partners
    else:
        partners = []
        for application in fallback_partners:
            partners.append(
                SimpleNamespace(
                    business_name=application.business_name,
                    owner_name=application.owner_name,
                    location=application.location,
                    vehicles=[
                        SimpleNamespace(
                            id=application.id,
                            name=application.business_name,
                            vehicle_type="Bike",
                            location=application.location,
                            price=900.0,
                        )
                    ],
                )
            )
    return render_template("traveler/bikes.html", partners=partners)


@traveler_bp.route("/bikes/<int:vehicle_id>", methods=["GET", "POST"])
def bike_detail(vehicle_id):
    vehicle = BikeVehicle.query.filter_by(id=vehicle_id, is_active=True).first()
    if vehicle is None:
        partner_application = PartnerApplication.query.filter_by(id=vehicle_id, category="bike_rental", status="approved").first()
        if partner_application is None:
            return render_template("errors/404.html"), 404
        return render_template("traveler/bike_detail.html", vehicle=None, partner=partner_application, min_date=date.today().isoformat())

    partner = RentalPartner.query.filter_by(id=vehicle.provider_id, status="approved").first()
    if request.method == "POST":
        if not session.get("authenticated") or session.get("account_type") != "traveler":
            return redirect(url_for("auth.account_type"))
        booking_date_raw = request.form.get("booking_date", "").strip()
        try:
            booking_date = date.fromisoformat(booking_date_raw)
        except ValueError:
            flash("Please choose a valid booking date.", "error")
            return render_template("traveler/bike_detail.html", vehicle=vehicle, partner=partner, min_date=date.today().isoformat())
        duration = request.form.get("duration_days", "1").strip()
        try:
            duration_days = int(duration)
        except ValueError:
            duration_days = 0
        if not 1 <= duration_days <= 30:
            flash("Bike bookings must be between 1 and 30 days.", "error")
            return render_template("traveler/bike_detail.html", vehicle=vehicle, partner=partner, min_date=date.today().isoformat())
        if booking_date < date.today():
            flash("Please choose a future booking date.", "error")
            return render_template("traveler/bike_detail.html", vehicle=vehicle, partner=partner, min_date=date.today().isoformat())
        if not _service_is_available("bike", vehicle.id, booking_date, duration_days):
            flash("This vehicle is already requested for part of those dates.", "error")
            return render_template("traveler/bike_detail.html", vehicle=vehicle, partner=partner, min_date=date.today().isoformat())
        booking = Booking(
            traveler_phone=current_phone() or "",
            booking_type="bike",
            provider_id=vehicle.provider_id,
            service_id=vehicle.id,
            provider_name=partner.business_name if partner else vehicle.name,
            destination=vehicle.location,
            booking_date=booking_date,
            booking_time=request.form.get("booking_time", "").strip(),
            duration_days=duration_days,
            guests=max(1, min(4, request.form.get("guests", type=int) or 1)),
            message=request.form.get("message", "").strip(),
            amount=round(float(vehicle.price) * duration_days, 2),
            currency="INR",
            payment_status="unpaid",
            status="pending",
        )
        db.session.add(booking)
        db.session.commit()
        flash("Your bike booking request has been sent.", "success")
        return redirect(url_for("traveler.bookings"))

    return render_template("traveler/bike_detail.html", vehicle=vehicle, partner=partner, min_date=date.today().isoformat())


@traveler_bp.route("/stays")
def stays():
    resorts = ResortListing.query.filter_by(status="approved").order_by(ResortListing.name.asc()).all()
    if not resorts:
        resorts = PartnerApplication.query.filter_by(category="resort_owner", status="approved").order_by(PartnerApplication.business_name.asc()).all()
    return render_template("traveler/resorts.html", resorts=resorts)


@traveler_bp.route("/stays/<int:resort_id>")
def resort_detail(resort_id):
    resort = ResortListing.query.filter_by(id=resort_id, status="approved").first()
    if resort is None:
        resort = PartnerApplication.query.filter_by(id=resort_id, category="resort_owner", status="approved").first()
    if resort is None:
        return render_template("errors/404.html"), 404
    return render_template("traveler/resort_detail.html", resort=resort)


@traveler_bp.route("/services")
def services():
    total_guides = GuideApplication.query.filter_by(status="approved").count()
    total_bikes = RentalPartner.query.filter_by(status="approved").count() or PartnerApplication.query.filter_by(category="bike_rental", status="approved").count()
    total_resorts = ResortListing.query.filter_by(status="approved").count() or PartnerApplication.query.filter_by(category="resort_owner", status="approved").count()
    total_auto = AutoCaptain.query.filter_by(status="approved").count()
    total_coracle = CoracleOperator.query.filter_by(status="approved").count()
    return render_template(
        "traveler/service_discovery.html",
        total_guides=total_guides,
        total_bikes=total_bikes,
        total_resorts=total_resorts,
        total_auto=total_auto,
        total_coracle=total_coracle,
    )


@traveler_bp.route("/guides/<int:guide_id>", methods=["GET", "POST"])
def guide_detail(guide_id):
    guide = GuideApplication.query.filter_by(id=guide_id, status="approved").first_or_404()
    reviews = Review.query.join(Booking, Review.booking_id == Booking.id).filter(
        Review.provider_id == guide.id,
        Booking.booking_type == "guide",
    ).order_by(Review.created_at.desc()).all()
    rating_values = [review.rating for review in reviews]
    average_rating = (sum(rating_values) / len(rating_values)) if rating_values else 0
    rating_summary = {
        "count": len(reviews),
        "average": round(average_rating, 1) if rating_values else 0,
        "stars": [
            min(5, max(0, round(average_rating))),
        ],
    }
    if request.method == "POST":
        if not session.get("authenticated") or session.get("account_type") != "traveler":
            return redirect(url_for("auth.account_type"))
        booking_date_raw = request.form.get("booking_date", "").strip()
        try:
            booking_date = date.fromisoformat(booking_date_raw)
        except ValueError:
            flash("Please choose a valid booking date.", "error")
            return render_template("traveler/guide_detail.html", guide=guide, reviews=reviews, rating_summary=rating_summary, min_date=date.today().isoformat())
        guests = request.form.get("guests", "1")
        try:
            guests = max(1, int(guests))
        except ValueError:
            guests = 1
        if guide.max_group_size and guests > int(guide.max_group_size):
            flash("The selected group is larger than this guide's maximum group size.", "error")
            return render_template("traveler/guide_detail.html", guide=guide, reviews=reviews, rating_summary=rating_summary)
        duration = request.form.get("duration", "hourly").strip()
        if booking_date < date.today():
            flash("Please choose a future booking date.", "error")
            return render_template("traveler/guide_detail.html", guide=guide, reviews=reviews, rating_summary=rating_summary, min_date=date.today().isoformat())
        if guide.minimum_booking_notice and booking_date < date.today() + timedelta(days=guide.minimum_booking_notice):
            flash("This guide requires more advance notice for bookings.", "error")
            return render_template("traveler/guide_detail.html", guide=guide, reviews=reviews, rating_summary=rating_summary, min_date=date.today().isoformat())
        if not _service_is_available("guide", guide.id, booking_date, 1):
            flash("This guide is already booked for that date.", "error")
            return render_template("traveler/guide_detail.html", guide=guide, reviews=reviews, rating_summary=rating_summary, min_date=date.today().isoformat())
        amount = {
            "full_day": guide.full_day_rate,
            "half_day": guide.half_day_rate,
        }.get(duration, guide.hourly_rate)
        if amount is None:
            flash("This guide has no price configured for the selected duration.", "error")
            return render_template("traveler/guide_detail.html", guide=guide, reviews=reviews, rating_summary=rating_summary, min_date=date.today().isoformat())
        booking = Booking(
            traveler_phone=current_phone() or "",
            booking_type="guide",
            provider_id=guide.id,
            service_id=guide.id,
            provider_name=f"{guide.first_name} {guide.last_name}",
            destination=guide.location,
            booking_date=booking_date,
            booking_time=request.form.get("booking_time", "").strip(),
            guests=guests,
            message=request.form.get("message", "").strip(),
            duration_days=1,
            amount=amount,
            currency="INR",
            payment_status="unpaid",
            status="pending",
        )
        db.session.add(booking)
        db.session.commit()
        flash("Your guide booking request has been sent.", "success")
        return redirect(url_for("traveler.bookings"))
    return render_template("traveler/guide_detail.html", guide=guide, reviews=reviews, rating_summary=rating_summary, min_date=date.today().isoformat())


@traveler_bp.route("/bookings")
@traveler_required
def bookings():
    rows = Booking.query.filter_by(traveler_phone=current_phone()).order_by(Booking.created_at.desc()).all()
    return render_template("traveler/bookings.html", bookings=rows)


@traveler_bp.route("/profile")
@traveler_required
def profile():
    profile = TravelerProfile.query.filter_by(phone_number=current_phone()).first()
    return render_template("traveler/profile.html", profile=profile)


@traveler_bp.route("/offline")
def offline():
    return render_template("traveler/offline.html")


@traveler_bp.route("/offline/hampi.json")
def offline_hampi():
    destination_entry = Destination.query.filter_by(slug="hampi", is_published=True).first()
    payload = {
        "name": "AAROHA Hampi Offline Pack",
        "version": 1,
        "destination": serialize_destination(destination_entry) if destination_entry else {
            "name": "Hampi",
            "region": "Karnataka",
            "description": "Hampi heritage region.",
            "rules": [],
            "opening": "Opening details vary locally.",
            "highlights": [],
        },
        "emergency_numbers": {
            "universal": "112",
            "tourist_assistance": "1363",
        },
        "essential": [
            "Keep a screenshot or saved copy of your accommodation confirmation.",
            "Keep your passport and important documents secure.",
            "Confirm monument hours before timed visits.",
        ],
    }
    return Response(json.dumps(payload, ensure_ascii=False, indent=2), mimetype="application/json", headers={"Content-Disposition": 'attachment; filename="aaroha-hampi-offline.json"'})


@traveler_bp.route("/sos", methods=["GET", "POST"])
@traveler_required
def sos():
    incident = SOSIncident.query.filter_by(traveler_phone=current_phone()).order_by(SOSIncident.created_at.desc()).first()
    if request.method == "POST":
        safety = request.form.get("safety_response", "yes").strip().lower()
        location_text = request.form.get("location_text", "").strip()
        if safety not in {"yes", "no"} or len(location_text) > 255:
            flash("Choose a valid safety response and keep the location under 256 characters.", "error")
            contacts = EmergencyContact.query.filter_by(user_phone=current_phone()).order_by(EmergencyContact.is_primary.desc(), EmergencyContact.name.asc()).all()
            return render_template("traveler/sos.html", incident=incident, contacts=contacts), 400
        mode = "silent" if safety == "no" else "standard"
        incident = SOSIncident(
            traveler_phone=current_phone() or "",
            safety_response=safety,
            mode=mode,
            location_text=location_text,
            status="initiated",
        )
        db.session.add(incident)
        db.session.commit()
        flash("Emergency workflow initiated. Use the contact controls below and call emergency services when needed.", "success")
    contacts = EmergencyContact.query.filter_by(user_phone=current_phone()).order_by(EmergencyContact.is_primary.desc(), EmergencyContact.name.asc()).all()
    return render_template("traveler/sos.html", incident=incident, contacts=contacts)


@traveler_bp.route("/support")
def support():
    return render_template("traveler/support.html")
