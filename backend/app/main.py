from __future__ import annotations

import csv
from io import StringIO

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse

from .character_progression import (
    analyze_character,
    authenticated_character_data,
    create_login_url,
    disconnect_character,
    exchange_code_for_token,
    get_profile,
    load_profiles,
    remove_plan,
    save_plan,
    saved_plans,
    session_summary,
)
from .config import settings
from .database import (
    create_position,
    delete_position,
    get_settings,
    init_db,
    list_positions,
    save_settings,
    update_position,
)
from .models import (
    MarketScanRequest,
    MarketScanResponse,
    PortfolioPosition,
    PortfolioPositionCreate,
    PortfolioSummary,
    SettingsPayload,
)
from .scanner import scan_market


app = FastAPI(title="EVE Business Assistant API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

last_scan: MarketScanResponse | None = None


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/market/scan", response_model=MarketScanResponse)
async def market_scan(payload: MarketScanRequest) -> MarketScanResponse:
    global last_scan
    last_scan = await scan_market(payload)
    return last_scan


@app.get("/api/market/export.csv")
def export_market_csv() -> StreamingResponse:
    if last_scan is None:
        raise HTTPException(status_code=404, detail="Run a market scan before exporting CSV.")

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Item",
            "Category",
            "Buy Price",
            "Sell Price",
            "Net Margin %",
            "30d Volume",
            "Order Count",
            "Suggested Quantity",
            "Required ISK",
            "Expected Profit",
            "Risk",
            "Manipulation Risk",
            "Why Recommended",
            "Score",
        ]
    )
    for item in last_scan.opportunities:
        writer.writerow(
            [
                item.item_name,
                item.category,
                item.recommended_buy_price,
                item.recommended_sell_price,
                item.net_margin_percent,
                item.avg_daily_volume_30d,
                item.buy_order_count + item.sell_order_count,
                item.suggested_quantity,
                item.required_isk,
                item.expected_profit,
                item.risk,
                item.manipulation_risk_score,
                item.reason,
                item.score,
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=eve-market-opportunities.csv"},
    )


@app.get("/api/portfolio", response_model=PortfolioSummary)
def get_portfolio() -> PortfolioSummary:
    positions = list_positions()
    settings = get_settings()
    open_positions = [position for position in positions if position.status == "open"]
    closed_positions = [position for position in positions if position.status == "closed"]
    invested = sum(position.quantity * position.buy_price for position in open_positions)
    realized = sum(position.profit_loss for position in closed_positions)
    closed_cost = sum(position.quantity * position.buy_price for position in closed_positions)
    roi = (realized / closed_cost * 100) if closed_cost else 0.0
    best = max(closed_positions, key=lambda position: position.profit_loss, default=None)
    worst = min(closed_positions, key=lambda position: position.profit_loss, default=None)
    return PortfolioSummary(
        total_liquid_isk=settings.total_liquid_isk,
        isk_invested=invested,
        open_positions=len(open_positions),
        realized_profit=realized,
        roi_percent=roi,
        best_item=best.item_name if best else None,
        worst_item=worst.item_name if worst else None,
        positions=positions,
    )


@app.post("/api/portfolio", response_model=PortfolioPosition)
def add_portfolio_position(payload: PortfolioPositionCreate) -> PortfolioPosition:
    return create_position(payload)


@app.put("/api/portfolio/{position_id}", response_model=PortfolioPosition)
def edit_portfolio_position(position_id: int, payload: PortfolioPositionCreate) -> PortfolioPosition:
    position = update_position(position_id, payload)
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found.")
    return position


@app.delete("/api/portfolio/{position_id}")
def remove_portfolio_position(position_id: int) -> dict[str, bool]:
    deleted = delete_position(position_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Position not found.")
    return {"deleted": True}


@app.get("/api/settings", response_model=SettingsPayload)
def read_settings() -> SettingsPayload:
    return get_settings()


@app.put("/api/settings", response_model=SettingsPayload)
def write_settings(payload: SettingsPayload) -> SettingsPayload:
    return save_settings(payload)


@app.get("/api/character/session")
def character_session() -> dict:
    return session_summary()


@app.get("/api/character/login")
def character_login() -> dict:
    return create_login_url()


@app.get("/api/character/callback")
async def character_callback(code: str, state: str) -> RedirectResponse:
    await exchange_code_for_token(code, state)
    return RedirectResponse(f"{settings.frontend_base_url}?character_login=success")


@app.post("/api/character/disconnect/{character_id}")
def character_disconnect(character_id: int) -> dict[str, bool]:
    return {"deleted": disconnect_character(character_id)}


@app.get("/api/character/profiles")
def character_profiles() -> list[dict]:
    return load_profiles()


@app.get("/api/character/profiles/{profile_id}")
def character_profile(profile_id: str) -> dict:
    return get_profile(profile_id)


@app.get("/api/character/analysis")
async def character_analysis(profile_id: str = "safe_jita_trader", character_id: int | None = None) -> dict:
    payload = await authenticated_character_data(character_id)
    return analyze_character(payload, profile_id)


@app.get("/api/character/saved-plans")
def character_saved_plans() -> list[dict]:
    return saved_plans()


@app.post("/api/character/saved-plans")
def character_save_plan(payload: dict) -> dict:
    return save_plan(payload)


@app.delete("/api/character/saved-plans/{plan_id}")
def character_delete_plan(plan_id: int) -> dict[str, bool]:
    deleted = remove_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved plan not found.")
    return {"deleted": True}
