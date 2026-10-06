from datetime import date, datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_wtf.csrf import generate_csrf
from sqlalchemy import and_, or_

from app.extensions import csrf, db, limiter
from app.models.platform import (
    AutoCaptain,
    Booking,
    CoracleOperator,
    EmergencyContact,
    Notification,
    PaymentTransaction,
    Review,
)
from app.services.payment import PaymentError, create_transaction, process_webhook, refund_payment, verify_transaction, verify_webhook

marketplace_bp = Blueprint("marketplace", __name__)


def traveler_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authenticated") or session.get("account_type") != "traveler":
            return redirect(url_for("auth.account_type"))
        return view(*args, **kwargs)
    return wrapped


def partner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authenticated") or session.get("account_type") != "partner":
            return redirect(url_for("auth.account_type"))
        return view(*args, **kwargs)
    return wrapped


def notify(phone, notification_type, title, message, related_type=None, related_id=None):
    if not phone:
        return
    existing = Notification.query.filter_by(
        recipient_phone=phone,
        notification_type=notification_type,
        related_type=related_type,
        related_id=related_id,
        title=title,
        message=message,
    ).first()
    if existing:
        return existing
    row = Notification(
        recipient_phone=phone,
        notification_type=notification_type,
        title=title,
        message=message,
        related_type=related_type,
        related_id=related_id,
    )
    db.session.add(row)
    return row


