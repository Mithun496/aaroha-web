# Authorization Matrix

Generated from the live Flask URL map after the current audit. `GUEST` means an unauthenticated account-selection/OTP flow; `PUBLIC` means anonymous access. Every mutation is a CSRF-protected POST. Numeric IDs are not treated as authorization.

| Route | Methods | Access | Ownership / enforcement |
| --- | --- | --- | --- |
| `/` | GET | PUBLIC | Public home page. |
| `/health` | GET | PUBLIC | Database readiness query only. |
| `/static/<path:filename>` | GET | PUBLIC | Framework static directory only. |
| `/media/<path:relative_path>` | GET | PUBLIC | Only validated `public/` media keys; private namespace denied. |
| `/explore` | GET | PUBLIC | Published browsing data. |
| `/destination/<slug>` | GET | PUBLIC | Published destination by slug. |
| `/culture-guide` | GET | PUBLIC | Static/public guide content. |
| `/trip-planner` | GET, POST | PUBLIC | Stateless planner input/output; no account records mutated. |
| `/guides` | GET | PUBLIC | Approved guide listings. |
| `/guides/<int:guide_id>` | GET, POST | PUBLIC / TRAVELER | GET exposes approved guide data and guide-booking reviews only; POST creates a booking for the authenticated traveler and selected approved guide. |
| `/bikes` | GET | PUBLIC | Approved rental partners and active fleet. |
| `/bikes/<int:vehicle_id>` | GET, POST | PUBLIC / TRAVELER | POST requires authenticated traveler; server chooses active vehicle, approved provider, price, currency, and provider identity. |
| `/stays` | GET | PUBLIC | Approved resort listings. |
| `/stays/<int:resort_id>` | GET | PUBLIC | Approved listing only. |
| `/services` | GET | PUBLIC | Aggregate public service counts. |
| `/auto` | GET, POST | PUBLIC / TRAVELER | POST requires authenticated traveler and selects an approved, online captain. |
| `/coracles` | GET, POST | PUBLIC / TRAVELER | POST requires authenticated traveler; approved operator, future date, and capacity are validated server-side. |
| `/offline` | GET | PUBLIC | Public offline-pack page. |
| `/offline/hampi.json` | GET | PUBLIC | Public static/destination content; no account data. |
| `/support` | GET | PUBLIC | Public support page. |
| `/auth/account-type` | GET, POST | GUEST | Sets only the current browser's onboarding account type. |
| `/auth/phone` | GET, POST | GUEST | Normalizes phone; rejects disabled accounts; IP rate limit and per-phone resend cooldown. |
| `/auth/otp` | GET, POST | GUEST | Challenge is bound to phone in session and DB, expires, limits attempts, and is one-time. |
| `/auth/logout` | POST | AUTHENTICATED | Clears only the current browser session; CSRF required. |
| `/auth/profile` | GET, POST | TRAVELER | Reads/writes the profile matching the authenticated session phone. |
| `/auth/partner/category` | GET, POST | PARTNER | Authenticated partner onboarding session only. |
| `/auth/partner/business` | GET, POST | PARTNER | Authenticated partner onboarding session only. |
| `/auth/partner/verification` | GET, POST | PARTNER | Authenticated partner onboarding session only. |
| `/auth/partner/submitted` | GET | PARTNER | Current session onboarding status only. |
| `/auth/partner/<category>` | GET, POST | PARTNER | New application is bound to authenticated phone and allowlisted category. |
| `/auth/partner/<category>/submitted/<int:application_id>` | GET | PARTNER | Application lookup includes authenticated phone. |
| `/auth/partner/guide` | GET, POST | PARTNER | Guide-category onboarding; data belongs to current browser session until submission. |
| `/auth/partner/guide/services` | GET, POST | PARTNER | Guide-category onboarding session only. |
| `/auth/partner/guide/pricing` | GET, POST | PARTNER | Guide-category onboarding session only; server validates numeric ranges. |
| `/auth/partner/guide/availability` | GET, POST | PARTNER | Guide-category onboarding session only. |
| `/auth/partner/guide/verification` | GET, POST | PARTNER | Guide-category onboarding; files stored under private namespace; document numbers are not retained in session. |
| `/auth/partner/guide/photos` | GET, POST | PARTNER | Guide-category onboarding; media stored in public namespace. |
| `/auth/partner/guide/payout` | GET, POST | PARTNER | Stores only preferred method; bank/UPI credentials are not collected or retained. |
| `/auth/partner/guide/review` | GET | PARTNER | Current session's draft onboarding data. |
| `/auth/partner/guide/submit` | POST | PARTNER | Requires all session steps and explicit confirmation; submitted phone is taken from authenticated session. |
| `/auth/partner/guide/submitted` | GET | PARTNER | Session application ID is constrained by authenticated phone. |
| `/auth/partner/guide/application-status` | GET | PARTNER | Application lookup constrained by authenticated phone. |
| `/bookings` | GET | TRAVELER | Query filters by authenticated traveler phone. |
| `/profile` | GET | TRAVELER | Query filters by authenticated traveler phone. |
| `/notifications` | GET | TRAVELER | Recipient is authenticated traveler phone. |
| `/notifications/<int:notification_id>/read` | POST | TRAVELER | Notification ID and recipient phone are queried together. |
| `/emergency-contacts` | GET, POST | TRAVELER | All contact reads/writes use authenticated traveler phone. |
| `/emergency-contacts/<int:contact_id>/delete` | POST | TRAVELER | Contact ID and owner phone are queried together. |
| `/sos` | GET, POST | TRAVELER | Incident and contacts filter by authenticated traveler phone; input is validated. No dispatch/live tracking is performed. |
| `/payments/<string:booking_reference>` | POST | TRAVELER | Booking reference and authenticated traveler phone are queried together. Production payment remains disabled without an adapter. |
| `/reviews/<int:booking_id>` | POST | TRAVELER | Requires completed booking owned by traveler; provider ID comes from booking; unique booking constraint enforces one review. |
| `/partner/dashboard` | GET | APPROVED PARTNER | Guide application or approved rental partner is resolved using authenticated phone. |
| `/partner/bike/vehicles` | GET, POST | APPROVED PARTNER | Bike fleet is attached to approved rental partner ID. |
| `/partner/bike/bookings/<int:booking_id>/decision` | POST | APPROVED PARTNER | Booking is constrained by bike type and the authenticated partner ID; transition must be pending to confirmed/cancelled. |
| `/partner/bookings/<int:booking_id>/decision` | POST | APPROVED PARTNER | Booking is constrained by guide application ID and guide type; allowed status transitions validated. |
| `/partner/guide/profile/edit` | GET, POST | APPROVED PARTNER | Current guide application lookup is phone-bound. |
| `/partner/guide/services/edit` | GET, POST | APPROVED PARTNER | Current guide application lookup is phone-bound; values validated. |
| `/partner/guide/pricing/edit` | GET, POST | APPROVED PARTNER | Current guide application lookup is phone-bound; numeric values validated. |
| `/partner/guide/availability/edit` | GET, POST | APPROVED PARTNER | Current guide application lookup is phone-bound. |
| `/partner/service-bookings` | GET | APPROVED PARTNER | Authenticated phone selects approved operator/captain; query binds both provider ID and booking type. |
| `/partner/service-bookings/<int:booking_id>` | POST | APPROVED PARTNER | Booking query binds authenticated provider, booking type, and ID; finite state transition map enforced. |
| `/admin/login` | GET, POST | GUEST | Password hash checked; global rate limits apply. Successful login clears old session state. |
| `/admin/logout` | GET, POST | ADMIN | GET is confirmation-only; POST clears current administrator session and requires CSRF. |
| `/admin/dashboard` | GET | ADMIN | Admin session required. |
| `/admin/operations` | GET | ADMIN | Admin-only, read-only operational datasets; latest 50 per dataset. |
| `/admin/partners` | GET | ADMIN | Admin-only partner applications. |
| `/admin/partner/<int:application_id>` | GET | ADMIN | Admin-only application detail. |
| `/admin/partner/<int:application_id>/decision` | POST | ADMIN | Status/action allowlists, state validation, database updates and audit log. |
| `/admin/guide/<int:application_id>` | GET | ADMIN | Admin-only guide application detail and private document references. |
| `/admin/guide/<int:application_id>/decision` | POST | ADMIN | Action/status validation and audit log. |
| `/admin/audit-logs` | GET | ADMIN | Admin-only, read-only log list. |
| `/admin/private-file/<path:relative_path>` | GET | ADMIN | Admin gate plus private-root/key validation; normal traveler/provider receives login redirect. |

## Explicit Isolation Tests

Automated tests exercise Traveler A versus Traveler B for bookings, reviews, notifications, emergency contacts, SOS incident content, payments, and profile data. Provider tests cover guide profile/application IDs, bike booking ownership, and auto/coracle numeric-ID collisions. Private download tests cover anonymous/provider denial and admin access. These tests use SQLite and local storage; they do not establish PostgreSQL, S3, Twilio, or real payment-provider behavior.

## Residual Authorization Scope

Administrator authentication is a single shared environment-configured administrator identity, not per-admin accounts or MFA. The admin operations page is an operational read-only listing; it is not an editable CRUD console. Access by an administrator is intentionally broad and should be restricted operationally.
