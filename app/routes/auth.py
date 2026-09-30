from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.otp import OTPChallenge
from app.models.platform import TravelerProfile
from app.models.user import User
from app.extensions import limiter
from app.services.otp import generate_code, normalize_phone_number, send_code, verify_code
from app.services.storage import save_private_file


auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth"
)


def _clear_temp_otp_session():
    for key in ("otp_phone", "otp_challenge_id", "dev_otp"):
        session.pop(key, None)


def _as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home.index"))


# =========================================================
# ACCOUNT TYPE
# =========================================================

@auth_bp.route(
    "/account-type",
    methods=["GET", "POST"]
)
def account_type():

    if request.method == "POST":

        account_type = request.form.get(
            "account_type"
        )

        if account_type not in [
            "traveler",
            "partner",
            "guest",
        ]:

            return render_template(
                "auth/account_type.html",
                error="Please select an account type."
            )

        session["account_type"] = account_type

        if account_type == "traveler":

            return redirect(
                url_for("auth.phone")
            )

        if account_type == "partner":

            return redirect(
                url_for("auth.phone")
            )

        if account_type == "guest":

            return redirect(
                url_for("home.index")
            )

    return render_template(
        "auth/account_type.html"
    )


# =========================================================
# PHONE
# =========================================================

@auth_bp.route(
    "/phone",
    methods=["GET", "POST"]
)
@limiter.limit("3 per minute")
def phone():

    if request.method == "POST":

        raw_phone = request.form.get("phone_number", "").strip()
        try:
            phone_number = normalize_phone_number(raw_phone)
        except ValueError:
            return render_template("auth/phone.html", error="Please enter a valid mobile number.")

        existing_user = User.query.filter_by(phone_number=phone_number).first()
        if existing_user and not existing_user.is_active:
            return render_template("auth/phone.html", error="This account is disabled.")

        previous_challenge = OTPChallenge.query.filter_by(phone_number=phone_number, purpose="login").order_by(OTPChallenge.created_at.desc()).first()
        now = datetime.now(timezone.utc)
        if previous_challenge and now - _as_utc(previous_challenge.created_at) < timedelta(seconds=60):
            return render_template("auth/phone.html", error="Please wait before requesting another code.")

        OTPChallenge.query.filter_by(phone_number=phone_number, purpose="login").delete()
        code = generate_code()
        challenge = OTPChallenge(
            phone_number=phone_number,
            purpose="login",
            code_hash=generate_password_hash(code),
            expires_at=now + timedelta(minutes=5),
            attempts=0,
        )
        db.session.add(challenge)
        try:
            send_code(phone_number, code)
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            return render_template(
                "auth/phone.html",
                error="OTP service is not configured. Add your OTP provider settings before using public authentication.",
            )

        session["phone_number"] = phone_number
        session["otp_phone"] = phone_number
        session["otp_challenge_id"] = challenge.id
        return redirect(url_for("auth.otp"))

    return render_template("auth/phone.html")


# =========================================================
# OTP
# =========================================================

