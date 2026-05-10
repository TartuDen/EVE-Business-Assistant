import React from "react";
import { Save } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

export function SettingsPage({ settings, onSaved, setError }) {
  const [form, setForm] = useState({
    total_liquid_isk: 365000000,
    broker_fee_rate: 0.03,
    sales_tax_rate: 0.08,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function save(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        total_liquid_isk: Number(form.total_liquid_isk),
        broker_fee_rate: Number(form.broker_fee_rate),
        sales_tax_rate: Number(form.sales_tax_rate),
      };
      const saved = await api.saveSettings(payload);
      onSaved(saved);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save} className="max-w-2xl rounded-lg border border-line bg-panel p-5">
      <h2 className="text-lg font-semibold text-white">Settings</h2>
      <p className="mt-2 text-sm leading-6 text-slate-400">
        Tune wallet and fee assumptions. These values only affect recommendations and portfolio summaries.
      </p>

      <div className="mt-5 grid gap-4">
        <NumberInput label="Total liquid ISK" value={form.total_liquid_isk} onChange={(value) => update("total_liquid_isk", value)} />
        <NumberInput label="Broker fee rate" value={form.broker_fee_rate} step="0.001" onChange={(value) => update("broker_fee_rate", value)} />
        <NumberInput label="Sales tax rate" value={form.sales_tax_rate} step="0.001" onChange={(value) => update("sales_tax_rate", value)} />
      </div>

      <button
        disabled={saving}
        className="mt-5 inline-flex items-center gap-2 rounded-md bg-cyan px-4 py-3 font-semibold text-hull disabled:opacity-60"
      >
        <Save size={18} />
        Save Settings
      </button>
    </form>
  );
}

function NumberInput({ label, value, onChange, step = "1" }) {
  return (
    <label className="block">
      <span className="text-sm text-slate-300">{label}</span>
      <input
        type="number"
        step={step}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-md border border-line bg-hull px-3 py-2 text-sm text-white outline-none focus:border-cyan"
      />
    </label>
  );
}
