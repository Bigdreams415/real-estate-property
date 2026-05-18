from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # App
    APP_NAME: str = os.getenv("APP_NAME", "Property Management API")
    DEBUG: bool = os.getenv("DEBUG", "True") == "True"

    # Paystack
    PAYSTACK_SECRET_KEY: str = ""
    APP_BASE_URL: str = "http://localhost:8000"

    # Google OAuth — client IDs from Firebase/Google Cloud console
    GOOGLE_CLIENT_ID_ANDROID: str = os.getenv("GOOGLE_CLIENT_ID_ANDROID", "")
    GOOGLE_CLIENT_ID_IOS: str = os.getenv("GOOGLE_CLIENT_ID_IOS", "")
    GOOGLE_CLIENT_ID_WEB: str = os.getenv("GOOGLE_CLIENT_ID_WEB", "")

    # BulkSMS Nigeria
    BULKSMS_NIGERIA_API_TOKEN: str = os.getenv("BULKSMS_NIGERIA_API_TOKEN", "")
    BULKSMS_NIGERIA_SENDER_ID: str = os.getenv("BULKSMS_NIGERIA_SENDER_ID", "RentalGuide")

settings = Settings()