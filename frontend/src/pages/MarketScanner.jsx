import React from "react";
import { Download, PlayCircle } from "lucide-react";
import { useState } from "react";
import { ItemDrawer } from "../components/ItemDrawer.jsx";
import { RiskBadge } from "../components/RiskBadge.jsx";
import { api, formatIsk } from "../lib/api.js";

const defaultFilters = {
  safe_mode: true,
  starting_capital: 365000000,
  region_id: 10000002,
  station_id: 60003760,
  max_isk_per_item: 25000000,
  minimum_daily_volume: 500,
  minimum_margin_percent: 4,
  maximum_margin_percent: 25,
  minimum_expected_profit: 100000,
  risk_level: "normal",
  result_limit: 50,
};

export function MarketScanner({ settings, scanResult, setScanResult, setError }) {
  const [filters, setFilters] = useState({
    ...defaultFilters,
    starting_capital: settings?.total_liquid_isk ?? defaultFilters.starting_capital,
  });
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);

  function update(field, value) {
    setFilters((current) => ({ ...current, [field]: value }));
  }

  async function scan() {
    setLoading(true);
    setError("");
    try {
      const payload = {
        ...filters,
        starting_capital: Number(filters.starting_capital),
        max_isk_per_item: Number(filters.max_isk_per_item),
        minimum_daily_volume: Number(filters.minimum_daily_volume),
        minimum_margin_percent: Number(filters.minimum_margin_percent),
        maximum_margin_percent: Number(filters.maximum_margin_percent),
        minimum_expected_profit: Number(filters.minimum_expected_profit),
        result_limit: Number(filters.result_limit),
      };
      const data = await api.scanMarket(payload);
      setScanResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[300px_1fr]">
      <aside className="rounded-lg border border-line bg-panel p-4 xl:sticky xl:top-4 xl:self-start">
        <h2 className="text-base font-semibold text-white">Filters</h2>
        <div className="mt-4 space-y-4">
          <label className="flex items-center justify-between gap-3 rounded-md border border-line bg-hull px-3 py-2 text-sm text-slate-200">
            <span>Beginner safe mode</span>
            <input
              type="checkbox"
              checked={filters.safe_mode}
              onChange={(event) => update("safe_mode", event.target.checked)}
              className="h-4 w-4 accent-cyan"
            />
          </label>
          <NumberInput label="Starting capital" value={filters.starting_capital} onChange={(value) => update("starting_capital", value)} />
          <NumberInput label="Max ISK per item" value={filters.max_isk_per_item} onChange={(value) => update("max_isk_per_item", value)} />
          <NumberInput label="Minimum daily volume" value={filters.minimum_daily_volume} onChange={(value) => update("minimum_daily_volume", value)} />
          <NumberInput label="Minimum margin %" value={filters.minimum_margin_percent} onChange={(value) => update("minimum_margin_percent", value)} />
          <NumberInput label="Maximum margin %" value={filters.maximum_margin_percent} onChange={(value) => update("maximum_margin_percent", value)} />
          <NumberInput label="Minimum expected profit" value={filters.minimum_expected_profit} onChange={(value) => update("minimum_expected_profit", value)} />
          <label className="block">
            <span className="text-sm text-slate-300">Risk level</span>
            <select
              value={filters.risk_level}
              onChange={(event) => update("risk_level", event.target.value)}
              className="mt-1 w-full rounded-md border border-line bg-hull px-3 py-2 text-sm text-white outline-none focus:border-cyan"
            >
              <option value="conservative">Conservative</option>
              <option value="normal">Normal</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </label>
          <button
            onClick={scan}
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-md bg-cyan px-4 py-3 font-semibold text-hull disabled:cursor-not-allowed disabled:opacity-60"
          >
            <PlayCircle size={19} />
            {loading ? "Scanning..." : "Scan Market"}
          </button>
          {scanResult?.opportunities?.length ? (
            <a
              className="flex w-full items-center justify-center gap-2 rounded-md border border-line px-4 py-3 text-sm text-slate-200 hover:border-cyan hover:text-cyan"
              href={api.csvUrl()}
            >
              <Download size={17} />
              Export CSV
            </a>
          ) : null}
        </div>
      </aside>

      <section className="min-w-0">
        <div className="mb-3 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-white">Jita recommendations</h2>
            <p className="mt-1 text-sm text-slate-400">
              {scanResult
                ? `${scanResult.opportunities.length} opportunities from ${formatIsk(scanResult.total_station_orders)} Jita 4-4 orders`
                : "Run a scan to load public ESI market data."}
            </p>
          </div>
          <div className="text-sm text-slate-500">The Forge / Jita 4-4</div>
        </div>

        <div className="overflow-hidden rounded-lg border border-line bg-panel">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1220px] text-left text-sm">
              <thead className="border-b border-line bg-hull text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-3 py-3">Item</th>
                  <th className="px-3 py-3">Category</th>
                  <th className="px-3 py-3">Buy Price</th>
                  <th className="px-3 py-3">Sell Price</th>
                  <th className="px-3 py-3">Net Margin %</th>
                  <th className="px-3 py-3">30d Volume</th>
                  <th className="px-3 py-3">Order Count</th>
                  <th className="px-3 py-3">Suggested Qty</th>
                  <th className="px-3 py-3">Required ISK</th>
                  <th className="px-3 py-3">Expected Profit</th>
                  <th className="px-3 py-3">Risk</th>
                  <th className="px-3 py-3">Why Recommended</th>
                </tr>
              </thead>
              <tbody>
                {(scanResult?.opportunities ?? []).map((item) => (
                  <tr
                    key={item.type_id}
                    className="cursor-pointer border-b border-line/70 hover:bg-cyan/6"
                    onClick={() => setSelected(item)}
                  >
                    <td className="px-3 py-3 font-medium text-white">{item.item_name}</td>
                    <td className="px-3 py-3 text-slate-400">{item.category}</td>
                    <td className="px-3 py-3 text-slate-300">{formatIsk(item.recommended_buy_price)}</td>
                    <td className="px-3 py-3 text-slate-300">{formatIsk(item.recommended_sell_price)}</td>
                    <td className="px-3 py-3 text-mint">{item.net_margin_percent.toFixed(2)}%</td>
                    <td className="px-3 py-3 text-slate-300">{formatIsk(item.avg_daily_volume_30d)}</td>
                    <td className="px-3 py-3 text-slate-300">{formatIsk(item.buy_order_count + item.sell_order_count)}</td>
                    <td className="px-3 py-3 text-slate-300">{formatIsk(item.suggested_quantity)}</td>
                    <td className="px-3 py-3 text-slate-300">{formatIsk(item.required_isk, true)}</td>
                    <td className="px-3 py-3 text-mint">{formatIsk(item.expected_profit, true)}</td>
                    <td className="px-3 py-3"><RiskBadge risk={item.risk} /></td>
                    <td className="max-w-[320px] px-3 py-3 text-slate-400">{item.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!scanResult?.opportunities?.length ? (
            <div className="px-4 py-12 text-center text-sm text-slate-400">
              No scan results yet. Public ESI scans can take a little while because market orders are paginated.
            </div>
          ) : null}
        </div>
      </section>

      <ItemDrawer item={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function NumberInput({ label, value, onChange }) {
  return (
    <label className="block">
      <span className="text-sm text-slate-300">{label}</span>
      <input
        type="number"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-md border border-line bg-hull px-3 py-2 text-sm text-white outline-none focus:border-cyan"
      />
    </label>
  );
}
