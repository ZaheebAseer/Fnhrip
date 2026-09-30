import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
WORKSPACE_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
DATABASE_PATH = os.path.join(BASE_DIR, "fnhrip.db")

class Config:
    SECRET_KEY = os.environ.get("FNHRIP_SECRET_KEY")
    DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
    COUNTRY_CODE = "IND"
    COUNTRY_NAME = "National Health Grid"
    TIMEZONE = "UTC"
    CURRENCY = "USD"
    VERSION = "1.0.0-PROD-SPEC"
    
    # Alert thresholds
    CRITICAL_DAYS_OF_STOCK = 5.0
    WARNING_DAYS_OF_STOCK = 14.0
    EXPIRY_WARNING_DAYS = 30
    ICU_PRESSURE_THRESHOLD = 0.85
    
    # Offline sync batch size
    MAX_SYNC_BATCH = 100
