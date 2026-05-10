from __future__ import annotations

import os
from dataclasses import dataclass


THE_FORGE_REGION_ID = 10000002
JITA_4_4_LOCATION_ID = 60003760


@dataclass(frozen=True)
class Settings:
    app_name: str = "EVE Business Assistant"
    database_path: str = os.getenv("EBA_DATABASE_PATH", "eve_business_assistant.sqlite3")
    esi_base_url: str = os.getenv("EBA_ESI_BASE_URL", "https://esi.evetech.net/latest")
    esi_user_agent: str = os.getenv(
        "EBA_ESI_USER_AGENT",
        "EVE-Business-Assistant/0.1 local decision-support tool",
    )
    market_max_pages: int = int(os.getenv("EBA_MARKET_MAX_PAGES", "0"))
    request_timeout_seconds: float = float(os.getenv("EBA_REQUEST_TIMEOUT_SECONDS", "20"))
    broker_fee_rate: float = float(os.getenv("EBA_BROKER_FEE_RATE", "0.03"))
    sales_tax_rate: float = float(os.getenv("EBA_SALES_TAX_RATE", "0.08"))


settings = Settings()
