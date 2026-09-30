from app.extensions import db
from app.models.destination import Destination, DestinationImage
from app.models.platform import AutoCaptain, BikeVehicle, CoracleOperator, RentalPartner, ResortListing


DESTINATION_SEED = [
    {
        "name": "Hampi",
        "slug": "hampi",
        "region": "Karnataka",
        "category": "heritage",
        "description": "A UNESCO-listed heritage landscape of temples, boulders, riverfront ruins and living local culture.",
        "latitude": 15.3350,
        "longitude": 76.4600,
        "opening_hours": "Opening hours vary by monument and temple; confirm locally before a timed visit.",
        "cultural_info": "Respect temple customs, dress modestly at active religious sites, and ask before photographing people or ceremonies.",
        "safety_info": "Always carry water, avoid isolated paths after dark, and confirm local conditions before climbing rocky viewpoints.",
        "highlights": ["Virupaksha Temple", "Vijaya Vittala Temple", "Hampi Bazaar", "Tungabhadra riverside", "Hemakuta Hill"],
        "rules": [
            "Remove shoes where signs or temple staff require it.",
            "Dress respectfully at active religious sites.",
            "Check photography restrictions before entering sanctums.",
            "Follow queue, worship and local etiquette.",
        ],
        "images": [
            {"image_url": "/static/images/destinations/hampi-1.jpg", "caption": "Hampi heritage landscape"},
            {"image_url": "/static/images/destinations/hampi-2.jpg", "caption": "Ruins and riverfront"},
        ],
    },
    {
        "name": "Sanapur",
        "slug": "sanapur",
        "region": "Karnataka",
        "category": "nature",
        "description": "A quieter base near Hampi known for its lake, rocky landscapes and rural atmosphere.",
        "latitude": 15.3329,
        "longitude": 76.4308,
        "opening_hours": "Outdoor areas are best visited in daylight; access can vary by local conditions.",
        "cultural_info": "Stay conscious of village privacy and keep to public access points.",
        "safety_info": "Carry water, avoid unsafe climbing, and check local conditions before entering or swimming in water bodies.",
        "highlights": ["Sanapur Lake", "Rocky viewpoints", "Village roads", "Sunset landscapes"],
        "rules": [
            "Respect private farmland and village homes.",
            "Avoid entering water or climbing rocks in unsafe conditions.",
            "Carry water and sun protection.",
        ],
        "images": [{"image_url": "/static/images/destinations/sanapur-1.jpg", "caption": "Sanapur lake"}],
    },
    {
        "name": "Anegundi",
        "slug": "anegundi",
        "region": "Karnataka",
        "category": "heritage",
        "description": "A historic riverside settlement across the Tungabhadra from the core Hampi landscape.",
        "latitude": 15.3342,
        "longitude": 76.4831,
        "opening_hours": "Individual monuments and community spaces may keep different hours.",
        "cultural_info": "Anegundi is a living village as well as a heritage area; respect local households and community spaces.",
        "safety_info": "Use marked routes and established crossings; avoid isolated riverbanks after dark.",
        "highlights": ["Pampa Sarovara", "Village heritage", "Riverside landscapes"],
        "rules": ["Respect shrines and village spaces.", "Ask before photographing people."],
        "images": [{"image_url": "/static/images/destinations/anegundi-1.jpg", "caption": "Anegundi river settlement"}],
    },
    {
        "name": "Kamalapura",
        "slug": "kamalapura",
        "region": "Karnataka",
        "category": "culture",
        "description": "A practical gateway for museums, heritage monuments and local travel around Hampi.",
        "latitude": 15.4150,
        "longitude": 76.5787,
        "opening_hours": "Museum and monument hours vary by site.",
        "cultural_info": "This area is a useful cultural and transit hub for the broader Hampi region.",
        "safety_info": "Follow local traffic rules and monument signage when visiting heritage spaces.",
        "highlights": ["Archaeological Museum", "Heritage access", "Local transport hub"],
        "rules": ["Follow monument signage.", "Respect photography restrictions."],
        "images": [{"image_url": "/static/images/destinations/kamalapura-1.jpg", "caption": "Kamalapura"}],
    },
    {
        "name": "Gangavathi",
        "slug": "gangavathi",
        "region": "Karnataka",
        "category": "local-life",
        "description": "A nearby town useful for local services, transport and regional exploration.",
        "latitude": 15.4253,
        "longitude": 76.5288,
        "opening_hours": "Town services follow individual business hours.",
        "cultural_info": "A practical place to observe daily life and connect with local services across the region.",
        "safety_info": "Keep valuables secure in crowded areas and observe general traffic caution.",
        "highlights": ["Local markets", "Regional food", "Transport connections"],
        "rules": ["Use normal local traffic and pedestrian caution.", "Ask before photographing people or private places."],
        "images": [{"image_url": "/static/images/destinations/gangavathi-1.jpg", "caption": "Gangavathi town"}],
    },
    {
        "name": "Hosapete",
        "slug": "hosapete",
        "region": "Karnataka",
        "category": "hub",
        "description": "A major nearby town and transport base for exploring the Hampi region.",
        "latitude": 15.2680,
        "longitude": 76.3899,
        "opening_hours": "Individual attractions and businesses have their own schedules.",
        "cultural_info": "A helpful base for transport, meals, and onward movement into heritage sites.",
        "safety_info": "Keep valuables secure in crowded transit areas and verify final transport timings.",
        "highlights": ["Local markets", "Transport hub", "Regional access"],
        "rules": ["Keep valuables secure in crowded areas.", "Confirm last-mile transport timings."],
        "images": [{"image_url": "/static/images/destinations/hosapete-1.jpg", "caption": "Hosapete town"}],
    },
]


