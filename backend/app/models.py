from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["conservative", "normal", "aggressive"]
RiskBadge = Literal["Low", "Medium", "High", "Avoid"]


class MarketScanRequest(BaseModel):
    safe_mode: bool = True
    starting_capital: float = Field(default=365_000_000, ge=1)
    region_id: int = 10000002
    station_id: int = 60003760
    max_isk_per_item: float = Field(default=25_000_000, ge=0)
    minimum_daily_volume: int = Field(default=500, ge=1)
    minimum_order_count: int = Field(default=20, ge=1)
    minimum_sell_order_count: int = Field(default=10, ge=1)
    minimum_buy_order_count: int = Field(default=10, ge=1)
    minimum_margin_percent: float = Field(default=4, ge=0)
    maximum_margin_percent: float = Field(default=25, ge=0)
    minimum_expected_profit: float = Field(default=100_000, ge=0)
    minimum_price: float = Field(default=1_000, ge=0)
    exclude_single_unit_orders: bool = True
    exclude_event_items: bool = True
    exclude_skins: bool = True
    exclude_fireworks: bool = True
    exclude_blueprints: bool = True
    exclude_contract_only_items: bool = True
    risk_level: RiskLevel = "normal"
    result_limit: int = Field(default=50, ge=1, le=100)


class MarketOpportunity(BaseModel):
    type_id: int
    item_name: str
    category: str
    buy_price: float
    sell_price: float
    spread: float
    estimated_broker_fee: float
    estimated_sales_tax: float
    net_margin_percent: float
    roi_percent: float
    daily_volume: int
    avg_daily_volume_30d: float
    median_daily_volume_30d: float
    avg_price_30d: float
    median_price_30d: float
    price_volatility_30d: float
    days_traded_30d: int
    competition_level: str
    recommended_buy_price: float
    recommended_sell_price: float
    expected_buy_price: float
    expected_sell_price: float
    depth_buy_price: float
    depth_sell_price: float
    buy_order_count: int
    sell_order_count: int
    buy_depth_5_percent: int
    sell_depth_5_percent: int
    top_buy_quantity: int
    top_sell_quantity: int
    suggested_quantity: int
    required_isk: float
    expected_profit: float
    profit_per_unit: float
    total_expected_profit: float
    break_even_sell_price: float
    manipulation_risk_score: float
    risk_score: float
    risk: RiskBadge
    score: float
    reason: str
    action: str
    warning: str


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
