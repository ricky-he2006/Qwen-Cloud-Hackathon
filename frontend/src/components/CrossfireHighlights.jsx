import React from 'react';

const CrossfireHighlights = ({ messages, onExport }) => {
  const directReplies = messages.filter(
    (m) => m.message_type === 'debate' || m.content?.includes('Responding to')
  );
  const disagreements = messages.filter((m) => m.stance === 'disagree');
  const rebuttals = messages.filter((m) => m.message_type === 'rebuttal');
  const highlights = [...directReplies, ...rebuttals, ...disagreements]
    .filter((msg, index, all) => all.findIndex((m) => m.turn === msg.turn && m.agent_name === msg.agent_name) === index)
    .slice(-5)
    .reverse();

  return (
    <div className="bg-white rounded-lg shadow-md border overflow-hidden">
      <div className="bg-slate-100 px-4 py-3 border-b flex justify-between items-center gap-3">
        <div>
          <h2 className="font-semibold text-slate-800">Crossfire Highlights</h2>
          <p className="text-sm text-slate-600">Best judge-facing proof that agents are arguing, not monologuing</p>
        </div>
        <button
          onClick={onExport}
          disabled={!messages.length}
          className="text-xs bg-slate-900 text-white rounded-full px-3 py-1.5 disabled:opacity-40"
        >
          Export Report
        </button>
      </div>

      <div className="p-4">
        {highlights.length === 0 ? (
          <div className="text-sm text-slate-500 text-center py-6">
            Crossfire highlights will appear after agents start responding to each other.
          </div>
        ) : (
          <div className="space-y-3">
            {highlights.map((msg, index) => (
              <div key={`${msg.turn}-${index}`} className="border border-slate-200 rounded-lg p-3 bg-slate-50">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="font-semibold text-sm text-slate-800">{msg.agent_name}</span>
                  <span className={`text-xs rounded-full px-2 py-0.5 ${
                    msg.stance === 'disagree'
                      ? 'bg-red-100 text-red-700'
                      : msg.stance === 'agree'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-slate-200 text-slate-600'
                  }`}>
                    {msg.stance || msg.message_type || 'comment'}
                  </span>
                  <span className="text-xs text-slate-400">Round {msg.round_num}</span>
                </div>
                <p className="text-sm text-slate-700 whitespace-pre-wrap">
                  {msg.content?.slice(0, 360)}
                  {msg.content?.length > 360 ? '...' : ''}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CrossfireHighlights;