@auth_bp.route(
    "/otp",
    methods=["GET", "POST"]
)
@limiter.limit("5 per minute")
def otp():
    phone_number = session.get("phone_number")
    if not phone_number:
        return redirect(url_for("auth.phone"))

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        challenge = OTPChallenge.query.filter_by(phone_number=phone_number, purpose="login").order_by(OTPChallenge.created_at.desc()).first()
        if challenge is None:
            return render_template("auth/otp.html", error="No active OTP request was found. Please request a new code.", phone=phone_number)
        if challenge.verified_at is not None:
            return render_template("auth/otp.html", error="This OTP has already been used. Please request a new code.", phone=phone_number)
        if _as_utc(challenge.expires_at) < datetime.now(timezone.utc):
            return render_template("auth/otp.html", error="This OTP has expired. Please request a new code.", phone=phone_number)
        if challenge.attempts >= 5:
            return render_template("auth/otp.html", error="Too many failed OTP attempts. Please request a new code.", phone=phone_number)

        challenge.attempts += 1
        valid = verify_code(phone_number, otp, challenge.code_hash)
        if not valid:
            db.session.commit()
            return render_template("auth/otp.html", error="Invalid OTP. Please try again.", phone=phone_number)

        user = User.query.filter_by(phone_number=phone_number).first()
        if user is not None and not user.is_active:
            db.session.rollback()
            return render_template("auth/otp.html", error="This account is disabled.", phone=phone_number)

        challenge.verified_at = datetime.now(timezone.utc)
        db.session.commit()

        previous_account_type = session.get("account_type") or "traveler"
        session.clear()
        session["authenticated"] = True
        session["account_type"] = previous_account_type
        session["phone_number"] = phone_number

        if user is None:
            user = User(phone_number=phone_number, country_code="+91", role=previous_account_type if previous_account_type in {"traveler", "partner"} else "traveler")
            db.session.add(user)
            db.session.commit()
        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()
        session["user_id"] = user.id
        _clear_temp_otp_session()

        if previous_account_type == "partner":
            return redirect(url_for("auth.partner_category"))
        return redirect(url_for("auth.profile"))

    return render_template("auth/otp.html", phone=phone_number)


# =========================================================
# TRAVELER PROFILE
# =========================================================

@auth_bp.route(
    "/profile",
    methods=["GET", "POST"]
)
def profile():

    if not session.get("authenticated"):
        return redirect(url_for("auth.account_type"))

    if session.get("account_type") != "traveler":
        return redirect(url_for("home.index"))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        country = request.form.get("country", "").strip()
        travel_style = request.form.get("travel_style", "").strip()
        trip_duration = request.form.get("trip_duration", "").strip()
        interests = request.form.getlist("interests")

        if not first_name:
            return render_template("auth/profile.html", error="First name is required.")

        session["first_name"] = first_name
        session["last_name"] = last_name
        session["country"] = country
        session["travel_style"] = travel_style
        session["trip_duration"] = trip_duration
        session["interests"] = interests
        session["profile_complete"] = True

        user = db.session.get(User, session.get("user_id"))
        if user is None:
            user = User.query.filter_by(phone_number=session.get("phone_number", "")).first()
        if user is not None:
            user.first_name = first_name
            user.last_name = last_name
            user.email = request.form.get("email", "").strip() or user.email
            db.session.add(user)

        profile = TravelerProfile.query.filter_by(phone_number=session.get("phone_number", "")).first()
        if profile is None:
            profile = TravelerProfile(phone_number=session.get("phone_number", ""), first_name=first_name)
            db.session.add(profile)

        profile.first_name = first_name
        profile.last_name = last_name
        profile.country = country
        profile.travel_style = travel_style
        profile.trip_duration = trip_duration
        profile.interests = interests
        db.session.commit()

        return redirect(url_for("home.index"))

    return render_template("auth/profile.html")


# =========================================================
# PARTNER CATEGORY
# =========================================================

@auth_bp.route(
    "/partner/category",
    methods=["GET", "POST"]
)
def partner_category():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":

        return redirect(
            url_for("home.index")
        )

    if request.method == "POST":

        category = request.form.get(
            "category",
            ""
        ).strip()

        categories = [
            "guide",
            "bike_rental",
            "auto_driver",
            "coracle_operator",
            "resort_owner",
        ]

        if category not in categories:

            return render_template(
                "auth/partner_category.html",
                error="Please select a partner category."
            )

        session["partner_category"] = category

        if category == "guide":

            return redirect(
                url_for("auth.guide_registration")
            )

        return redirect(
            url_for(
                "partner_onboarding.register",
                category=category
            )
        )

    return render_template(
        "auth/partner_category.html"
    )


# =========================================================
# GUIDE STEP 1 — PROFILE
# =========================================================

