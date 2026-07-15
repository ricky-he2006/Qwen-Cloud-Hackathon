import React from 'react';

const PHASES = [
  { key: 'planning', label: 'Planning', detail: 'Moderator assigns specialist work' },
  { key: 'opening', label: 'Openings', detail: 'Agents take initial positions' },
  { key: 'crossfire', label: 'Crossfire', detail: 'Agents answer each other directly' },
  { key: 'rebuttal', label: 'Rebuttal', detail: 'Dissent is challenged and defended' },
  { key: 'verdict', label: 'Verdict', detail: 'Consensus + dissent ledger' },
];

const DebateStage = ({ debateStatus, debateEvents, messages, assignments }) => {
  const latestEvent = debateEvents[debateEvents.length - 1];
  const latestMessage = messages[messages.length - 1];
  const hasPlanning = assignments.length > 0;
  const hasOpening = messages.some((m) => m.message_type === 'opening');
  const hasCrossfire = messages.some((m) => m.message_type === 'debate');
  const hasRebuttal = messages.some((m) => m.message_type === 'rebuttal');
  const hasVerdict = debateStatus.consensusReached;

  const activeKey = hasVerdict
    ? 'verdict'
    : hasRebuttal
      ? 'rebuttal'
      : hasCrossfire
        ? 'crossfire'
        : hasOpening
          ? 'opening'
          : 'planning';

  const isComplete = (key) => {
    if (key === 'planning') return hasPlanning;
    if (key === 'opening') return hasOpening;
    if (key === 'crossfire') return hasCrossfire;
    if (key === 'rebuttal') return hasRebuttal;
    if (key === 'verdict') return hasVerdict;
    return false;
  };

  return (
    <div className="bg-white rounded-lg shadow-md border overflow-hidden">
      <div className="bg-slate-900 text-white px-4 py-3 flex flex-wrap justify-between gap-3">
        <div>
          <h2 className="font-semibold">Live Debate Stage</h2>
          <p className="text-xs text-slate-300">
            Round {debateStatus.round || 0} · {latestEvent?.topic || latestMessage?.agent_name || 'waiting for agents'}
          </p>
        </div>
        <div className="text-xs bg-white/10 border border-white/20 rounded-full px-3 py-1 self-start">
          {debateStatus.consensusReached ? 'Complete' : 'Live cross-examination'}
        </div>
      </div>

      <div className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {PHASES.map((phase, index) => {
            const complete = isComplete(phase.key);
            const active = phase.key === activeKey;
            return (
              <div
                key={phase.key}
                className={`rounded-lg border p-3 ${
                  active
                    ? 'border-purple-300 bg-purple-50 ring-2 ring-purple-100'
                    : complete
                      ? 'border-green-200 bg-green-50'
                      : 'border-slate-200 bg-slate-50'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`h-6 w-6 rounded-full flex items-center justify-center text-xs font-bold ${
                      complete ? 'bg-green-500 text-white' : active ? 'bg-purple-500 text-white' : 'bg-slate-200 text-slate-600'
                    }`}
                  >
                    {complete ? '✓' : index + 1}
                  </span>
                  <span className="font-semibold text-sm text-slate-800">{phase.label}</span>
                </div>
                <p className="text-xs text-slate-500 mt-2">{phase.detail}</p>
              </div>
            );
          })}
        </div>

        {latestMessage && (
          <div className="mt-4 rounded-lg bg-slate-50 border border-slate-200 p-3">
            <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">Latest move</div>
            <p className="text-sm text-slate-700">
              <strong>{latestMessage.agent_name}</strong>
              {latestMessage.message_type ? ` · ${latestMessage.message_type}` : ''}: {latestMessage.content?.slice(0, 180)}
              {latestMessage.content?.length > 180 ? '...' : ''}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default DebateStage;
