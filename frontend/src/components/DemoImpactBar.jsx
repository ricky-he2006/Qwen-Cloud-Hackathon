import React from 'react';

const DemoImpactBar = ({
  paperData,
  assignments,
  messages,
  agreementHistory,
  verdict,
  benchmark,
  dissentLedger,
}) => {
  const crossfireTurns = messages.filter((m) => m.message_type === 'debate').length;
  const rebuttals = messages.filter((m) => m.message_type === 'rebuttal').length;
  const dissentMsgs = messages.filter((m) => m.stance === 'disagree').length;
  const dissentItems = dissentLedger?.length || 0;
  const latestAgreement = agreementHistory.length
    ? Math.round(agreementHistory[agreementHistory.length - 1] * 100)
    : 0;

  const cards = [
    {
      label: 'Task Split',
      value: assignments.length || (paperData ? '—' : 0),
      caption: assignments.length ? 'specialist assignments' : 'plan or start debate',
      tone: 'from-blue-500 to-indigo-600',
    },
    {
      label: 'Crossfire',
      value: crossfireTurns,
      caption: crossfireTurns ? 'direct replies by name' : 'starts during debate',
      tone: 'from-fuchsia-500 to-purple-600',
    },
    {
      label: 'Dissent',
      value: Math.max(dissentItems, dissentMsgs + rebuttals),
      caption: dissentItems
        ? `${dissentItems} ledger · ${rebuttals} rebuttals`
        : 'tracked when agents disagree',
      tone: 'from-orange-500 to-red-500',
    },
    {
      label: 'Consensus',
      value: `${latestAgreement}%`,
      caption: verdict?.verdict ? `${verdict.verdict} verdict` : 'evidence-weighted',
      tone: 'from-emerald-500 to-teal-600',
    },
  ];

  const delta = benchmark?.comparison?.coverage_delta;
  const deltaPct = delta != null ? (delta * 100).toFixed(1) : null;
  const societyScore =
    benchmark?.society?.overall_score ?? benchmark?.society?.coverage_score;
  const soloScore =
    benchmark?.comparison?.solo_overall_score ??
    benchmark?.solo?.coverage_score;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {cards.map((card) => (
          <div
            key={card.label}
            className={`rounded-xl p-4 text-white shadow-md bg-gradient-to-br ${card.tone}`}
          >
            <div className="text-xs uppercase tracking-wide opacity-80">{card.label}</div>
            <div className="text-3xl font-black mt-1">{card.value}</div>
            <div className="text-xs opacity-90 mt-1">{card.caption}</div>
          </div>
        ))}
      </div>

      {benchmark?.comparison && (
        <div className="rounded-xl bg-slate-900 text-white p-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-wide text-purple-200">Benchmark Proof</div>
            <div className="font-semibold text-lg">
              Society impact {deltaPct != null && Number(deltaPct) >= 0 ? '+' : ''}
              {deltaPct}% vs solo reviewer
            </div>
            <p className="text-xs text-slate-300 mt-1">
              Society {societyScore != null ? `${Math.round(societyScore * 100)}%` : '—'} · Solo{' '}
              {soloScore != null ? `${Math.round(soloScore * 100)}%` : '—'} · Track 3 measurable gain
            </p>
          </div>
          <span className="text-xs bg-purple-500/30 border border-purple-300/40 rounded-full px-3 py-1">
            Multi-agent &gt; single agent
          </span>
        </div>
      )}
    </div>
  );
};

export default DemoImpactBar;
