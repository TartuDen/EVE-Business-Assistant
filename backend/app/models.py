from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["conservative", "normal", "aggressive"]
RiskBadge = Literal["Low", "Medium", "High"]


class MarketScanRequest(BaseModel):
    starting_capital: float = Field(default=365_000_000, ge=1)
    region_id: int = 10000002
    station_id: int = 60003760
    max_isk_per_item: float = Field(default=75_000_000, ge=0)
    minimum_daily_volume: int = Field(default=20, ge=1)
    minimum_margin_percent: float = Field(default=5, ge=0)
    minimum_expected_profit: float = Field(default=500_000, ge=0)
    risk_level: RiskLevel = "normal"
    result_limit: int = Field(default=50, ge=1, le=100)


class MarketOpportunity(BaseModel):
    type_id: int
    item_name: str
    buy_price: float
    sell_price: float
    spread: float
    estimated_broker_fee: float
    estimated_sales_tax: float
    net_margin_percent: float
    daily_volume: int
    competition_level: str
    recommended_buy_price: float
    recommended_sell_price: float
    suggested_quantity: int
    required_isk: float
    expected_profit: float
    risk: RiskBadge
    score: float
    reason: str
    action: str


class MarketScanResponse(BaseModel):
    scanned_at: datetime
    source: str
    total_orders_seen: int
    total_station_orders: int
    opportunities: list[MarketOpportunity]


class PortfolioPositionCreate(BaseModel):
    item_name: str = Field(min_length=1)
    type_id: int | None = None
    quantity: int = Field(ge=1)
    buy_price: float = Field(ge=0)
    sell_price_target: float = Field(ge=0)
    sold_price: float | None = Field(default=None, ge=0)
    notes: str = ""


class PortfolioPosition(PortfolioPositionCreate):
    id: int
    status: Literal["open", "closed"]
    created_at: datetime
    updated_at: datetime
    profit_loss: float


class PortfolioSummary(BaseModel):
    total_liquid_isk: float
    isk_invested: float
    open_positions: int
    realized_profit: float
    roi_percent: float
    best_item: str | None
    worst_item: str | None
    positions: list[PortfolioPosition]


class SettingsPayload(BaseModel):
    total_liquid_isk: float = Field(default=365_000_000, ge=0)
    broker_fee_rate: float = Field(default=0.03, ge=0, le=0.2)
    sales_tax_rate: float = Field(default=0.08, ge=0, le=0.2)
