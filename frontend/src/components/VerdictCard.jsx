import React from 'react';
import DissentLedger from './DissentLedger.jsx';

const VERDICT_STYLES = {
  ACCEPT: 'bg-green-100 text-green-800 border-green-300',
  REVISE: 'bg-amber-100 text-amber-800 border-amber-300',
  REJECT: 'bg-red-100 text-red-800 border-red-300',
};

const VerdictCard = ({ verdict, dissentLedger }) => {
  if (!verdict) return null;

  const v = verdict.verdict || 'REVISE';
  const scores = verdict.scores || {};

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow-md border overflow-hidden">
        <div className="bg-slate-800 text-white px-4 py-3 flex justify-between items-center">
          <h3 className="font-semibold">Review Verdict</h3>
          <span className={`px-3 py-1 rounded-full text-sm font-bold border ${VERDICT_STYLES[v] || VERDICT_STYLES.REVISE}`}>
            {v}
          </span>
        </div>

        <div className="p-4 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(scores).map(([key, val]) => (
              <div key={key} className="text-center p-2 bg-slate-50 rounded-lg">
                <div className="text-2xl font-bold text-primary-600">{val}</div>
                <div className="text-xs text-slate-500 capitalize">{key}</div>
              </div>
            ))}
          </div>

          {verdict.consensus_summary && (
            <p className="text-sm text-slate-700">
              <strong>Consensus:</strong> {verdict.consensus_summary}
            </p>
          )}
        </div>
      </div>

      <DissentLedger
        dissentLedger={dissentLedger}
        dissentSummary={verdict.dissent_summary}
      />
    </div>
  );
};

export default VerdictCard;