def seed_destinations():
    created = 0
    for data in DESTINATION_SEED:
        destination = Destination.query.filter_by(slug=data["slug"]).first()
        if destination is None:
            destination = Destination(**{k: v for k, v in data.items() if k not in {"images"}})
            db.session.add(destination)
            db.session.flush()
            created += 1
        else:
            for field in [
                "name",
                "region",
                "category",
                "description",
                "latitude",
                "longitude",
                "opening_hours",
                "cultural_info",
                "safety_info",
                "highlights",
                "rules",
                "is_published",
            ]:
                setattr(destination, field, data.get(field, getattr(destination, field)))

        for image_data in data.get("images", []):
            existing = DestinationImage.query.filter_by(destination_id=destination.id, image_url=image_data["image_url"]).first()
            if existing is None:
                image = DestinationImage(destination_id=destination.id, **image_data)
                db.session.add(image)

    db.session.commit()
    return created


def seed_demo_data():
    seed_destinations()
    created = 0
    partner = RentalPartner.query.filter_by(phone_number="+919000000001").first()
    if partner is None:
        partner = RentalPartner(phone_number="+919000000001", owner_name="AAROHA Demo", business_name="Hampi Demo Rides", location="Hampi", status="approved")
        db.session.add(partner)
        db.session.flush()
        created += 1
    if not BikeVehicle.query.filter_by(provider_id=partner.id, name="Demo scooter").first():
        db.session.add(BikeVehicle(provider_id=partner.id, name="Demo scooter", vehicle_type="Scooter", location="Hampi", price=700, pricing_unit="day", is_active=True))
        created += 1
    if not AutoCaptain.query.filter_by(phone_number="+919000000002").first():
        db.session.add(AutoCaptain(phone_number="+919000000002", owner_name="AAROHA Demo", full_name="Demo Captain", location="Hampi", vehicle_number="KA-00-DEMO", vehicle_type="Auto", status="approved", is_online=True))
        created += 1
    if not CoracleOperator.query.filter_by(phone_number="+919000000003").first():
        db.session.add(CoracleOperator(phone_number="+919000000003", business_name="Demo Coracle Operator", location="Tungabhadra", boat_capacity=6, price=250, status="approved"))
        created += 1
    if not ResortListing.query.filter_by(provider_phone="+919000000004").first():
        db.session.add(ResortListing(provider_phone="+919000000004", name="AAROHA Demo Stay", description="Development-only listing.", address="Hampi", amenities=["water"], room_info=["demo room"], photos=[], status="approved"))
        created += 1
    db.session.commit()
    return created
