"""
scripts/create_admin.py

Run this once from your project root to create the first admin user:

    python -m scripts.create_admin

You will be prompted for name, email, phone, and password.
The user will be created with full admin capabilities.
"""

import sys
import os

# Make sure app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.user import User
from app.utils.auth import get_password_hash


ADMIN_CAPABILITIES = [
    "browse_properties",
    "save_favorites",
    "create_listing",
    "admin_access",
    "manage_users",
    "verify_properties",
]


def create_admin():
    print("\n── Create Admin User ─────────────────────")

    full_name    = input("Full name:      ").strip()
    email        = input("Email:          ").strip()
    phone_number = input("Phone (+234...): ").strip()
    password     = input("Password:       ").strip()

    if not all([full_name, email, phone_number, password]):
        print("❌ All fields are required.")
        sys.exit(1)

    if len(password) < 8:
        print("❌ Password must be at least 8 characters.")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Check for duplicates
        if db.query(User).filter(User.email == email).first():
            print(f"❌ Email '{email}' is already registered.")
            sys.exit(1)

        if db.query(User).filter(User.phone_number == phone_number).first():
            print(f"❌ Phone '{phone_number}' is already registered.")
            sys.exit(1)

        admin = User(
            full_name=full_name,
            email=email,
            phone_number=phone_number,
            password_hash=get_password_hash(password),
            capabilities=ADMIN_CAPABILITIES,
            verification_level="verified",
            city="Benin City",      # defaults — admin doesn't need a Nigerian address
            state="Edo State",
            is_active=True,
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print(f"\n✅ Admin user created successfully!")
        print(f"   ID:    {admin.id}")
        print(f"   Name:  {admin.full_name}")
        print(f"   Email: {admin.email}")
        print(f"   Caps:  {', '.join(admin.capabilities)}")
        print(f"\nYou can now log in at your admin dashboard.\n")

    except Exception as e:
        db.rollback()
        print(f"❌ Failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()