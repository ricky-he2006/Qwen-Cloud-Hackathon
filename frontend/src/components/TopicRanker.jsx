import React, { useState, useEffect, useMemo } from 'react';

const TOPIC_EXAMPLES = [
  'Best papers on slow-wave sleep loss and dementia for a clinical researcher',
  'Strongest cohort studies on GLP-1 drugs and heart failure',
  'Foundational transformer papers for a beginner in NLP',
];

function describeTopicEvent(event) {
  switch (event.type) {
    case 'topic_research_started':
      return `Started research: debating up to ${event.papers_to_debate} papers`;
    case 'topic_papers_discovered':
      return `Found ${event.count} candidate papers`;
    case 'topic_shortlist_ready':
      return `Shortlisted ${event.shortlist?.length || 0} papers for debate`;
    case 'topic_paper_review_started':
      return `Debating (${event.paper_index}/${event.total_papers}): ${event.title?.slice(0, 60)}…`;
    case 'topic_paper_review_complete':
      return `Finished: ${event.evaluation?.title?.slice(0, 50)}… (${Math.round((event.evaluation?.overall_score || 0) * 100)}% fit)`;
    case 'topic_research_complete':
      return 'Ranking complete';
    default:
      return null;
  }
}

const TopicRanker = ({
  onSelectPaper,
  loading,
  topicEvents = [],
  onResearchBegin,
  onResearchEnd,
}) => {
  const [goal, setGoal] = useState('');
  const [papersToDebate, setPapersToDebate] = useState(3);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const progressLines = useMemo(() => {
    const lines = [];
    for (const event of topicEvents) {
      const line = describeTopicEvent(event);
      if (line) lines.push(line);
    }
    return lines;
  }, [topicEvents]);

  const latestStatus = progressLines[progressLines.length - 1] || '';

  useEffect(() => {
    const complete = topicEvents.find((e) => e.type === 'topic_research_complete');
    if (complete && busy) {
      setResult({
        success: true,
        summary: complete.summary,
        top_pick: complete.top_pick,
        honorable_mentions: complete.honorable_mentions,
        recommendations: complete.recommendations,
        papers_debated: complete.papers_debated,
      });
      setBusy(false);
      onResearchEnd?.();
    }
  }, [topicEvents, busy, onResearchEnd]);

  const runTopicResearch = async (e) => {
    e.preventDefault();
    if (!goal.trim()) return;

    setBusy(true);
    setResult(null);
    onResearchBegin?.();

    // Brief pause so WebSocket connects before long-running POST returns events
    await new Promise((r) => setTimeout(r, 400));

    try {
      const response = await fetch('/api/research/topic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goal: goal.trim(),
          max_discover: 8,
          papers_to_debate: papersToDebate,
          top_recommendations: 3,
          expand_query: true,
          debate_config: {
            max_rounds: 2,
            min_rounds: 1,
            crossfire_passes: 1,
            consensus_threshold: 0.8,
          },
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Topic research failed');
      }

      setResult(data);
      if (!data.success) {
        setBusy(false);
        onResearchEnd?.();
      }
    } catch (err) {
      setBusy(false);
      onResearchEnd?.();
      alert(err.message || 'Topic research failed. This can take 10–20 minutes.');
    }
  };

  const loadRankedPaper = async (paper) => {
    const id = paper.identifier || paper.paper_id || paper.title;
    if (onSelectPaper && id) {
      await onSelectPaper(id);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-md overflow-hidden border border-amber-200">
      <div className="bg-gradient-to-r from-amber-500 to-orange-600 px-4 py-4 text-white">
        <h2 className="font-semibold text-lg">Topic → Debate → Best Papers</h2>
        <p className="text-sm opacity-90 mt-1">
          Describe your goal. Agents find papers, debate each one, and rank the best fits.
        </p>
      </div>

      <form onSubmit={runTopicResearch} className="p-4 space-y-3">
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          rows={4}
          placeholder="e.g. I'm looking for the best evidence linking sleep fragmentation to dementia — prefer large cohorts and recent neurology journals"
          className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-amber-500 focus:border-amber-500"
        />

        <div className="flex items-center gap-3 text-sm">
          <label className="text-slate-600">Papers to debate:</label>
          <select
            value={papersToDebate}
            onChange={(e) => setPapersToDebate(Number(e.target.value))}
            className="border border-slate-300 rounded px-2 py-1"
            disabled={busy}
          >
            <option value={2}>2 (faster)</option>
            <option value={3}>3 (recommended)</option>
            <option value={4}>4</option>
            <option value={5}>5 (slow)</option>
          </select>
        </div>

        <div className="flex flex-wrap gap-2">
          {TOPIC_EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => setGoal(ex)}
              className="text-xs px-2 py-1 rounded-full bg-amber-50 text-amber-800 hover:bg-amber-100"
              disabled={busy}
            >
              {ex.length > 52 ? `${ex.slice(0, 52)}…` : ex}
            </button>
          ))}
        </div>

        <button
          type="submit"
          disabled={!goal.trim() || busy || loading}
          className="w-full bg-amber-600 text-white py-2.5 rounded-lg hover:bg-amber-700 disabled:opacity-50 font-medium"
        >
          {busy ? 'Agents researching… (10–20 min)' : 'Find & Debate Papers'}
        </button>

        {busy && latestStatus && (
          <p className="text-sm text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            {latestStatus}
          </p>
        )}

        {busy && progressLines.length > 0 && (
          <ul className="text-xs text-slate-600 space-y-1 max-h-32 overflow-y-auto border border-slate-100 rounded-lg p-2 bg-slate-50">
            {progressLines.map((line, i) => (
              <li key={`${line}-${i}`} className={i === progressLines.length - 1 ? 'font-medium text-amber-800' : ''}>
                {line}
              </li>
            ))}
          </ul>
        )}

        {busy && (
          <p className="text-xs text-slate-500">
            Pipeline: discover → shortlist → debate each paper → rank. Keep this tab open.
          </p>
        )}
      </form>

      {result?.success && (
        <div className="border-t p-4 space-y-4 bg-amber-50/50">
          <div>
            <h3 className="font-semibold text-slate-900">Society recommendation</h3>
            <p className="text-sm text-slate-700 mt-1">{result.summary}</p>
            {result.top_pick && (
              <p className="text-sm font-medium text-amber-800 mt-2">Top pick: {result.top_pick}</p>
            )}
          </div>

          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
              Ranked papers ({result.papers_debated} debated)
            </h4>
            {(result.recommendations || result.ranked_papers || []).map((paper, index) => (
              <div
                key={`${paper.paper_id || paper.title}-${index}`}
                className="bg-white border border-slate-200 rounded-lg p-3"
              >
                <div className="flex justify-between gap-2 items-start">
                  <div>
                    <span className="text-xs font-bold text-amber-700">#{paper.rank || index + 1}</span>
                    <h5 className="font-medium text-sm text-slate-900 mt-1">{paper.title}</h5>
                  </div>
                  <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded shrink-0">
                    {Math.round((paper.overall_score || 0) * 100)}% fit
                  </span>
                </div>
                <p className="text-xs text-slate-600 mt-2">{paper.recommendation}</p>
                {paper.strengths?.length > 0 && (
                  <p className="text-xs text-green-700 mt-1">+ {paper.strengths.slice(0, 2).join('; ')}</p>
                )}
                {paper.weaknesses?.length > 0 && (
                  <p className="text-xs text-red-600">− {paper.weaknesses.slice(0, 2).join('; ')}</p>
                )}
                <div className="flex gap-2 mt-3">
                  <button
                    type="button"
                    onClick={() => loadRankedPaper(paper)}
                    className="text-xs bg-slate-900 text-white px-3 py-1 rounded-full"
                  >
                    Load for full debate
                  </button>
                  {paper.verdict && (
                    <span className="text-xs text-slate-500 self-center">Verdict: {paper.verdict}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {result && !result.success && (
        <div className="border-t p-4 text-sm text-red-700 bg-red-50">
          {result.error || 'No papers found for this topic.'}
        </div>
      )}
    </div>
  );
};

export default TopicRanker;
