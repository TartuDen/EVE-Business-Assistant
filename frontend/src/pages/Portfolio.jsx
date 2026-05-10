import React from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, formatIsk } from "../lib/api.js";

const emptyForm = {
  item_name: "",
  type_id: "",
  quantity: 1,
  buy_price: 0,
  sell_price_target: 0,
  sold_price: "",
  notes: "",
};

export function Portfolio({ portfolio, onChanged, setError }) {
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.addPosition({
        item_name: form.item_name,
        type_id: form.type_id ? Number(form.type_id) : null,
        quantity: Number(form.quantity),
        buy_price: Number(form.buy_price),
        sell_price_target: Number(form.sell_price_target),
        sold_price: form.sold_price === "" ? null : Number(form.sold_price),
        notes: form.notes,
      });
      setForm(emptyForm);
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id) {
    setError("");
    try {
      await api.deletePosition(id);
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
      <form onSubmit={submit} className="rounded-lg border border-line bg-panel p-4">
        <h2 className="text-base font-semibold text-white">Add manual position</h2>
        <div className="mt-4 grid gap-3">
          <TextInput label="Item bought" value={form.item_name} onChange={(value) => update("item_name", value)} required />
          <TextInput label="Type ID" value={form.type_id} onChange={(value) => update("type_id", value)} />
          <NumberInput label="Quantity" value={form.quantity} onChange={(value) => update("quantity", value)} />
          <NumberInput label="Buy price" value={form.buy_price} onChange={(value) => update("buy_price", value)} />
          <NumberInput label="Sell price target" value={form.sell_price_target} onChange={(value) => update("sell_price_target", value)} />
          <NumberInput label="Sold price" value={form.sold_price} onChange={(value) => update("sold_price", value)} placeholder="Leave blank while open" />
          <label className="block">
            <span className="text-sm text-slate-300">Notes</span>
            <textarea
              value={form.notes}
              onChange={(event) => update("notes", event.target.value)}
              className="mt-1 min-h-24 w-full rounded-md border border-line bg-hull px-3 py-2 text-sm text-white outline-none focus:border-cyan"
            />
          </label>
          <button
            disabled={saving}
            className="mt-1 inline-flex items-center justify-center gap-2 rounded-md bg-cyan px-4 py-3 font-semibold text-hull disabled:opacity-60"
          >
            <Plus size={18} />
            Add Position
          </button>
        </div>
      </form>

      <section className="min-w-0">
        <div className="mb-3 grid gap-3 md:grid-cols-4">
          <Metric label="Invested" value={`${formatIsk(portfolio?.isk_invested, true)} ISK`} />
          <Metric label="Open positions" value={portfolio?.open_positions ?? 0} />
          <Metric label="Realized profit" value={`${formatIsk(portfolio?.realized_profit, true)} ISK`} />
          <Metric label="ROI" value={`${(portfolio?.roi_percent ?? 0).toFixed(2)}%`} />
        </div>

        <div className="overflow-hidden rounded-lg border border-line bg-panel">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="border-b border-line bg-hull text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-3 py-3">Item</th>
                  <th className="px-3 py-3">Qty</th>
                  <th className="px-3 py-3">Buy</th>
                  <th className="px-3 py-3">Target</th>
                  <th className="px-3 py-3">Sold</th>
                  <th className="px-3 py-3">Profit/Loss</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(portfolio?.positions ?? []).map((position) => (
                  <tr key={position.id} className="border-b border-line/70">
                    <td className="px-3 py-3 font-medium text-white">{position.item_name}</td>
                    <td className="px-3 py-3 text-slate-300">{formatIsk(position.quantity)}</td>
                    <td className="px-3 py-3 text-slate-300">{formatIsk(position.buy_price)}</td>
                    <td className="px-3 py-3 text-slate-300">{formatIsk(position.sell_price_target)}</td>
                    <td className="px-3 py-3 text-slate-300">{position.sold_price == null ? "-" : formatIsk(position.sold_price)}</td>
                    <td className={`px-3 py-3 ${position.profit_loss >= 0 ? "text-mint" : "text-danger"}`}>
                      {formatIsk(position.profit_loss, true)}
                    </td>
                    <td className="px-3 py-3 text-slate-300">{position.status}</td>
                    <td className="px-3 py-3">
                      <button
                        onClick={() => remove(position.id)}
                        className="rounded-md border border-line p-2 text-slate-300 hover:border-danger hover:text-danger"
                        title="Delete position"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!portfolio?.positions?.length ? (
            <div className="px-4 py-12 text-center text-sm text-slate-400">
              Add trades manually as you buy and sell items.
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-lg border border-line bg-panel p-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-2 text-lg font-semibold text-white">{value}</div>
    </div>
  );
}

function TextInput({ label, value, onChange, required }) {
  return (
    <label className="block">
      <span className="text-sm text-slate-300">{label}</span>
      <input
        required={required}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-md border border-line bg-hull px-3 py-2 text-sm text-white outline-none focus:border-cyan"
      />
    </label>
  );
}

function NumberInput({ label, value, onChange, placeholder }) {
  return (
    <label className="block">
      <span className="text-sm text-slate-300">{label}</span>
      <input
        type="number"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-md border border-line bg-hull px-3 py-2 text-sm text-white outline-none focus:border-cyan"
      />
    </label>
  );
}
