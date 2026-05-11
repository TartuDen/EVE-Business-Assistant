import React, { useEffect, useMemo, useState } from "react";
import { BookOpen, Brain, CheckCircle2, Clock, LogIn, Save, ShieldAlert, Sparkles, Trash2 } from "lucide-react";
import { api, formatIsk } from "../lib/api.js";
import { StatCard } from "../components/StatCard.jsx";

const subpages = [
  "Overview",
  "Current Skills",
  "Recommended Queue",
  "Career Profiles",
  "Long-Term Roadmap",
  "Saved Plans",
];

export function CharacterProgression({ setError }) {
  const [session, setSession] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [selectedProfile, setSelectedProfile] = useState("safe_jita_trader");
  const [analysis, setAnalysis] = useState(null);
  const [savedPlans, setSavedPlans] = useState([]);
  const [activeSubpage, setActiveSubpage] = useState("Overview");
  const [loading, setLoading] = useState(false);

  async function loadBase() {
    const [sessionData, profileData, plans] = await Promise.all([
      api.getCharacterSession(),
      api.getCharacterProfiles(),
      api.getSavedPlans(),
    ]);
    setSession(sessionData);
    setProfiles(profileData);
    setSavedPlans(plans);
  }

  async function loadAnalysis(profileId = selectedProfile) {
    setLoading(true);
    setError("");
    try {
      const data = await api.getCharacterAnalysis(profileId);
      setAnalysis(data);
    } catch (err) {
      setAnalysis(null);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBase().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (session?.characters?.length) {
      loadAnalysis(selectedProfile);
    }
  }, [session, selectedProfile]);

  async function login() {
    setError("");
    const data = await api.getCharacterLogin();
    if (!data.configured) {
      setError(data.message);
      return;
    }
    window.location.href = data.authorization_url;
  }

  async function saveCurrentPlan() {
    if (!analysis) return;
    const payload = {
      character_id: analysis.character.character_id,
      character_name: analysis.character.name,
      profile_id: analysis.profile.profile_id,
      plan_name: `${analysis.character.name} - ${analysis.profile.display_name}`,
      notes: analysis.progression_analysis,
    };
    const saved = await api.saveSkillPlan(payload);
    setSavedPlans((current) => [saved, ...current]);
  }

  async function deletePlan(id) {
    await api.deleteSkillPlan(id);
    setSavedPlans((current) => current.filter((plan) => plan.id !== id));
  }

  const nextBest = analysis?.next_best_skill;
  const clone = analysis?.character?.clone_state;
  const currentProfile = useMemo(
    () => profiles.find((profile) => profile.profile_id === selectedProfile),
    [profiles, selectedProfile],
  );

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-4 border-b border-line pb-5 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-white">Character Progression</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            Connect an EVE character, compare real skills against reusable career profiles, and build a practical training roadmap.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={selectedProfile}
            onChange={(event) => setSelectedProfile(event.target.value)}
            className="rounded-md border border-line bg-hull px-3 py-2 text-sm text-white outline-none focus:border-cyan"
          >
            {profiles.map((profile) => (
              <option key={profile.profile_id} value={profile.profile_id}>{profile.display_name}</option>
            ))}
          </select>
          <button onClick={login} className="inline-flex items-center gap-2 rounded-md bg-cyan px-4 py-2 font-semibold text-hull">
            <LogIn size={18} />
            Connect EVE SSO
          </button>
          {analysis ? (
            <button onClick={saveCurrentPlan} className="inline-flex items-center gap-2 rounded-md border border-line px-4 py-2 text-sm text-slate-200 hover:border-cyan hover:text-cyan">
              <Save size={17} />
              Save Plan
            </button>
          ) : null}
        </div>
      </section>

      {!session?.configured ? (
        <section className="rounded-lg border border-amber/40 bg-amber/10 p-4 text-sm leading-6 text-amber">
          EVE SSO is not configured yet. Register an EVE developer app, set `EVE_CLIENT_ID`, `EVE_CLIENT_SECRET`, and callback `http://127.0.0.1:8000/api/character/callback`, then restart the backend.
        </section>
      ) : null}

      <div className="flex gap-2 overflow-x-auto border-b border-line pb-3">
        {subpages.map((page) => (
          <button
            key={page}
            onClick={() => setActiveSubpage(page)}
            className={`min-w-max rounded-md border px-3 py-2 text-sm ${
              activeSubpage === page ? "border-cyan/40 bg-cyan/12 text-cyan" : "border-line text-slate-300 hover:text-white"
            }`}
          >
            {page}
          </button>
        ))}
      </div>

      {loading ? <div className="text-sm text-slate-400">Loading character analysis...</div> : null}
      {!analysis && !loading ? <DisconnectedState session={session} currentProfile={currentProfile} onLogin={login} /> : null}

      {analysis && activeSubpage === "Overview" ? (
        <Overview analysis={analysis} nextBest={nextBest} clone={clone} />
      ) : null}
      {analysis && activeSubpage === "Current Skills" ? <CurrentSkills analysis={analysis} /> : null}
      {analysis && activeSubpage === "Recommended Queue" ? <RecommendedQueue analysis={analysis} /> : null}
      {activeSubpage === "Career Profiles" ? <CareerProfiles profiles={profiles} selectedProfile={selectedProfile} setSelectedProfile={setSelectedProfile} /> : null}
      {analysis && activeSubpage === "Long-Term Roadmap" ? <Roadmap analysis={analysis} /> : null}
      {activeSubpage === "Saved Plans" ? <SavedPlans plans={savedPlans} onDelete={deletePlan} /> : null}
    </div>
  );
}

