# Real Estate Property Listing API

A production-ready RESTful backend API for a real estate property management platform. Built with Python and FastAPI, this backend powers property listings, user authentication, media uploads, admin verification workflows, and more.

---

## Tech Stack

- **Framework:** FastAPI (Python)
- **ORM:** SQLAlchemy
- **Database:** SQLite (easily swappable to PostgreSQL)
- **Validation:** Pydantic
- **Authentication:** JWT (JSON Web Tokens)
- **Media Storage:** Local file storage with static file serving
- **Environment Config:** python-dotenv

---

## Features

### Property Management
- Create, read, update, and delete property listings
- Support for multiple property types and listing types (sale, rent, etc.)
- Multi-image upload per property with captions and display ordering
- External video URL support (YouTube / Vimeo)
- Property features list, bedroom/bathroom/toilet counts, square meters, and plot size
- View count tracking per property
- Smart search with relevance scoring across title, address, city, state, landmark, LGA, and description
- Filter by state, city, property type, listing type, price range, and bedroom count
- Sort by newest, oldest, price low, price high, most viewed, or relevance

### Authentication and Authorization
- JWT-based user authentication
- Secure token generation and decoding
- Capability-based access control (e.g. create_listing, admin_access)
- Separate admin authentication router
- Active user verification checks

### Property Verification Workflow
- Properties submitted for listing enter a PENDING_VERIFICATION state
- Admins review ownership documents uploaded by the property owner
- Admins can approve or reject listings with optional notes
- Rejected properties can resubmit updated ownership documents
- Verification status resets automatically when documents are updated

### Admin Panel Endpoints
- List all pending verification properties
- Approve or reject individual property listings
- Timestamped audit trail of who verified each property and when

### User Management
- User models with ID, active status, capabilities, and verification level
- User verification router for identity or document verification flows

### Media Handling
- Property images saved to disk and served via /media static endpoint
- Captions and display order stored per image
- Images replaced cleanly on property update without orphaned files

### Developer Utilities
- Health check endpoint
- Database connection test script (test_db.py)
- Admin user creation script (scripts/create_admin.py)
- CORS middleware configured for cross-origin frontend access

---

## Project Structure

```
├── app/
│   ├── api/
│   │   └── deps.py              # Auth dependencies (get_current_user, capability checks)
│   ├── core/
│   │   ├── config.py            # App settings loaded from environment variables
│   │   └── database.py          # SQLAlchemy engine, session, and base setup
│   ├── models/
│   │   ├── base.py              # Shared base model
│   │   ├── property.py          # Property, PropertyImage, PropertyVideo ORM models
│   │   └── user.py              # User ORM model
│   ├── routers/
│   │   ├── auth.py              # Standard user authentication endpoints
│   │   ├── admin_auth.py        # Admin-specific authentication endpoints
│   │   ├── properties.py        # Full property CRUD and admin verification endpoints
│   │   └── verification.py      # User and property verification workflows
│   ├── schemas/
│   │   ├── property.py          # Pydantic schemas for property requests and responses
│   │   ├── user.py              # Pydantic schemas for user data
│   │   └── verification.py      # Pydantic schemas for verification actions
│   ├── utils/
│   │   ├── auth.py              # JWT encoding and decoding helpers
│   │   └── file_storage.py      # Media upload and deletion utilities
│   └── main.py                  # FastAPI app entry point, router registration, static mount
├── scripts/
│   └── create_admin.py          # Script to create an admin user
├── test_db.py                   # Database connection test
├── app.db                       # SQLite database file
└── .env                         # Environment variables (not committed)
```

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/Bigdreams415/real-estate-property.git
cd real-estate-property

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your settings
```

### Environment Variables

```env
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=your_jwt_secret_key
APP_NAME=Real Estate API
DEBUG=True
```

### Run the Application

```bash
uvicorn app.main:app --reload
```

API will be live at: http://localhost:8000

Interactive docs at: http://localhost:8000/docs

### Create an Admin User

```bash
python scripts/create_admin.py
```

---

## API Endpoints Overview

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /auth/login | User login, returns JWT token |
| POST | /admin/login | Admin login |

### Properties
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /properties/ | List all verified properties with filters |
| POST | /properties/ | Create a new property listing |
| GET | /properties/{id} | Get a single property (increments view count) |
| PUT | /properties/{id} | Update a property listing |
| GET | /properties/admin/pending | List pending verification properties (Admin only) |
| POST | /properties/admin/{id}/verify | Approve or reject a property (Admin only) |

### Media
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /media/{filename} | Serve uploaded property images |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check endpoint |

---

## Key Design Decisions

- **Capability-based auth** instead of simple role checks makes the permission system flexible and easy to extend
- **Multipart form data** on property creation supports simultaneous text fields and image uploads in a single request, designed to work seamlessly with Flutter frontends
- **Verification workflow** ensures every property listing is reviewed by an admin before going live, protecting platform integrity
- **Relevance-scored search** weights matches by field importance so the most relevant results always surface first

---

## Author

**Bigdreams415**
[GitHub](https://github.com/Bigdreams415)