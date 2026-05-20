"""
Backfill latitude/longitude for properties that have no coordinates.
Uses Nominatim (OpenStreetMap) — throttled to ~1 req/sec per their usage policy.
Safe to re-run: only touches rows where latitude IS NULL.

Usage:
    cd /Users/bigdreams/Workspace/property/backend
    python scripts/backfill_property_coordinates.py
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.property import Property
from app.services.geocoding_service import geocode_address


BATCH_SIZE = 20


async def run():
    db: Session = next(get_db())

    total = db.query(Property).filter(Property.latitude.is_(None)).count()
    print(f"Properties without coordinates: {total}")

    if total == 0:
        print("Nothing to backfill.")
        return

    processed = 0
    updated = 0
    failed = 0

    offset = 0
    while True:
        batch = (
            db.query(Property)
            .filter(Property.latitude.is_(None))
            .order_by(Property.created_at.asc())
            .offset(offset)
            .limit(BATCH_SIZE)
            .all()
        )
        if not batch:
            break

        for prop in batch:
            lat, lng = await geocode_address(
                prop.address or "",
                prop.city or "",
                prop.state or "",
                prop.lga or "",
            )
            processed += 1
            if lat is not None:
                prop.latitude = lat
                prop.longitude = lng
                updated += 1
                print(f"  [{processed}/{total}] {prop.title[:40]!r} → ({lat:.4f}, {lng:.4f})")
            else:
                failed += 1
                print(f"  [{processed}/{total}] {prop.title[:40]!r} → no result")

            # Nominatim usage policy: max 1 request/second
            time.sleep(1.1)

        db.commit()
        offset += BATCH_SIZE

    db.close()
    print(f"\nDone. Updated: {updated}, No result: {failed}, Total: {processed}")


if __name__ == "__main__":
    asyncio.run(run())
