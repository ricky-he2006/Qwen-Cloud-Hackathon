import React from 'react';

const ConsensusThermometer = ({ agreementHistory, currentLevel }) => {
  const level = currentLevel ?? (agreementHistory?.length ? agreementHistory[agreementHistory.length - 1] : 0);
  const pct = Math.round(level * 100);

  return (
    <div className="p-4">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-slate-600">Consensus Level</span>
        <span className="font-semibold text-slate-800">{pct}%</span>
      </div>
      <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
        <div
          className={`h-3 rounded-full transition-all duration-500 ${
            pct >= 60 ? 'bg-green-500' : pct >= 40 ? 'bg-amber-500' : 'bg-red-400'
          }`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      {agreementHistory?.length > 1 && (
        <div className="flex gap-1 mt-2">
          {agreementHistory.map((a, i) => (
            <div
              key={i}
              className="flex-1 h-1.5 rounded"
              style={{
                backgroundColor: a >= 0.6 ? '#22c55e' : a >= 0.4 ? '#f59e0b' : '#f87171',
                opacity: 0.4 + (i / agreementHistory.length) * 0.6,
              }}
              title={`Round ${i + 1}: ${Math.round(a * 100)}%`}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default ConsensusThermometer;
