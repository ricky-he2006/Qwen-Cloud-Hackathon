import React from 'react';

/**
 * Track 3 judge-facing checklist. Updates as the demo progresses.
 */
const DemoChecklist = ({
  paperData,
  conceptMap,
  assignments,
  debateStarted,
  debateDone,
  dissentCount,
  benchmark,
  onRunJudgeDemo,
  onPlanOnly,
  onGenerateMap,
  onBenchmark,
  busy,
}) => {
  const steps = [
    {
      id: 'paper',
      done: Boolean(paperData),
      label: 'Load a paper',
      hint: 'Short arXiv/DOI paper works best for demos',
    },
    {
      id: 'map',
      done: Boolean(conceptMap?.key_points?.length || conceptMap?.summary),
      label: 'Concept map + key points',
      hint: 'Judge briefing with methods / findings / limitations',
      action: onGenerateMap,
      actionLabel: 'Generate map',
    },
    {
      id: 'plan',
      done: assignments.length > 0,
      label: 'Task decomposition',
      hint: 'Show specialist ownership before debate',
      action: onPlanOnly,
      actionLabel: 'Plan only',
    },
    {
      id: 'debate',
      done: debateDone,
      label: 'Judge Demo debate',
      hint: '2 rounds · 1 crossfire — saves tokens',
      action: onRunJudgeDemo,
      actionLabel: 'Run Judge Demo',
      primary: true,
    },
    {
      id: 'dissent',
      done: dissentCount > 0 || debateDone,
      label: 'Visible conflict → resolution',
      hint: dissentCount ? `${dissentCount} dissent/rebuttal signals` : 'Crossfire + dissent ledger',
    },
    {
      id: 'benchmark',
      done: Boolean(benchmark?.comparison),
      label: 'Society vs solo benchmark',
      hint: 'Measurable multi-agent gain for Track 3',
      action: onBenchmark,
      actionLabel: 'Run benchmark',
    },
  ];

  const doneCount = steps.filter((s) => s.done).length;

  return (
    <div className="bg-white border border-indigo-100 rounded-xl shadow-sm overflow-hidden">
      <div className="bg-indigo-600 text-white px-4 py-3 flex items-center justify-between">
        <div>
          <h3 className="font-semibold">Track 3 Judge Path</h3>
          <p className="text-xs text-indigo-100 mt-0.5">
            Hit these proof points in your demo / Devpost video
          </p>
        </div>
        <span className="text-sm font-bold bg-white/15 rounded-full px-3 py-1">
          {doneCount}/{steps.length}
        </span>
      </div>
      <ol className="divide-y divide-slate-100">
        {steps.map((step, i) => (
          <li key={step.id} className="px-4 py-3 flex items-start gap-3">
            <span
              className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                step.done ? 'bg-emerald-500 text-white' : 'bg-slate-200 text-slate-600'
              }`}
            >
              {step.done ? '✓' : i + 1}
            </span>
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-medium ${step.done ? 'text-emerald-800' : 'text-slate-800'}`}>
                {step.label}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">{step.hint}</p>
            </div>
            {step.action && !step.done && (
              <button
                type="button"
                disabled={busy || (!paperData && step.id !== 'paper')}
                onClick={step.action}
                className={`shrink-0 text-xs font-semibold px-3 py-1.5 rounded-lg disabled:opacity-40 ${
                  step.primary
                    ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                {step.actionLabel}
              </button>
            )}
          </li>
        ))}
      </ol>
      {debateStarted && !debateDone && (
        <div className="px-4 py-2 bg-amber-50 text-amber-800 text-xs border-t border-amber-100">
          Debate in progress — leave the Chamber tab open so judges see live crossfire.
        </div>
      )}
    </div>
  );
};

export default DemoChecklist;
