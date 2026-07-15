import React from 'react';

const MetricBar = ({ label, society, solo, format = (v) => v }) => {
  const max = Math.max(society, solo, 0.01);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-600">
        <span>{label}</span>
        <span>Society {format(society)} vs Solo {format(solo)}</span>
      </div>
      <div className="flex gap-2 h-4">
        <div className="flex-1 bg-slate-100 rounded overflow-hidden">
          <div
            className="h-full bg-purple-500 rounded transition-all"
            style={{ width: `${(society / max) * 100}%` }}
          />
        </div>
        <div className="flex-1 bg-slate-100 rounded overflow-hidden">
          <div
            className="h-full bg-slate-400 rounded transition-all"
            style={{ width: `${(solo / max) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
};

const BenchmarkArena = ({ benchmark, loading }) => {
  if (loading) {
    return (
      <div className="p-8 text-center text-slate-500">
        Running benchmark: Society vs Solo Reviewer...
      </div>
    );
  }

  if (!benchmark) {
    return (
      <div className="p-8 text-center text-slate-500">
        Run a debate first, then click Benchmark to compare against a single-agent reviewer.
      </div>
    );
  }

  const { society, solo, comparison } = benchmark;
  const societyOverall = society.overall_score ?? society.coverage_score ?? 0;
  const soloOverall = comparison.solo_overall_score ?? solo.coverage_score ?? 0;

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-2 gap-4 text-center">
        <div className="p-4 bg-purple-50 border-2 border-purple-200 rounded-lg">
          <div className="text-xs text-purple-600 font-semibold mb-1">AGENT SOCIETY</div>
          <div className="text-3xl font-bold text-purple-700">
            {Math.round(societyOverall * 100)}%
          </div>
          <div className="text-xs text-slate-500">overall impact</div>
        </div>
        <div className="p-4 bg-slate-50 border-2 border-slate-200 rounded-lg">
          <div className="text-xs text-slate-600 font-semibold mb-1">SOLO REVIEWER</div>
          <div className="text-3xl font-bold text-slate-700">
            {Math.round(soloOverall * 100)}%
          </div>
          <div className="text-xs text-slate-500">overall impact</div>
        </div>
      </div>

      <div className={`p-3 rounded-lg text-sm font-medium text-center ${
        comparison.coverage_winner === 'society'
          ? 'bg-green-50 text-green-800 border border-green-200'
          : 'bg-amber-50 text-amber-800 border border-amber-200'
      }`}>
        Winner: {comparison.coverage_winner === 'society' ? 'Agent Society' : 'Solo Reviewer'}
        {' '}(Δ impact: {comparison.coverage_delta > 0 ? '+' : ''}{(comparison.coverage_delta * 100).toFixed(1)}%)
      </div>

      <div className="space-y-3">
        <MetricBar
          label="Overall Impact"
          society={societyOverall}
          solo={soloOverall}
          format={(v) => `${Math.round(v * 100)}%`}
        />
        <MetricBar
          label="Coverage Score"
          society={society.coverage_score || 0}
          solo={solo.coverage_score || 0}
          format={(v) => `${Math.round(v * 100)}%`}
        />
        <MetricBar
          label="Evidence References"
          society={society.evidence_count || 0}
          solo={solo.evidence_count || 0}
        />
        <MetricBar
          label="Dimensions Covered"
          society={(society.dimensions_covered || []).length}
          solo={(solo.dimensions_covered || []).length}
        />
        <MetricBar
          label="Collaboration Signal"
          society={society.collaboration_score || 0}
          solo={0}
          format={(v) => `${Math.round(v * 100)}%`}
        />
      </div>

      <p className="text-sm text-slate-600 text-center">{comparison.summary}</p>
      <p className="text-xs text-slate-400 text-center">
        Solo review took {solo.elapsed_seconds}s • Society used {society.message_count || 0} agent messages
        {society.crossfire_count ? ` • ${society.crossfire_count} crossfire replies` : ''}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border rounded-lg p-3 max-h-48 overflow-y-auto">
          <h4 className="text-xs font-semibold text-purple-700 mb-2">Society Dimensions</h4>
          <ul className="text-xs text-slate-600 space-y-1">
            {(society.dimensions_covered || []).map((d) => (
              <li key={d}>✓ {d.replace(/_/g, ' ')}</li>
            ))}
          </ul>
        </div>
        <div className="border rounded-lg p-3 max-h-48 overflow-y-auto">
          <h4 className="text-xs font-semibold text-slate-600 mb-2">Solo Dimensions</h4>
          <ul className="text-xs text-slate-600 space-y-1">
            {(solo.dimensions_covered || []).map((d) => (
              <li key={d}>✓ {d.replace(/_/g, ' ')}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default BenchmarkArena;
