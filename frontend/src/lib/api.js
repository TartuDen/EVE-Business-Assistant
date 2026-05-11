const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Keep the HTTP status text.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export const api = {
  scanMarket(payload) {
    return request("/api/market/scan", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  csvUrl() {
    return `${API_BASE}/api/market/export.csv`;
  },
  getPortfolio() {
    return request("/api/portfolio");
  },
  addPosition(payload) {
    return request("/api/portfolio", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updatePosition(id, payload) {
    return request(`/api/portfolio/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  deletePosition(id) {
    return request(`/api/portfolio/${id}`, { method: "DELETE" });
  },
  getSettings() {
    return request("/api/settings");
  },
  saveSettings(payload) {
    return request("/api/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  getCharacterSession() {
    return request("/api/character/session");
  },
  getCharacterLogin() {
    return request("/api/character/login");
  },
  getCharacterProfiles() {
    return request("/api/character/profiles");
  },
  getCharacterAnalysis(profileId = "safe_jita_trader", characterId = null) {
    const params = new URLSearchParams({ profile_id: profileId });
    if (characterId) params.set("character_id", characterId);
    return request(`/api/character/analysis?${params.toString()}`);
  },
  getSavedPlans() {
    return request("/api/character/saved-plans");
  },
  saveSkillPlan(payload) {
    return request("/api/character/saved-plans", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  deleteSkillPlan(id) {
    return request(`/api/character/saved-plans/${id}`, { method: "DELETE" });
  },
};

export function formatIsk(value, compact = false) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: compact ? 1 : 2,
    notation: compact ? "compact" : "standard",
  }).format(Number(value || 0));
}
