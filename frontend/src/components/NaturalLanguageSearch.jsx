import React, { useState } from 'react';

const EXAMPLES = [
  'Find recent papers on slow-wave sleep and dementia risk',
  'Good cohort studies on GLP-1 agonists and cardiovascular outcomes',
  'https://jamanetwork.com/journals/jamaneurology/fullarticle/2810957',
  '10.1001/jamaneurol.2023.3889',
  'Attention Is All You Need transformer paper',
];

function detectMode(text) {
  const raw = text.trim();
  if (!raw) return 'empty';
  if (raw.startsWith('http')) return 'direct';
  if (/^10\.\d{4,9}\//.test(raw)) return 'direct';
  if (/^(pmid:)?\d{7,8}$/i.test(raw)) return 'direct';
  if (/^\d{4}\.\d{5}/.test(raw)) return 'direct';
  const lower = raw.toLowerCase();
  if (['find', 'search', 'papers on', 'studies on', 'looking for', 'i want', 'recommend'].some((m) => lower.includes(m))) {
    return 'discover';
  }
  if (raw.split(/\s+/).length >= 6) return 'discover';
  return 'direct';
}

const NaturalLanguageSearch = ({
  paperData,
  onPaperLoaded,
  onSelectPaper,
  onStartDebate,
  debateDisabled,
  loading,
}) => {
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState(null);
  const [results, setResults] = useState(null);
  const [searchQueries, setSearchQueries] = useState([]);
  const [status, setStatus] = useState('');

  const predicted = detectMode(query);

  const runQuery = async (text) => {
    const q = (text ?? query).trim();
    if (!q) return;

    setBusy(true);
    setResults(null);
    setSearchQueries([]);
    setStatus('Understanding your request…');

    try {
      const response = await fetch('/api/paper/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, max_results: 8, expand_query: true }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Query failed');
      }

      setMode(data.mode);

      if (data.mode === 'direct' && data.success && data.paper) {
        setStatus('Loaded paper — ready for debate');
        onPaperLoaded({
          success: true,
          ...data.paper,
        });
        setResults(null);
      } else if (data.mode === 'discover') {
        setSearchQueries(data.search_queries || []);
        setResults(data.results || []);
        setStatus(
          data.direct_failed
            ? 'Could not load directly — here are matching papers from the web'
            : `Found ${data.results?.length || 0} papers on the scholarly web`
        );
      } else {
        setStatus(data.hint || data.error_message || 'No results');
        alert(data.hint || data.error_message || 'Could not find papers');
      }
    } catch (err) {
      setStatus('');
      alert(err.message || 'Search failed. Is the backend running?');
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    runQuery();
  };

  const handlePick = async (paper) => {
    const id = paper.identifier || paper.paper_id || paper.title;
    setStatus('Loading full paper text…');
    await onSelectPaper(id);
    setStatus('Paper loaded');
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl shadow-md overflow-hidden border border-slate-200">
        <div className="bg-gradient-to-r from-slate-900 via-indigo-900 to-purple-900 px-4 py-4 text-white">
          <h2 className="font-semibold text-lg">Review one paper</h2>
          <p className="text-sm opacity-90 mt-1">
            Paste a URL, DOI, or title — or search and pick one to load
          </p>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-3">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={4}
            placeholder="e.g. Find good recent papers on sleep fragmentation and dementia in large cohorts…"
            className="w-full px-4 py-3 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
          />

          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => {
                  setQuery(ex);
                }}
                className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 hover:bg-indigo-100 hover:text-indigo-800 transition-colors"
              >
                {ex.length > 48 ? `${ex.slice(0, 48)}…` : ex}
              </button>
            ))}
          </div>

          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-slate-500">
              {predicted === 'discover'
                ? 'Will search OpenAlex, PubMed & arXiv'
                : predicted === 'direct'
                  ? 'Will load this paper directly'
                  : 'Type a question or paste a link'}
            </span>
            <button
              type="submit"
              disabled={!query.trim() || busy || loading}
              className="shrink-0 bg-indigo-600 text-white px-5 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm font-medium"
            >
              {busy ? 'Working…' : predicted === 'discover' ? 'Search' : 'Go'}
            </button>
          </div>

          {status && (
            <p className="text-sm text-indigo-700 bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2">
              {status}
            </p>
          )}

          {searchQueries.length > 0 && (
            <p className="text-xs text-slate-500">
              <span className="font-medium">Expanded to:</span> {searchQueries.join(' · ')}
            </p>
          )}
        </form>
      </div>

      {results && results.length > 0 && (
        <div className="bg-white rounded-xl shadow-md border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b bg-slate-50">
            <h3 className="font-semibold text-slate-800">Pick one to review</h3>
            <p className="text-xs text-slate-500">Load full text, then start a deep agent debate on this paper</p>
          </div>
          <div className="p-3 space-y-2 max-h-[380px] overflow-y-auto">
            {results.map((paper, index) => (
              <button
                key={`${paper.paper_id}-${index}`}
                type="button"
                onClick={() => handlePick(paper)}
                disabled={loading}
                className="w-full text-left border border-slate-200 rounded-lg p-3 hover:border-indigo-400 hover:bg-indigo-50 transition-colors disabled:opacity-50"
              >
                <div className="flex justify-between gap-2">
                  <span className="font-medium text-sm text-slate-900">{paper.title}</span>
                  <span className="text-[10px] uppercase bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                    {paper.source}
                  </span>
                </div>
                {paper.authors?.length > 0 && (
                  <p className="text-xs text-slate-500 mt-1">
                    {paper.authors.slice(0, 3).join(', ')}
                    {paper.published_date ? ` · ${paper.published_date}` : ''}
                  </p>
                )}
                {paper.abstract && (
                  <p className="text-xs text-slate-600 mt-2 line-clamp-2">{paper.abstract}</p>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {paperData && (
        <div className="bg-white rounded-xl shadow-md border border-green-200 overflow-hidden">
          <div className="px-4 py-3 border-b bg-green-50 flex justify-between items-center">
            <h3 className="font-semibold text-green-900">Ready to analyze</h3>
            {paperData.type && (
              <span className="text-xs bg-white text-green-700 px-2 py-0.5 rounded border border-green-200">
                via {paperData.type}
              </span>
            )}
          </div>
          <div className="p-4">
            <p className="font-medium text-slate-900">{paperData.title}</p>
            {paperData.authors?.length > 0 && (
              <p className="text-xs text-slate-500 mt-1">
                {paperData.authors.slice(0, 4).join(', ')}
              </p>
            )}
            <p className="text-sm text-slate-600 mt-3 line-clamp-4">
              {paperData.abstract || 'Abstract loaded from paper sections.'}
            </p>
            {paperData.sections && (
              <p className="text-xs text-green-700 mt-2">
                {Object.keys(paperData.sections).length} sections loaded
              </p>
            )}
            <button
              type="button"
              onClick={onStartDebate}
              disabled={debateDisabled}
              className="mt-4 w-full bg-green-600 text-white py-2.5 rounded-lg hover:bg-green-700 disabled:opacity-50 font-medium"
            >
              Start Agent Debate
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default NaturalLanguageSearch;
