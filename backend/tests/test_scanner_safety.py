from __future__ import annotations

import unittest

from app.safety import (
    FeeRates,
    HistoryStats,
    ItemMetadata,
    MarketOrder,
    OrderBook,
    SafetyFilters,
    calculate_fees,
    evaluate_opportunity,
    suggested_quantity,
)


FEES = FeeRates(broker_fee_rate=0.03, sales_tax_rate=0.08)
FILTERS = SafetyFilters()
LIQUID_ISK = 365_000_000


def book(type_id: int, buy_price: float, sell_price: float, buy_count: int = 12, sell_count: int = 12, volume: int = 500) -> OrderBook:
    buy_orders = tuple(MarketOrder(price=buy_price - idx * 0.01, volume=volume) for idx in range(buy_count))
    sell_orders = tuple(MarketOrder(price=sell_price + idx * 0.01, volume=volume) for idx in range(sell_count))
    return OrderBook(type_id=type_id, buy_orders=buy_orders, sell_orders=sell_orders)


def stats(volume: int = 1_000, median_price: float = 115, volatility: float = 0.05, days: int = 30) -> HistoryStats:
    return HistoryStats(
        avg_daily_volume_30d=volume,
        median_daily_volume_30d=volume,
        avg_price_30d=median_price,
        median_price_30d=median_price,
        avg_price_7d=median_price,
        price_volatility_30d=volatility,
        days_traded_30d=days,
    )


class ScannerSafetyTests(unittest.TestCase):
    def test_margin_and_fee_calculation(self) -> None:
        result = calculate_fees(100, 125, FEES)
        self.assertAlmostEqual(result.broker_fee_buy, 3)
        self.assertAlmostEqual(result.broker_fee_sell, 3.75)
        self.assertAlmostEqual(result.sales_tax, 10)
        self.assertAlmostEqual(result.net_profit_per_unit, 8.25)
        self.assertAlmostEqual(result.margin_percent, 8.25)
        self.assertGreater(result.break_even_sell_price, 100)

    def test_quantity_calculation_uses_conservative_limits(self) -> None:
        quantity = suggested_quantity(stats(), 100, LIQUID_ISK, 10_000, 10_000, FILTERS, FEES)
        self.assertEqual(quantity, 50)

    def test_safe_item_accepted(self) -> None:
        result = evaluate_opportunity(
            book(1, 1_000, 1_250, volume=20_000),
            ItemMetadata(name="Antimatter Charge M", category="Charge", group="Hybrid Charge"),
            stats(volume=50_000, median_price=1_150),
            FILTERS,
            FEES,
            LIQUID_ISK,
        )
        self.assertIsNotNone(result)
        self.assertIn(result.risk, {"Low", "Medium"})

    def test_event_firework_item_rejected(self) -> None:
        result = evaluate_opportunity(
            book(2, 100, 125),
            ItemMetadata(name="Zakura Bazei Firework", category="Charge", group="Festival Charge"),
            stats(),
            FILTERS,
            FEES,
            LIQUID_ISK,
        )
        self.assertIsNone(result)

    def test_low_volume_rejected(self) -> None:
        result = evaluate_opportunity(
            book(3, 100, 125),
            ItemMetadata(name="Expensive Low Volume Module", category="Module", group="Shield Module"),
            stats(volume=25),
            FILTERS,
            FEES,
            LIQUID_ISK,
        )
        self.assertIsNone(result)

    def test_high_margin_rejected_in_safe_mode(self) -> None:
        result = evaluate_opportunity(
            book(4, 100, 150),
            ItemMetadata(name="Suspicious Module", category="Module", group="Armor Module"),
            stats(median_price=125),
            FILTERS,
            FEES,
            LIQUID_ISK,
        )
        self.assertIsNone(result)

    def test_manipulated_one_order_item_rejected(self) -> None:
        result = evaluate_opportunity(
            book(5, 100, 125, buy_count=1, sell_count=1, volume=2),
            ItemMetadata(name="Thin Order Module", category="Module", group="Armor Module"),
            stats(),
            FILTERS,
            FEES,
            LIQUID_ISK,
        )
        self.assertIsNone(result)

    def test_mocked_set_accepts_only_safe_ammo_and_normal_module(self) -> None:
        cases = [
            (
                "A",
                book(10, 1_000, 1_250, volume=20_000),
                ItemMetadata(name="Antimatter Charge M", category="Charge", group="Hybrid Charge"),
                stats(volume=50_000, median_price=1_150),
            ),
            (
                "B",
                book(11, 100, 150),
                ItemMetadata(name="Zakura Bazei Firework", category="Charge", group="Festival Charge"),
                stats(median_price=125),
            ),
            (
                "C",
                book(12, 10_000_000, 11_500_000, volume=20),
                ItemMetadata(name="Expensive Rare Module", category="Module", group="Armor Module"),
                stats(volume=15, median_price=10_800_000),
            ),
            (
                "D",
                book(13, 100, 125, buy_count=1, sell_count=1, volume=2),
                ItemMetadata(name="Manipulated Module", category="Module", group="Shield Module"),
                stats(),
            ),
            (
                "E",
                book(14, 10_000, 12_600, volume=350),
                ItemMetadata(name="Adaptive Invulnerability Field I", category="Module", group="Shield Module"),
                stats(volume=3_000, median_price=11_700, volatility=0.18),
            ),
        ]
        accepted = [
            label
            for label, order_book, metadata, history in cases
            if evaluate_opportunity(order_book, metadata, history, FILTERS, FEES, LIQUID_ISK) is not None
        ]
        self.assertEqual(accepted, ["A", "E"])


if __name__ == "__main__":
    unittest.main()
