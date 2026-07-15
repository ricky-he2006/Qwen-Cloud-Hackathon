import React, { useState } from 'react';

const PaperDiscovery = ({ onSelectPaper, loading }) => {
  const [request, setRequest] = useState('');
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState(null);
  const [queries, setQueries] = useState([]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!request.trim()) return;

    setSearching(true);
    setResults(null);
    setQueries([]);

    try {
      const response = await fetch('/api/paper/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request: request.trim(),
          max_results: 8,
          expand_query: true,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Discovery failed');
      }
      setQueries(data.search_queries || []);
      setResults(data.results || []);
    } catch (err) {
      alert(err.message || 'Could not search for papers. Is the backend running?');
    } finally {
      setSearching(false);
    }
  };

  const handlePick = (paper) => {
    onSelectPaper(paper.identifier || paper.paper_id || paper.title);
  };

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden border border-indigo-100">
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 px-4 py-3 text-white">
        <h2 className="font-semibold">Research Discovery</h2>
        <p className="text-xs opacity-90 mt-0.5">
          Tell us what you want — we search the scholarly web (OpenAlex, PubMed, arXiv)
        </p>
      </div>

      <div className="p-4 space-y-4">
        <form onSubmit={handleSearch} className="space-y-3">
          <label className="block text-xs font-medium text-slate-600">
            What papers are you looking for?
          </label>
          <textarea
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            rows={3}
            placeholder="e.g. Recent cohort studies linking slow-wave sleep loss to dementia risk, preferably JAMA or neurology journals"
            className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-indigo-500 focus:border-indigo-500"
          />
          <button
            type="submit"
            disabled={!request.trim() || searching || loading}
            className="w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 disabled:opacity-50 text-sm font-medium"
          >
            {searching ? 'Searching scholarly web…' : 'Find Papers'}
          </button>
        </form>

        {queries.length > 0 && (
          <div className="text-xs text-slate-500">
            <span className="font-medium text-slate-600">Searched for:</span>{' '}
            {queries.join(' · ')}
          </div>
        )}

        {results && results.length === 0 && !searching && (
          <p className="text-sm text-slate-500 text-center py-4">
            No papers found. Try broader terms or paste a URL/DOI directly.
          </p>
        )}

        {results && results.length > 0 && (
          <div className="space-y-3 max-h-[420px] overflow-y-auto">
            <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
              {results.length} candidate{results.length !== 1 ? 's' : ''} — pick one to load full text
            </p>
            {results.map((paper, index) => (
              <button
                key={`${paper.paper_id}-${index}`}
                type="button"
                onClick={() => handlePick(paper)}
                disabled={loading}
                className="w-full text-left border border-slate-200 rounded-lg p-3 hover:border-indigo-400 hover:bg-indigo-50 transition-colors disabled:opacity-50"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium text-sm text-slate-900 leading-snug">{paper.title}</span>
                  <span className="text-[10px] uppercase bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded shrink-0">
                    {paper.source}
                  </span>
                </div>
                {paper.authors?.length > 0 && (
                  <p className="text-xs text-slate-500 mt-1">
                    {paper.authors.slice(0, 3).join(', ')}
                    {paper.authors.length > 3 ? ' et al.' : ''}
                    {paper.published_date ? ` · ${paper.published_date}` : ''}
                  </p>
                )}
                {paper.abstract && (
                  <p className="text-xs text-slate-600 mt-2 line-clamp-3">{paper.abstract}</p>
                )}
                <p className="text-xs text-indigo-600 mt-2 font-medium">Load &amp; debate →</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default PaperDiscovery;