@auth_bp.route(
    "/partner/guide",
    methods=["GET", "POST"]
)
def guide_registration():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":

        return redirect(
            url_for("home.index")
        )

    if session.get("partner_category") != "guide":

        return redirect(
            url_for("auth.partner_category")
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

        experience_years = request.form.get(
            "experience_years",
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
                "auth/guide_registration.html",
                error="First name is required.",
                profile=request.form
            )

        if not last_name:

            return render_template(
                "auth/guide_registration.html",
                error="Last name is required.",
                profile=request.form
            )

        if not location:

            return render_template(
                "auth/guide_registration.html",
                error="Primary location is required.",
                profile=request.form
            )

        if not experience_years:

            return render_template(
                "auth/guide_registration.html",
                error="Please select your guiding experience.",
                profile=request.form
            )

        if not bio:

            return render_template(
                "auth/guide_registration.html",
                error="Please tell travelers about yourself.",
                profile=request.form
            )

        if not languages:

            return render_template(
                "auth/guide_registration.html",
                error="Please select at least one language.",
                profile=request.form
            )

        profile_photo = request.files.get(
            "profile_photo"
        )

        photo_filename = None

        if profile_photo and profile_photo.filename:
            try:
                from app.services.storage import save_image
                photo_filename = save_image(
                    profile_photo,
                    current_app.config["UPLOAD_DIR"],
                    "profile-photos"
                )
            except ValueError as error:
                return render_template(
                    "auth/guide_registration.html",
                    error=str(error),
                    profile=request.form
                )

        session["guide_profile"] = {

            "first_name": first_name,

            "last_name": last_name,

            "email": email,

            "phone_number": session.get(
                "phone_number"
            ),

            "location": location,

            "experience_years": experience_years,

            "bio": bio,

            "languages": languages,

            "profile_photo": photo_filename,
        }

        return redirect(
            url_for("auth.guide_services")
        )

    return render_template(
        "auth/guide_registration.html",
        profile=session.get(
            "guide_profile"
        )
    )


# =========================================================
# GUIDE STEP 2 — SERVICES & AREAS
# =========================================================

@auth_bp.route(
    "/partner/guide/services",
    methods=["GET", "POST"]
)
def guide_services():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":

        return redirect(
            url_for("home.index")
        )

    if session.get("partner_category") != "guide":

        return redirect(
            url_for("auth.partner_category")
        )

    if not session.get("guide_profile"):

        return redirect(
            url_for("auth.guide_registration")
        )

    if request.method == "POST":

        services = request.form.getlist(
            "services"
        )

        areas = request.form.getlist(
            "areas"
        )

        max_group_size = request.form.get(
            "max_group_size",
            ""
        ).strip()

        if not services:

            return render_template(
                "auth/guide_services.html",
                error="Select at least one guide service."
            )

        if not areas:

            return render_template(
                "auth/guide_services.html",
                error="Select at least one area you can guide."
            )

        if not max_group_size:

            return render_template(
                "auth/guide_services.html",
                error="Please select your maximum group size."
            )

        session["guide_services"] = {

            "services": services,

            "areas": areas,

            "max_group_size": max_group_size,
        }

        return redirect(
            url_for("auth.guide_pricing")
        )

    return render_template(
        "auth/guide_services.html"
    )


# =========================================================
# GUIDE STEP 3 — GENERAL PRICING
# =========================================================

@auth_bp.route(
    "/partner/guide/pricing",
    methods=["GET", "POST"]
)
def guide_pricing():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":

        return redirect(
            url_for("home.index")
        )

    if session.get("partner_category") != "guide":

        return redirect(
            url_for("auth.partner_category")
        )

    if not session.get("guide_profile"):

        return redirect(
            url_for("auth.guide_registration")
        )

    if not session.get("guide_services"):

        return redirect(
            url_for("auth.guide_services")
        )

    if request.method == "POST":

        pricing_type = request.form.get(
            "pricing_type",
            ""
        ).strip()

        hourly_rate = request.form.get(
            "hourly_rate",
            ""
        ).strip()

        half_day_rate = request.form.get(
            "half_day_rate",
            ""
        ).strip()

        full_day_rate = request.form.get(
            "full_day_rate",
            ""
        ).strip()

        max_group_size = request.form.get(
            "max_group_size",
            ""
        ).strip()

        minimum_booking_notice = request.form.get(
            "minimum_booking_notice",
            ""
        ).strip()

        if pricing_type not in [
            "per_person",
            "per_group",
        ]:

            return render_template(
                "auth/guide_pricing.html",
                error="Please select a pricing type."
            )

        try:

            hourly = float(
                hourly_rate
            )

            half_day = float(
                half_day_rate
            )

            full_day = float(
                full_day_rate
            )

            group_size = int(
                max_group_size
            )

            booking_notice = int(
                minimum_booking_notice
            )

        except (
            TypeError,
            ValueError,
        ):

            return render_template(
                "auth/guide_pricing.html",
                error="Please enter valid pricing values."
            )

        if hourly < 0:

            return render_template(
                "auth/guide_pricing.html",
                error="Hourly rate cannot be negative."
            )

        if half_day < 0:

            return render_template(
                "auth/guide_pricing.html",
                error="Half-day rate cannot be negative."
            )

        if full_day < 0:

            return render_template(
                "auth/guide_pricing.html",
                error="Full-day rate cannot be negative."
            )

        if group_size < 1:

            return render_template(
                "auth/guide_pricing.html",
                error="Maximum group size must be at least 1."
            )

        if booking_notice < 0:

            return render_template(
                "auth/guide_pricing.html",
                error="Booking notice cannot be negative."
            )

        session["guide_pricing"] = {

            "pricing_type": pricing_type,

            "hourly_rate": hourly,

            "half_day_rate": half_day,

            "full_day_rate": full_day,

            "max_group_size": group_size,

            "minimum_booking_notice": booking_notice,
        }

        return redirect(
            url_for("auth.guide_availability")
        )

    return render_template(
        "auth/guide_pricing.html"
    )


# =========================================================
# GUIDE STEP 4 — AVAILABILITY
# =========================================================

@auth_bp.route(
    "/partner/guide/availability",
    methods=["GET", "POST"]
)
def guide_availability():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":

        return redirect(
            url_for("home.index")
        )

    if session.get("partner_category") != "guide":

        return redirect(
            url_for("auth.partner_category")
        )

    if not session.get("guide_profile"):

        return redirect(
            url_for("auth.guide_registration")
        )

    if not session.get("guide_services"):

        return redirect(
            url_for("auth.guide_services")
        )

    if not session.get("guide_pricing"):

        return redirect(
            url_for("auth.guide_pricing")
        )

    if request.method == "POST":

        available_days = request.form.getlist(
            "available_days"
        )

        time_slots = request.form.getlist(
            "time_slots"
        )

        booking_notice = request.form.get(
            "booking_notice",
            ""
        ).strip()

        booking_mode = request.form.get(
            "booking_mode",
            "request"
        ).strip()

        if not available_days:

            return render_template(
                "auth/guide_availability.html",
                error="Select at least one available day."
            )

        if not time_slots:

            return render_template(
                "auth/guide_availability.html",
                error="Select at least one available time period."
            )

        if not booking_notice:

            return render_template(
                "auth/guide_availability.html",
                error="Please select your booking notice."
            )

        if booking_mode not in [
            "request",
            "instant",
        ]:

            booking_mode = "request"

        session["guide_availability"] = {

            "available_days": available_days,

            "time_slots": time_slots,

            "booking_notice": booking_notice,

            "booking_mode": booking_mode,
        }

        return redirect(
            url_for("auth.guide_verification")
        )

    return render_template(
        "auth/guide_availability.html"
    )


# =========================================================
# GUIDE STEP 5 — VERIFICATION
# =========================================================

@auth_bp.route(
    "/partner/guide/verification",
    methods=["GET", "POST"]
)
def guide_verification():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":

        return redirect(
            url_for("home.index")
        )

    if session.get("partner_category") != "guide":

        return redirect(
            url_for("auth.partner_category")
        )

    if not session.get("guide_profile"):

        return redirect(
            url_for("auth.guide_registration")
        )

    if not session.get("guide_services"):

        return redirect(
            url_for("auth.guide_services")
        )

    if not session.get("guide_pricing"):

        return redirect(
            url_for("auth.guide_pricing")
        )

    if not session.get("guide_availability"):

        return redirect(
            url_for("auth.guide_availability")
        )

    if request.method == "POST":

        id_type = request.form.get(
            "id_type",
            ""
        ).strip()

        id_number = request.form.get(
            "id_number",
            ""
        ).strip()

        credential_type = request.form.get(
            "credential_type",
            ""
        ).strip()

        credential_number = request.form.get(
            "credential_number",
            ""
        ).strip()

        information_confirmed = request.form.get(
            "information_confirmed"
        )

        verification_consent = request.form.get(
            "verification_consent"
        )

        identity_document = request.files.get(
            "identity_document"
        )

        credential_document = request.files.get(
            "credential_document"
        )

        if not id_type:

            return render_template(
                "auth/guide_verification.html",
                error="Please select an identity document."
            )

        if not id_number:

            return render_template(
                "auth/guide_verification.html",
                error="Identity document number is required."
            )

        if not identity_document or not identity_document.filename:

            return render_template(
                "auth/guide_verification.html",
                error="Please upload your identity document."
            )

        if credential_type == "not_applicable":

            credential_type = ""

        if information_confirmed != "yes":

            return render_template(
                "auth/guide_verification.html",
                error="Please confirm that your information is accurate."
            )

        if verification_consent != "yes":

            return render_template(
                "auth/guide_verification.html",
                error="Please agree to verification."
            )

        try:
            identity_path = save_private_file(identity_document, current_app.config["UPLOAD_DIR"], "private/identity")
            credential_path = None
            if credential_document and credential_document.filename:
                credential_path = save_private_file(credential_document, current_app.config["UPLOAD_DIR"], "private/credentials")
        except ValueError as error:
            return render_template("auth/guide_verification.html", error=str(error))

        session["guide_verification"] = {

            "id_type": id_type,

            "credential_type": credential_type,

            "identity_document": identity_path,

            "credential_document": credential_path,

            "information_confirmed": True,

            "verification_consent": True,
        }

        return redirect(
            url_for("auth.guide_photos")
        )

    return render_template(
        "auth/guide_verification.html"
    )


# =========================================================
# GUIDE STEP 6 — PHOTOS
# =========================================================

@auth_bp.route(
    "/partner/guide/photos",
    methods=["GET", "POST"]
)
def guide_photos():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":

        return redirect(
            url_for("home.index")
        )

    if session.get("partner_category") != "guide":

        return redirect(
            url_for("auth.partner_category")
        )

    if not session.get("guide_verification"):

        return redirect(
            url_for("auth.guide_verification")
        )

    if request.method == "POST":

        cover_photo = request.files.get(
            "cover_photo"
        )

        gallery_photos = request.files.getlist(
            "gallery_photos"
        )

        allowed_extensions = {
            "jpg",
            "jpeg",
            "png",
            "webp",
        }

        def valid_image(file):

            if not file or not file.filename:

                return False

            filename = file.filename.lower()

            if "." not in filename:

                return False

            extension = filename.rsplit(
                ".",
                1
            )[1]

            return (
                extension
                in allowed_extensions
            )

        if not valid_image(cover_photo):

            return render_template(
                "auth/guide_photos.html",
                error="Please upload a valid cover photo."
            )

        if len(gallery_photos) > 6:

            return render_template(
                "auth/guide_photos.html",
                error="You can select a maximum of 6 gallery photos."
            )

        valid_gallery = []

        for photo in gallery_photos:

            if valid_image(photo):

                valid_gallery.append(
                    photo.filename
                )

        try:
            from app.services.storage import save_image
            cover_path = save_image(
                cover_photo,
                current_app.config["UPLOAD_DIR"],
                "guide-cover"
            )
            gallery_paths = []
            for photo in gallery_photos:
                if valid_image(photo):
                    gallery_paths.append(
                        save_image(
                            photo,
                            current_app.config["UPLOAD_DIR"],
                            "guide-gallery"
                        )
                    )
        except ValueError as error:
            return render_template(
                "auth/guide_photos.html",
                error=str(error)
            )

        session["guide_photos"] = {
            "cover_photo": cover_path,
            "gallery_photos": gallery_paths,
        }

        return redirect(
            url_for("auth.guide_payout")
        )

    return render_template(
        "auth/guide_photos.html"
    )


# =========================================================
# GUIDE STEP 7 — PAYOUT
# =========================================================

@auth_bp.route(
    "/partner/guide/payout",
    methods=["GET", "POST"]
)
def guide_payout():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":

        return redirect(
            url_for("home.index")
        )

    if session.get("partner_category") != "guide":

        return redirect(
            url_for("auth.partner_category")
        )

    if not session.get("guide_profile"):

        return redirect(
            url_for("auth.guide_registration")
        )

    if not session.get("guide_services"):

        return redirect(
            url_for("auth.guide_services")
        )

    if not session.get("guide_pricing"):

        return redirect(
            url_for("auth.guide_pricing")
        )

    if not session.get("guide_availability"):

        return redirect(
            url_for("auth.guide_availability")
        )

    if not session.get("guide_verification"):

        return redirect(
            url_for("auth.guide_verification")
        )

    if not session.get("guide_photos"):

        return redirect(
            url_for("auth.guide_photos")
        )

    if request.method == "POST":

        payout_method = request.form.get(
            "payout_method",
            ""
        ).strip()

        if payout_method not in [
            "bank",
            "upi",
        ]:

            return render_template(
                "auth/guide_payout.html",
                error="Please select a payout method."
            )

        session["guide_payout"] = {"payout_method": payout_method}

        return redirect(
            url_for("auth.guide_review")
        )

    return render_template(
        "auth/guide_payout.html"
    )


# =========================================================
# GUIDE STEP 8 — REVIEW
# =========================================================

@auth_bp.route(
    "/partner/guide/review",
    methods=["GET"]
)
def guide_review():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":

        return redirect(
            url_for("home.index")
        )

    if session.get("partner_category") != "guide":

        return redirect(
            url_for("auth.partner_category")
        )

    required_steps = [
        "guide_profile",
        "guide_services",
        "guide_pricing",
        "guide_availability",
        "guide_verification",
        "guide_photos",
        "guide_payout",
    ]

    route_map = {

        "guide_profile":
            "auth.guide_registration",

        "guide_services":
            "auth.guide_services",

        "guide_pricing":
            "auth.guide_pricing",

        "guide_availability":
            "auth.guide_availability",

        "guide_verification":
            "auth.guide_verification",

        "guide_photos":
            "auth.guide_photos",

        "guide_payout":
            "auth.guide_payout",
    }

    for step in required_steps:

        if not session.get(step):

            return redirect(
                url_for(
                    route_map[step]
                )
            )

    return render_template(
        "auth/guide_review.html"
    )


# =========================================================
# GUIDE SUBMIT
# THIS IS THE DATABASE FIX
# =========================================================

@auth_bp.route(
    "/partner/guide/submit",
    methods=["POST"]
)
def guide_submit():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":

        return redirect(
            url_for("home.index")
        )

    if session.get("partner_category") != "guide":

        return redirect(
            url_for("auth.partner_category")
        )

    required_steps = [
        "guide_profile",
        "guide_services",
        "guide_pricing",
        "guide_availability",
        "guide_verification",
        "guide_photos",
        "guide_payout",
    ]

    for step in required_steps:

        if not session.get(step):

            return redirect(
                url_for("auth.guide_review")
            )

    confirmation = request.form.get(
        "final_confirmation"
    )

    if confirmation != "yes":

        return redirect(
            url_for("auth.guide_review")
        )

    # -----------------------------------------------------
    # IMPORT DATABASE COMPONENTS
    # -----------------------------------------------------

    from app.extensions import db

    from app.models.guide import (
        GuideApplication
    )

    # -----------------------------------------------------
    # GET SESSION DATA
    # -----------------------------------------------------

    profile = session.get(
        "guide_profile",
        {}
    )

    services = session.get(
        "guide_services",
        {}
    )

    pricing = session.get(
        "guide_pricing",
        {}
    )

    availability = session.get(
        "guide_availability",
        {}
    )

    verification = session.get(
        "guide_verification",
        {}
    )

    photos = session.get(
        "guide_photos",
        {}
    )

    payout = session.get(
        "guide_payout",
        {}
    )

    # -----------------------------------------------------
    # CREATE DATABASE RECORD
    # -----------------------------------------------------

    application = GuideApplication(

        # Account
        phone_number=session.get(
            "phone_number",
            ""
        ),

        email=profile.get(
            "email"
        ),

        # Profile
        first_name=profile.get(
            "first_name",
            ""
        ),

        last_name=profile.get(
            "last_name",
            ""
        ),

        location=profile.get(
            "location",
            ""
        ),

        experience_years=profile.get(
            "experience_years",
            ""
        ),

        bio=profile.get(
            "bio",
            ""
        ),

        languages=profile.get(
            "languages",
            []
        ),

        # Services
        services=services.get(
            "services",
            []
        ),

        areas=services.get(
            "areas",
            []
        ),

        max_group_size=services.get(
            "max_group_size"
        ),

        # Pricing
        pricing_type=pricing.get(
            "pricing_type"
        ),

        hourly_rate=pricing.get(
            "hourly_rate"
        ),

        half_day_rate=pricing.get(
            "half_day_rate"
        ),

        full_day_rate=pricing.get(
            "full_day_rate"
        ),

        pricing_group_size=pricing.get(
            "max_group_size"
        ),

        minimum_booking_notice=pricing.get(
            "minimum_booking_notice"
        ),

        # Availability
        available_days=availability.get(
            "available_days",
            []
        ),

        time_slots=availability.get(
            "time_slots",
            []
        ),

        booking_notice=availability.get(
            "booking_notice"
        ),

        booking_mode=availability.get(
            "booking_mode"
        ),

        # Verification
        id_type=verification.get(
            "id_type"
        ),

        identity_document_path=verification.get(
            "identity_document"
        ),

        credential_type=verification.get(
            "credential_type"
        ),

        credential_number=verification.get(
            "credential_number"
        ),

        credential_document_path=verification.get(
            "credential_document"
        ),

        # Photos
        profile_photo_path=profile.get(
            "profile_photo"
        ),

        cover_photo_path=photos.get(
            "cover_photo"
        ),

        gallery_photo_paths=photos.get(
            "gallery_photos",
            []
        ),

        # Payout
        payout_method=payout.get(
            "payout_method"
        ),

        # Application
        status="pending",

        submitted_at=datetime.now(timezone.utc),
    )

    # -----------------------------------------------------
    # SAVE DATABASE RECORD
    # -----------------------------------------------------

    try:

        db.session.add(
            application
        )

        db.session.commit()

    except Exception as error:

        db.session.rollback()

        print(
            "GUIDE APPLICATION DATABASE ERROR:",
            error
        )

        return render_template(
            "auth/guide_review.html",
            error=(
                "We could not submit your application "
                "right now. Please try again."
            )
        )

    # -----------------------------------------------------
    # SAVE APPLICATION ID IN SESSION
    # -----------------------------------------------------

    session["guide_application_id"] = (
        application.id
    )

    session["guide_application_status"] = (
        "pending"
    )

    return redirect(
        url_for("auth.guide_submitted")
    )


# =========================================================
# GUIDE SUBMITTED
# =========================================================

@auth_bp.route(
    "/partner/guide/submitted",
    methods=["GET"]
)
def guide_submitted():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":

        return redirect(
            url_for("home.index")
        )

    if session.get("partner_category") != "guide":

        return redirect(
            url_for("auth.partner_category")
        )

    application_id = session.get("guide_application_id")
    if application_id and session.get("phone_number"):
        from app.models.guide import GuideApplication
        application = GuideApplication.query.filter_by(
            id=application_id,
            phone_number=session.get("phone_number"),
        ).first()
        if not application or application.status != "pending":
            return redirect(url_for("auth.guide_application_status"))
    elif session.get("guide_application_status") != "pending":
        return redirect(
            url_for("auth.guide_review")
        )

    return render_template(
        "auth/guide_submitted.html"
    )


# =========================================================
# COMMON PARTNER BUSINESS
# Used temporarily by:
# Bike Rental
# Auto Driver
# Coracle Operator
# Resort Owner
# =========================================================

@auth_bp.route(
    "/partner/business",
    methods=["GET", "POST"]
)
def partner_business():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":

        return redirect(
            url_for("home.index")
        )

    if request.method == "POST":

        business_name = request.form.get(
            "business_name",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        if not business_name:

            return render_template(
                "auth/partner_business.html",
                error="Business name is required."
            )

        session["business_name"] = (
            business_name
        )

        session["business_location"] = (
            location
        )

        session["business_description"] = (
            description
        )

        return redirect(
            url_for(
                "auth.partner_verification"
            )
        )

    return render_template(
        "auth/partner_business.html",
        category=session.get(
            "partner_category"
        )
    )


# =========================================================
# COMMON PARTNER VERIFICATION
# =========================================================

@auth_bp.route(
    "/partner/verification",
    methods=["GET", "POST"]
)
def partner_verification():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":
        return redirect(url_for("home.index"))

    if request.method == "POST":

        session["verification_status"] = (
            "pending"
        )

        return redirect(
            url_for("auth.partner_submitted")
        )

    return render_template(
        "auth/partner_verification.html",
        category=session.get(
            "partner_category"
        )
    )


# =========================================================
# COMMON PARTNER SUBMITTED
# =========================================================

@auth_bp.route(
    "/partner/submitted"
)
def partner_submitted():

    if not session.get("authenticated"):

        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":
        return redirect(url_for("home.index"))

    return render_template(
        "auth/partner_submitted.html",
        category=session.get(
            "partner_category"
        )
    )

# =========================================================
# GUIDE APPLICATION STATUS
# =========================================================

@auth_bp.route(
    "/partner/guide/application-status",
    methods=["GET"]
)
def guide_application_status():

    if not session.get("authenticated"):
        return redirect(
            url_for("auth.account_type")
        )

    if session.get("account_type") != "partner":
        return redirect(
            url_for("home.index")
        )

    if session.get("partner_category") != "guide":
        return redirect(
            url_for("auth.partner_category")
        )

    application_id = session.get(
        "guide_application_id"
    )

    from app.models.guide import GuideApplication

    application = None
    if application_id and session.get("phone_number"):
        application = GuideApplication.query.filter_by(
            id=application_id,
            phone_number=session.get("phone_number"),
        ).first()

    if application is None and session.get("phone_number"):
        application = GuideApplication.query.filter_by(
            phone_number=session.get("phone_number")
        ).order_by(GuideApplication.id.desc()).first()
        if application:
            session["guide_application_id"] = application.id

    if application is None:
        return redirect(
            url_for("auth.guide_registration")
        )

    return render_template(
        "auth/guide_application_status.html",
        application=application
    )