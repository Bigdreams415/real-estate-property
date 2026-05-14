# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate virtual environment (required before any commands)
source venv/bin/activate

# Run development server
uvicorn app.main:app --reload

# Run database migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "describe change"

# Create an admin user
python scripts/create_admin.py

# Test database connection
python app/test_db.py
```

API docs available at `http://localhost:8000/docs` when server is running.

## Environment Variables

Required in `.env`:
```
DATABASE_URL=postgresql://...   # or sqlite:///./app.db for local dev
SECRET_KEY=...
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=...
PAYSTACK_SECRET_KEY=...
APP_BASE_URL=http://localhost:8000
```

## Architecture

**FastAPI** app with **SQLAlchemy** ORM, **Pydantic v2** schemas, **Alembic** migrations, and **PostgreSQL** (SQLite supported for local dev). All routes are prefixed `/api/v1`.

### Layer responsibilities

- `app/models/` — SQLAlchemy ORM models. All inherit `BaseModel` (`app/models/base.py`) which provides UUID primary key + `created_at`/`updated_at`. Note: `base.py` uses `sqlalchemy.dialects.postgresql.UUID` even when running SQLite — this works but is fragile.
- `app/schemas/` — Pydantic v2 request/response schemas, separate from ORM models.
- `app/routers/` — FastAPI route handlers. One file per domain.
- `app/api/deps.py` — Auth dependency injection. Use `get_current_active_user` for authenticated routes, `require_capability("capability_name")` for capability-gated routes.
- `app/utils/auth.py` — JWT encode/decode with `python-jose`, password hashing with `bcrypt`.
- `app/core/config.py` — `Settings` via `pydantic-settings`, reads from `.env`.
- `app/core/database.py` — SQLAlchemy engine + `get_db()` session dependency.

### Auth system

JWT tokens with capability-based access control. User capabilities are stored as a JSON array in `users.capabilities` (e.g. `["browse_properties", "create_listing", "admin_access"]`). `require_capability()` in `deps.py` wraps any route that needs a specific capability.

Verification levels (hierarchical): `unverified → phone_verified → identity_verified → landlord_verified`. Use `require_verification_level()` for level-gated routes.

### Property lifecycle

1. Property created → `verification_status = PENDING_VERIFICATION`
2. Owner uploads ownership documents
3. Admin reviews via `/api/v1/admin/properties/pending`
4. Admin approves/rejects → status becomes `VERIFIED` or `REJECTED`
5. Only `VERIFIED` properties appear in public listings

### Payment/escrow flow

Payments go through Paystack. On `POST /api/v1/payments/initiate`, a `Transaction` is created with status `PENDING` and a Paystack authorization URL returned. After the user pays, Paystack calls the webhook (`POST /api/v1/payments/webhook`) which moves the transaction to `IN_ESCROW`. The 72-hour escrow hold is tracked via `release_at`. Admins manually release via `POST /api/v1/payments/{id}/release`. Platform fee is 8% (`PLATFORM_FEE_PERCENT`).

### Media

Images uploaded as multipart form data, saved to `media/properties/` with UUID filenames, served as static files at `/media/`. `app/utils/file_storage.py` handles save/delete. The `media/` directory is created at startup if missing.

### Key design notes

- `app/main.py` has a duplicate router import line (lines 4–5) — the `favorites` import on line 4 and the `payments` import on line 5 partially overlap. Both lines are active; this is harmless but should be cleaned up.
- `Inspection` model uses `create_type=False` on the status Enum to avoid PostgreSQL type conflicts across migrations — do not remove this.
- All monetary amounts are stored in **Naira** (float); Paystack calls convert to kobo via `_kobo()`.
- Search relevance scoring in `properties.py` weights matches by field importance (title > city > address etc.) — this is application-level, not DB-level.
