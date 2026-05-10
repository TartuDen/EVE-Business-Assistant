import React, { useEffect, useMemo, useState } from "react";
import { BarChart3, BriefcaseBusiness, Eye, Factory, Gauge, Settings, Star } from "lucide-react";
import { api, formatIsk } from "./lib/api.js";
import { Dashboard } from "./pages/Dashboard.jsx";
import { MarketScanner } from "./pages/MarketScanner.jsx";
import { Portfolio } from "./pages/Portfolio.jsx";
import { SettingsPage } from "./pages/SettingsPage.jsx";
import { Watchlist } from "./pages/Watchlist.jsx";
import { Manufacturing } from "./pages/Manufacturing.jsx";

const tabs = [
  { id: "dashboard", label: "Dashboard", icon: Gauge },
  { id: "scanner", label: "Market Scanner", icon: BarChart3 },
  { id: "portfolio", label: "Portfolio", icon: BriefcaseBusiness },
  { id: "watchlist", label: "Watchlist", icon: Eye },
  { id: "settings", label: "Settings", icon: Settings },
  { id: "manufacturing", label: "Manufacturing", icon: Factory },
];

export function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [portfolio, setPortfolio] = useState(null);
  const [settings, setSettings] = useState(null);
  const [scanResult, setScanResult] = useState(null);
  const [error, setError] = useState("");

  async function refreshPortfolio() {
    const data = await api.getPortfolio();
    setPortfolio(data);
  }

  async function refreshSettings() {
    const data = await api.getSettings();
    setSettings(data);
  }

  useEffect(() => {
    Promise.all([refreshPortfolio(), refreshSettings()]).catch((err) => setError(err.message));
  }, []);

  const bestOpportunity = scanResult?.opportunities?.[0] ?? null;
  const dashboardStats = useMemo(
    () => ({
      totalIsk: portfolio?.total_liquid_isk ?? settings?.total_liquid_isk ?? 365000000,
      invested: portfolio?.isk_invested ?? 0,
      openOrders: portfolio?.open_positions ?? 0,
      realized: portfolio?.realized_profit ?? 0,
      bestOpportunity,
    }),
    [portfolio, settings, bestOpportunity],
  );
  const isScanner = activeTab === "scanner";

  return (
    <div className="min-h-screen">
      <div className="border-b border-line bg-hull/95">
        <div className={`mx-auto flex items-center justify-between px-4 py-4 ${isScanner ? "max-w-none" : "max-w-[1480px]"}`}>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-cyan/40 bg-cyan/10 text-cyan">
              <Star size={20} />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">EVE Business Assistant</h1>
              <p className="text-sm text-slate-400">Manual trading decisions for Jita station traders</p>
            </div>
          </div>
          <div className="hidden text-right text-sm text-slate-400 sm:block">
            Liquid ISK
            <div className="font-semibold text-slate-100">{formatIsk(dashboardStats.totalIsk, true)} ISK</div>
          </div>
        </div>
      </div>

      <div className={`mx-auto grid grid-cols-1 gap-0 px-4 ${isScanner ? "max-w-none" : "max-w-[1480px] lg:grid-cols-[220px_1fr]"}`}>
        <nav className={`border-b border-line py-3 ${isScanner ? "" : "lg:min-h-[calc(100vh-73px)] lg:border-b-0 lg:border-r lg:pr-4"}`}>
          <div className={`flex gap-2 overflow-x-auto ${isScanner ? "" : "lg:flex-col"}`}>
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const selected = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex min-w-max items-center gap-2 rounded-md px-3 py-2 text-sm ${
                    selected
                      ? "border border-cyan/40 bg-cyan/12 text-cyan"
                      : "border border-transparent text-slate-300 hover:border-line hover:bg-panel"
                  }`}
                >
                  <Icon size={17} />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </nav>

        <main className={`py-5 ${isScanner ? "" : "lg:pl-5"}`}>
          {error ? (
            <div className="mb-4 rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
              {error}
            </div>
          ) : null}

          {activeTab === "dashboard" && (
            <Dashboard
              stats={dashboardStats}
              portfolio={portfolio}
              onScan={() => setActiveTab("scanner")}
            />
          )}
          {activeTab === "scanner" && (
            <MarketScanner
              settings={settings}
              scanResult={scanResult}
              setScanResult={setScanResult}
              setError={setError}
            />
          )}
          {activeTab === "portfolio" && (
            <Portfolio
              portfolio={portfolio}
              onChanged={() => refreshPortfolio().catch((err) => setError(err.message))}
              setError={setError}
            />
          )}
          {activeTab === "watchlist" && <Watchlist opportunities={scanResult?.opportunities ?? []} />}
          {activeTab === "settings" && (
            <SettingsPage
              settings={settings}
              onSaved={(nextSettings) => {
                setSettings(nextSettings);
                refreshPortfolio().catch((err) => setError(err.message));
              }}
              setError={setError}
            />
          )}
          {activeTab === "manufacturing" && <Manufacturing />}
        </main>
      </div>
    </div>
  );
}
