from __future__ import annotations

import csv
from io import StringIO

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
            "Buy Price",
            "Sell Price",
            "Margin %",
            "Daily Volume",
            "Suggested Quantity",
            "Required ISK",
            "Expected Profit",
            "Risk",
            "Score",
        ]
    )
    for item in last_scan.opportunities:
        writer.writerow(
            [
                item.item_name,
                item.recommended_buy_price,
                item.recommended_sell_price,
                item.net_margin_percent,
                item.daily_volume,
                item.suggested_quantity,
                item.required_isk,
                item.expected_profit,
                item.risk,
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