function DisconnectedState({ session, currentProfile, onLogin }) {
  return (
    <section className="rounded-lg border border-line bg-panel p-5">
      <div className="flex items-center gap-2 text-cyan">
        <Sparkles size={20} />
        <h3 className="font-semibold">Ready for EVE SSO</h3>
      </div>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
        Current profile: {currentProfile?.display_name ?? "Safe Jita Trader"}. After login, the app fetches skills, queue, wallet, assets, and implants through official ESI scopes.
      </p>
      <button onClick={onLogin} className="mt-4 inline-flex items-center gap-2 rounded-md bg-cyan px-4 py-2 font-semibold text-hull">
        <LogIn size={18} />
        Connect Character
      </button>
      {session?.characters?.length ? (
        <div className="mt-4 text-sm text-slate-400">Connected characters: {session.characters.map((character) => character.character_name).join(", ")}</div>
      ) : null}
    </section>
  );
}

function Overview({ analysis, nextBest, clone }) {
  return (
    <div className="space-y-5">
      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        <StatCard label="Character" value={analysis.character.name} />
        <StatCard label="Total SP" value={formatIsk(analysis.character.total_sp, true)} />
        <StatCard label="Clone State" value={<CloneBadge clone={clone} />} detail={clone?.confidence} />
        <StatCard label="Wallet" value={`${formatIsk(analysis.character.wallet_balance, true)} ISK`} />
        <StatCard label="Assets" value={formatIsk(analysis.character.asset_count)} />
        <StatCard label="Queue" value={`${analysis.character.skill_queue_count} skills`} />
      </section>

      {nextBest ? (
        <section className="rounded-lg border border-cyan/30 bg-cyan/8 p-4">
          <div className="flex items-center gap-2 text-cyan">
            <Brain size={20} />
            <h3 className="font-semibold">Next Best Skill</h3>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-5">
            <Metric label="Skill" value={nextBest.skill_name} />
            <Metric label="Current" value={`Level ${nextBest.current_level}`} />
            <Metric label="Target" value={`Level ${nextBest.target_level}`} />
            <Metric label="Training Time" value={nextBest.training_time} />
            <Metric label="Priority" value={`${nextBest.priority}/100`} />
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-200">{nextBest.reason} {nextBest.economic_impact}</p>
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-2">
        <Panel title="Progression Analysis" icon={BookOpen}>
          <p className="text-sm leading-6 text-slate-300">{analysis.progression_analysis}</p>
        </Panel>
        <Panel title="Alpha / Omega Notes" icon={ShieldAlert}>
          <p className="text-sm leading-6 text-slate-300">{clone?.reason}</p>
        </Panel>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Panel title="Strongest Skill Areas" icon={CheckCircle2}>
          <TagList items={analysis.strongest_skill_areas} />
        </Panel>
        <Panel title="Weakest Skill Areas" icon={ShieldAlert}>
          <TagList items={analysis.weakest_skill_areas} />
        </Panel>
      </section>
    </div>
  );
}

function CurrentSkills({ analysis }) {
  return (
    <section className="rounded-lg border border-line bg-panel p-4">
      <h3 className="font-semibold text-white">Current Skills</h3>
      <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {analysis.skills.slice(0, 120).map((skill) => (
          <div key={skill.skill_id} className="rounded-md border border-line bg-hull p-3 text-sm">
            <div className="font-medium text-white">{skill.skill_name}</div>
            <div className="mt-1 text-slate-400">Trained {skill.trained_skill_level} / Active {skill.active_skill_level}</div>
            <div className="mt-2 h-2 rounded bg-line">
              <div className="h-2 rounded bg-cyan" style={{ width: `${Math.min(100, skill.trained_skill_level * 20)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function RecommendedQueue({ analysis }) {
  return (
    <div className="space-y-4">
      <RecommendationList title="Recommended Queue" items={analysis.recommendations} />
      <RecommendationList title="Available after Omega upgrade" items={analysis.omega_only_recommendations} muted />
    </div>
  );
}

function RecommendationList({ title, items, muted = false }) {
  return (
    <section className="rounded-lg border border-line bg-panel p-4">
      <h3 className="font-semibold text-white">{title}</h3>
      <div className="mt-4 space-y-3">
        {items.map((item) => (
          <article key={`${item.skill_id}-${item.target_level}`} className="rounded-lg border border-line bg-hull p-4">
            <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
              <div>
                <h4 className="font-semibold text-white">{item.skill_name} {item.current_level} to {item.target_level}</h4>
                <p className="mt-1 text-sm leading-6 text-slate-400">{item.reason}</p>
                <p className="mt-1 text-sm text-slate-300">{item.economic_impact}</p>
              </div>
              <span className={`rounded border px-2 py-1 text-xs font-semibold ${muted ? "border-amber/40 text-amber" : "border-mint/40 text-mint"}`}>
                {item.priority}/100
              </span>
            </div>
            <div className="mt-3 flex items-center gap-2 text-sm text-slate-400">
              <Clock size={15} />
              {item.training_time}
            </div>
          </article>
        ))}
        {!items.length ? <div className="text-sm text-slate-400">No recommendations in this section.</div> : null}
      </div>
    </section>
  );
}

function CareerProfiles({ profiles, selectedProfile, setSelectedProfile }) {
  return (
    <section className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
      {profiles.map((profile) => (
        <button
          key={profile.profile_id}
          onClick={() => setSelectedProfile(profile.profile_id)}
          className={`rounded-lg border p-4 text-left ${selectedProfile === profile.profile_id ? "border-cyan/50 bg-cyan/8" : "border-line bg-panel hover:border-cyan/30"}`}
        >
          <h3 className="font-semibold text-white">{profile.display_name}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-400">{profile.description}</p>
          <p className="mt-3 text-xs uppercase tracking-wide text-slate-500">{profile.recommended_for}</p>
        </button>
      ))}
    </section>
  );
}

function Roadmap({ analysis }) {
  const groups = [
    ["Immediate goals", analysis.roadmap.immediate],
    ["Short-term goals", analysis.roadmap.short_term],
    ["Medium-term goals", analysis.roadmap.medium_term],
  ];
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      {groups.map(([title, items]) => (
        <RecommendationList key={title} title={title} items={items} />
      ))}
    </div>
  );
}

function SavedPlans({ plans, onDelete }) {
  return (
    <section className="rounded-lg border border-line bg-panel p-4">
      <h3 className="font-semibold text-white">Saved Plans</h3>
      <div className="mt-4 space-y-3">
        {plans.map((plan) => (
          <article key={plan.id} className="flex items-start justify-between gap-3 rounded-lg border border-line bg-hull p-4">
            <div>
              <h4 className="font-semibold text-white">{plan.plan_name}</h4>
              <p className="mt-1 text-sm text-slate-400">{plan.profile_id} / {plan.character_name}</p>
              <p className="mt-2 text-sm leading-6 text-slate-300">{plan.notes}</p>
            </div>
            <button onClick={() => onDelete(plan.id)} className="rounded-md border border-line p-2 text-slate-300 hover:border-danger hover:text-danger">
              <Trash2 size={16} />
            </button>
          </article>
        ))}
        {!plans.length ? <div className="text-sm text-slate-400">No saved plans yet.</div> : null}
      </div>
    </section>
  );
}

function CloneBadge({ clone }) {
  const omega = clone?.state === "Omega";
  return (
    <span className={`inline-flex rounded border px-2 py-1 text-xs font-semibold ${omega ? "border-cyan/40 text-cyan" : "border-amber/40 text-amber"}`}>
      {clone?.state ?? "Unknown"}
    </span>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-lg border border-line bg-panel p-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-sm font-semibold text-white">{value}</div>
    </div>
  );
}

function Panel({ title, icon: Icon, children }) {
  return (
    <section className="rounded-lg border border-line bg-panel p-4">
      <div className="flex items-center gap-2 text-cyan">
        <Icon size={18} />
        <h3 className="font-semibold text-white">{title}</h3>
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function TagList({ items }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span key={item} className="rounded border border-line bg-hull px-2 py-1 text-sm text-slate-200">{item}</span>
      ))}
      {!items.length ? <span className="text-sm text-slate-400">No clear signal yet.</span> : null}
    </div>
  );
}
