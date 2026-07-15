import React, { useState } from 'react';
import NaturalLanguageSearch from './NaturalLanguageSearch.jsx';
import TopicRanker from './TopicRanker.jsx';

const MODES = [
  {
    id: 'single',
    label: 'Single paper',
    short: 'Load one paper and run a full agent debate',
  },
  {
    id: 'topic',
    label: 'Topic ranking',
    short: 'Find papers, debate each, get the best fits',
  },
];

const ResearchHub = ({
  paperData,
  onPaperLoaded,
  onSelectPaper,
  onStartDebate,
  debateDisabled,
  loadingPaper,
  topicEvents,
  onResearchBegin,
  onResearchEnd,
  topicResearchRunning,
  debateStarted,
}) => {
  const [mode, setMode] = useState('single');

  const busy = loadingPaper || debateStarted || topicResearchRunning;

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl shadow-md border border-slate-200 overflow-hidden">
        <div className="px-4 py-3 border-b bg-slate-50">
          <h2 className="font-semibold text-slate-900">How do you want to research?</h2>
          <p className="text-xs text-slate-500 mt-1">
            Review one specific paper, or let agents find and rank the best papers for a topic.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-0">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => !busy && setMode(m.id)}
              disabled={busy}
              className={`px-4 py-3 text-left border-b-2 transition-colors ${
                mode === m.id
                  ? m.id === 'single'
                    ? 'border-indigo-600 bg-indigo-50'
                    : 'border-amber-600 bg-amber-50'
                  : 'border-transparent hover:bg-slate-50'
              } disabled:opacity-50`}
            >
              <span
                className={`block text-sm font-semibold ${
                  mode === m.id
                    ? m.id === 'single'
                      ? 'text-indigo-900'
                      : 'text-amber-900'
                    : 'text-slate-700'
                }`}
              >
                {m.label}
              </span>
              <span className="block text-xs text-slate-500 mt-0.5">{m.short}</span>
            </button>
          ))}
        </div>
      </div>

      {mode === 'single' ? (
        <NaturalLanguageSearch
          paperData={paperData}
          onPaperLoaded={onPaperLoaded}
          onSelectPaper={onSelectPaper}
          onStartDebate={onStartDebate}
          debateDisabled={debateDisabled}
          loading={loadingPaper}
        />
      ) : (
        <TopicRanker
          onSelectPaper={async (id) => {
            setMode('single');
            await onSelectPaper(id);
          }}
          loading={loadingPaper || debateStarted}
          topicEvents={topicEvents}
          onResearchBegin={onResearchBegin}
          onResearchEnd={onResearchEnd}
        />
      )}

      {busy && (
        <p className="text-xs text-center text-slate-500">
          {topicResearchRunning
            ? 'Topic ranking in progress — switch modes when finished'
            : debateStarted
              ? 'Debate in progress'
              : 'Loading paper…'}
        </p>
      )}
    </div>
  );
};

export default ResearchHub;