@marketplace_bp.route("/auto", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def auto():
    captains = AutoCaptain.query.filter_by(status="approved", is_online=True).order_by(AutoCaptain.full_name.asc()).all()
    if request.method == "POST":
        if not session.get("authenticated") or session.get("account_type") != "traveler":
            return redirect(url_for("auth.account_type"))
        captain_id = request.form.get("captain_id", type=int)
        captain = AutoCaptain.query.filter_by(id=captain_id, status="approved", is_online=True).first()
        pickup = request.form.get("pickup", "").strip()
        destination = request.form.get("destination", "").strip()
        if not captain or not pickup or not destination:
            return render_template("traveler/auto.html", captains=captains, error="Choose an available captain and enter both locations.")
        booking = Booking(
            traveler_phone=session.get("phone_number", ""),
            booking_type="auto",
            provider_id=captain.id,
            service_id=captain.id,
            provider_name=captain.full_name,
            destination=destination,
            booking_date=date.today(),
            booking_time=datetime.now(timezone.utc).strftime("%H:%M"),
            guests=1,
            message=f"Pickup: {pickup}",
            amount=0,
            currency="INR",
            payment_status="not_required",
            status="requested",
        )
        db.session.add(booking)
        db.session.flush()
        notify(captain.phone_number, "booking_created", "New auto request", f"Auto request {booking.booking_reference} needs your response.", "booking", booking.id)
        db.session.commit()
        flash("Your auto request was sent.", "success")
        return redirect(url_for("traveler.bookings"))
    return render_template("traveler/auto.html", captains=captains)


@marketplace_bp.route("/coracles", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def coracles():
    operators = CoracleOperator.query.filter_by(status="approved").order_by(CoracleOperator.business_name.asc()).all()
    if request.method == "POST":
        if not session.get("authenticated") or session.get("account_type") != "traveler":
            return redirect(url_for("auth.account_type"))
        operator_id = request.form.get("operator_id", type=int)
        operator = CoracleOperator.query.filter_by(id=operator_id, status="approved").first()
        booking_date_raw = request.form.get("booking_date", "")
        try:
            booking_date = date.fromisoformat(booking_date_raw)
            passengers = int(request.form.get("passengers", "1"))
        except (TypeError, ValueError):
            booking_date, passengers = None, 0
        if not operator or not booking_date or booking_date < date.today() or passengers < 1 or passengers > (operator.boat_capacity or 0):
            return render_template("traveler/coracles.html", operators=operators, error="Choose a future date and a passenger count within the operator capacity.")
        duplicate = Booking.query.filter_by(
            booking_type="coracle", service_id=operator.id, booking_date=booking_date,
        ).filter(Booking.status.in_(["pending", "confirmed"])).first()
        if duplicate:
            return render_template("traveler/coracles.html", operators=operators, error="This operator is already requested for that date.")
        booking = Booking(
            traveler_phone=session.get("phone_number", ""),
            booking_type="coracle",
            provider_id=operator.id,
            service_id=operator.id,
            provider_name=operator.business_name,
            destination=operator.location,
            booking_date=booking_date,
            booking_time=request.form.get("booking_time", "").strip(),
            guests=passengers,
            amount=round(operator.price * passengers, 2),
            currency="INR",
            payment_status="unpaid",
            status="pending",
        )
        db.session.add(booking)
        db.session.flush()
        notify(operator.phone_number, "booking_created", "New coracle request", f"Coracle request {booking.booking_reference} needs your response.", "booking", booking.id)
        db.session.commit()
        flash("Your coracle request was sent.", "success")
        return redirect(url_for("traveler.bookings"))
    return render_template("traveler/coracles.html", operators=operators)


@marketplace_bp.route("/partner/service-bookings")
@partner_required
def service_bookings():
    phone = session.get("phone_number")
    captain = AutoCaptain.query.filter_by(phone_number=phone, status="approved").first()
    operator = CoracleOperator.query.filter_by(phone_number=phone, status="approved").first()
    ownership = []
    if captain:
        ownership.append(and_(Booking.booking_type == "auto", Booking.provider_id == captain.id))
    if operator:
        ownership.append(and_(Booking.booking_type == "coracle", Booking.provider_id == operator.id))
    bookings = Booking.query.filter(or_(*ownership)).order_by(Booking.created_at.desc()).all() if ownership else []
    return render_template("partner/service_bookings.html", bookings=bookings)


@marketplace_bp.route("/partner/service-bookings/<int:booking_id>", methods=["POST"])
@partner_required
def service_booking_decision(booking_id):
    phone = session.get("phone_number")
    captain = AutoCaptain.query.filter_by(phone_number=phone, status="approved").first()
    operator = CoracleOperator.query.filter_by(phone_number=phone, status="approved").first()
    ownership = []
    if captain:
        ownership.append(and_(Booking.booking_type == "auto", Booking.provider_id == captain.id))
    if operator:
        ownership.append(and_(Booking.booking_type == "coracle", Booking.provider_id == operator.id))
    if not ownership:
        return Booking.query.filter_by(id=-1).first_or_404()
    booking = Booking.query.filter(Booking.id == booking_id, or_(*ownership)).first_or_404()
    action = request.form.get("action", "")
    allowed = {
        "auto": {"accept": "accepted", "arriving": "arriving", "started": "started", "complete": "completed", "cancel": "cancelled", "reject": "rejected"},
        "coracle": {"accept": "confirmed", "complete": "completed", "reject": "cancelled"},
    }
    next_status = allowed.get(booking.booking_type, {}).get(action)
    transitions = {
        "requested": {"accepted", "confirmed", "rejected", "cancelled"},
        "accepted": {"arriving", "cancelled"},
        "arriving": {"started", "cancelled"},
        "started": {"completed"},
        "pending": {"confirmed", "cancelled"},
        "confirmed": {"completed", "cancelled"},
    }
    if not next_status or next_status not in transitions.get(booking.status, set()):
        flash("That booking transition is not allowed.", "error")
        return redirect(url_for("marketplace.service_bookings"))
    booking.status = next_status
    notify(booking.traveler_phone, "booking_status", "Booking updated", f"Booking {booking.booking_reference} is now {next_status}.", "booking", booking.id)
    db.session.commit()
    return redirect(url_for("marketplace.service_bookings"))


@marketplace_bp.route("/payments/<string:booking_reference>", methods=["POST"])
@traveler_required
@limiter.limit("10 per minute")
def start_payment(booking_reference):
    booking = Booking.query.filter_by(booking_reference=booking_reference, traveler_phone=session.get("phone_number")).first_or_404()
    if booking.status not in {"pending", "confirmed"} or booking.payment_status == "paid":
        return redirect(url_for("traveler.bookings"))
    try:
        transaction = create_transaction(booking)
    except PaymentError as error:
        flash(str(error), "error")
        return redirect(url_for("traveler.bookings"))
    # In development the explicit confirmation button invokes only the mock
    # adapter; the browser never supplies a provider transaction reference.
    if transaction.status == "pending" and request.form.get("confirm_mock") == "1":
        if not verify_transaction(transaction):
            flash("Payment verification failed.", "error")
    elif transaction.status == "pending" and transaction.provider_order_id:
        return render_template(
            "traveler/payment_checkout.html",
            booking=booking,
            transaction=transaction,
            razorpay_key_id=current_app.config["RAZORPAY_KEY_ID"],
            amount_minor=int(round(float(transaction.amount) * 100)),
            csrf_value=generate_csrf(),
        )
    return redirect(url_for("traveler.bookings"))


@marketplace_bp.route("/payments/<string:booking_reference>/verify", methods=["POST"])
@traveler_required
@limiter.limit("10 per minute")
def verify_payment_callback(booking_reference):
    booking = Booking.query.filter_by(booking_reference=booking_reference, traveler_phone=session.get("phone_number")).first_or_404()
    transaction = PaymentTransaction.query.filter_by(booking_id=booking.id).first_or_404()
    if transaction.status == "paid":
        return jsonify({"paid": True}), 200
    if transaction.status not in {"pending", "failed"}:
        return jsonify({"paid": False, "error": "invalid_state"}), 409
    payment_id = request.form.get("razorpay_payment_id", "")
    order_id = request.form.get("razorpay_order_id", "")
    signature = request.form.get("razorpay_signature", "")
    try:
        verified = verify_transaction(transaction, payment_id, order_id, signature)
    except PaymentError:
        current_app.logger.exception("Payment verification request failed")
        return jsonify({"paid": False, "error": "verification_unavailable"}), 503
    if not verified:
        return jsonify({"paid": False, "error": "verification_failed"}), 400
    return jsonify({"paid": True}), 200


@marketplace_bp.route("/payments/razorpay/webhook", methods=["POST"])
@csrf.exempt
def razorpay_webhook():
    raw_body = request.get_data(cache=False)
    event_id = request.headers.get("x-razorpay-event-id", "")
    signature = request.headers.get("x-razorpay-signature", "")
    if not verify_webhook(raw_body, signature, event_id):
        return jsonify({"error": "invalid_signature"}), 401
    try:
        result = process_webhook(raw_body, event_id)
    except (ValueError, PaymentError):
        current_app.logger.exception("Razorpay webhook could not be processed")
        return jsonify({"error": "webhook_processing_failed"}), 503
    return jsonify({"status": result}), 200


@marketplace_bp.route("/reviews/<int:booking_id>", methods=["POST"])
@traveler_required
def review(booking_id):
    booking = Booking.query.filter_by(id=booking_id, traveler_phone=session.get("phone_number"), status="completed").first_or_404()
    if booking.review:
        flash("This booking already has a review.", "error")
        return redirect(url_for("traveler.bookings"))
    rating = request.form.get("rating", type=int)
    text = request.form.get("text", "").strip()
    if rating not in range(1, 6):
        flash("A rating from 1 to 5 is required.", "error")
        return redirect(url_for("traveler.bookings"))
    if len(text) < 12:
        flash("Please share at least 12 characters of feedback.", "error")
        return redirect(url_for("traveler.bookings"))
    db.session.add(Review(booking_id=booking.id, traveler_phone=booking.traveler_phone, provider_id=booking.provider_id, rating=rating, text=text))
    db.session.commit()
    notify(booking.traveler_phone, "review_submitted", "Review submitted", "Thanks for sharing your trip feedback.", "booking", booking.id)
    return redirect(url_for("traveler.bookings"))


@marketplace_bp.route("/notifications")
@traveler_required
def notifications():
    rows = Notification.query.filter_by(recipient_phone=session.get("phone_number")).order_by(Notification.created_at.desc()).all()
    return render_template("traveler/notifications.html", notifications=rows)


@marketplace_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@traveler_required
def mark_notification_read(notification_id):
    row = Notification.query.filter_by(id=notification_id, recipient_phone=session.get("phone_number")).first_or_404()
    row.is_read = True
    row.read_at = datetime.now(timezone.utc)
    db.session.commit()
    return redirect(url_for("marketplace.notifications"))


@marketplace_bp.route("/emergency-contacts", methods=["GET", "POST"])
@traveler_required
def emergency_contacts():
    phone = session.get("phone_number")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact_phone = request.form.get("phone", "").strip()
        if not name or not contact_phone:
            return render_template("traveler/emergency_contacts.html", contacts=EmergencyContact.query.filter_by(user_phone=phone).all(), error="Name and phone are required.")
        db.session.add(EmergencyContact(user_phone=phone, name=name, phone=contact_phone, relationship=request.form.get("relationship", "").strip(), is_primary=bool(request.form.get("is_primary"))))
        db.session.commit()
        return redirect(url_for("marketplace.emergency_contacts"))
    contacts = EmergencyContact.query.filter_by(user_phone=phone).order_by(EmergencyContact.is_primary.desc(), EmergencyContact.name.asc()).all()
    return render_template("traveler/emergency_contacts.html", contacts=contacts)


@marketplace_bp.route("/emergency-contacts/<int:contact_id>/delete", methods=["POST"])
@traveler_required
def delete_emergency_contact(contact_id):
    contact = EmergencyContact.query.filter_by(id=contact_id, user_phone=session.get("phone_number")).first_or_404()
    db.session.delete(contact)
    db.session.commit()
    return redirect(url_for("marketplace.emergency_contacts"))
