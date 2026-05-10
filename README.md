# EVE Business Assistant

A local, legal EVE Online decision-support tool for solo Alpha players. It gathers public ESI market data, finds Jita station-trading opportunities, and tracks manual portfolio decisions. It never controls or automates the EVE client.

## Stack

- Backend: FastAPI, SQLite, httpx
- Frontend: React, Tailwind, Vite
- Data: public ESI market endpoints first; EVE SSO is reserved for a later phase

## Run locally

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Notes

- The scanner uses The Forge (`10000002`) and Jita 4-4 (`60003760`) by default.
- ESI market order data is cached by CCP and paginated. You can tune `EBA_MARKET_MAX_PAGES` for speed versus coverage. Set it to `0` to fetch every available page.
- Fees are configurable in Settings. Defaults are intentionally conservative for new traders.
- Phase 2 will add EVE SSO OAuth 2.0 for private character data. MVP does not require login.

## Legal boundary

This app only gives recommendations. It must not click, inject into, control, or automate the EVE client, and it must not automatically create buy or sell orders.
