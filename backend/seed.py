from database import SessionLocal
from models import HCP

DEMO_HCPS = [
    {"name": "Dr. Sarah Chen", "specialty": "Cardiology", "location": "Boston, MA"},
    {"name": "Dr. Rajesh Kumar", "specialty": "Oncology", "location": "Mumbai, IN"},
    {"name": "Dr. Emily Rodriguez", "specialty": "Neurology", "location": "Austin, TX"},
    {"name": "Dr. James Okafor", "specialty": "Endocrinology", "location": "London, UK"},
    {"name": "Dr. Mei Tanaka", "specialty": "Pediatrics", "location": "Tokyo, JP"},
    {"name": "Dr. Anna Kowalski", "specialty": "Cardiology", "location": "Berlin, DE"},
]


def seed_hcps():
    db = SessionLocal()
    try:
        if db.query(HCP).count() == 0:
            db.add_all([HCP(**h) for h in DEMO_HCPS])
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_hcps()
    print("Seeded demo HCPs.")
