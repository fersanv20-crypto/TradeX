export default function SettingsDeploymentCard() {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="text-lg font-semibold text-white">Deployment & Integrations</h2>
      <div className="mt-4 space-y-3">
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Frontend</div>
          <div className="mt-1 text-sm text-emerald-300">Healthy - Last deploy 2h ago</div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">API + Bot Engine</div>
          <div className="mt-1 text-sm text-cyan-300">Connected (paper mode)</div>
        </div>
      </div>
    </section>
  );
}