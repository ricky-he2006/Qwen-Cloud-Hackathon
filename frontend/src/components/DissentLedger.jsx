import React from 'react';

/**
 * Structured minority opinions — Track 3 conflict-resolution proof.
 */
const DissentLedger = ({ dissentLedger = [], dissentSummary }) => {
  if (!dissentLedger?.length && !dissentSummary) {
    return (
      <div className="bg-slate-50 border border-dashed border-slate-200 rounded-lg p-4 text-sm text-slate-500">
        No dissent recorded yet. Disagreements during debate appear here when consensus slips.
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-red-100 shadow-sm overflow-hidden">
      <div className="bg-red-50 px-4 py-3 border-b border-red-100 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-red-900">Dissent Ledger</h3>
          <p className="text-xs text-red-700 mt-0.5">
            Minority views preserved — not collapsed into majority vote
          </p>
        </div>
        <span className="text-xs font-bold bg-red-100 text-red-800 rounded-full px-2.5 py-1">
          {dissentLedger.length} item{dissentLedger.length === 1 ? '' : 's'}
        </span>
      </div>

      <div className="p-4 space-y-3">
        {dissentSummary && (
          <p className="text-sm text-slate-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            <span className="font-semibold text-amber-900">Moderator summary: </span>
            {dissentSummary}
          </p>
        )}

        <ul className="space-y-3">
          {dissentLedger.map((d, i) => (
            <li
              key={`${d.agent_name}-${d.topic}-${i}`}
              className="rounded-lg border border-red-100 bg-gradient-to-r from-red-50/80 to-white p-3"
            >
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="font-semibold text-red-900 text-sm">{d.agent_name || 'Agent'}</span>
                {d.topic && (
                  <span className="text-[11px] uppercase tracking-wide bg-white border border-red-100 text-red-700 px-2 py-0.5 rounded-full">
                    {d.topic}
                  </span>
                )}
                {d.round != null && (
                  <span className="text-[11px] text-slate-400">Round {d.round}</span>
                )}
              </div>
              <p className="text-sm text-slate-800 leading-snug">{d.position || d.content || '—'}</p>
              {d.evidence?.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {d.evidence.slice(0, 2).map((ev, j) => (
                    <li key={j} className="text-xs text-slate-600 pl-2 border-l-2 border-red-200">
                      [{ev.section || 'section'}] {ev.quote || ev}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default DissentLedger;
