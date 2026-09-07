"""Seed script to populate initial demo enforcement officers in the database."""
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import SessionLocal
from app.db.models.officer import Officer

DEMO_OFFICERS = [
    {
        "name": "Inspector Rajesh Sharma",
        "email": "rajesh.sharma@nic.in",
        "badge_number": "LM-DEL-042",
        "jurisdiction": "South Delhi District",
        "password": "officer123",
    },
    {
        "name": "Inspector Priya Verma",
        "email": "priya.verma@nic.in",
        "badge_number": "LM-MUM-108",
        "jurisdiction": "Mumbai Suburban Division",
        "password": "officer123",
    },
]


def seed_demo_officers(db: Session | None = None) -> list[Officer]:
    """Idempotently seed demo enforcement officer accounts."""
    should_close = False
    if db is None:
        if SessionLocal is None:
            raise RuntimeError("Database not configured. Set DATABASE_URL in .env.")
        db = SessionLocal()
        should_close = True

    created: list[Officer] = []
    try:
        for officer_data in DEMO_OFFICERS:
            existing = (
                db.query(Officer)
                .filter(Officer.email == officer_data["email"])
                .first()
            )
            if not existing:
                officer = Officer(
                    name=officer_data["name"],
                    email=officer_data["email"],
                    badge_number=officer_data.get("badge_number"),
                    jurisdiction=officer_data["jurisdiction"],
                    hashed_password=hash_password(officer_data["password"]),
                )
                db.add(officer)
                created.append(officer)
        db.commit()
        for off in created:
            db.refresh(off)
            db.expunge(off)
        return created
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    print("Seeding demo officers into database...")
    officers = seed_demo_officers()
    if officers:
        print(f"Successfully seeded {len(officers)} new officer accounts:")
        for off in officers:
            print(f"  - {off.name} ({off.email}) [{off.jurisdiction}]")
    else:
        print("Demo officers already exist in the database.")
