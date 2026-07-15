import React, { useState } from 'react';

const PaperPreview = ({ paperData, onIdentify, onStartDebate, disabled, loading, hideInput = false }) => {
  const [identifier, setIdentifier] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (identifier.trim()) {
      onIdentify(identifier.trim());
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="bg-slate-100 px-4 py-3 border-b">
        <h2 className="font-semibold text-slate-800">{hideInput ? 'Loaded Paper' : 'Paper Input'}</h2>
      </div>

      <div className="p-4 space-y-4">
        {!hideInput && (
        <>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              URL, DOI, arXiv ID, PubMed ID, or search terms
            </label>
            <input
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="https://jamanetwork.com/... or 10.1001/... or 1706.03762"
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-primary-500 focus:border-primary-500"
            />
          </div>

          <button
            type="submit"
            disabled={!identifier.trim() || loading}
            className="w-full bg-primary-600 text-white py-2 px-4 rounded-md hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
          >
            {loading ? 'Fetching paper...' : 'Load Paper'}
          </button>
        </form>

        <div className="bg-slate-50 rounded-lg p-3 text-xs text-slate-600">
          <p className="mb-1"><strong>Works with any source:</strong></p>
          <ul className="list-disc list-inside space-y-1">
            <li>Publisher URLs (JAMA, Nature, Wiley, Springer, etc.)</li>
            <li>DOIs (e.g., 10.1001/jama.2023.12345)</li>
            <li>arXiv, PubMed, PMC, bioRxiv links</li>
            <li>Paper title or keyword search</li>
          </ul>
        </div>
        </>
        )}
      </div>

      {paperData && (
        <div className="border-t p-4">
          <h3 className="font-semibold text-slate-800 mb-2">Paper Details</h3>

          {paperData.type && (
            <span className="inline-block text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded mb-2">
              via {paperData.type}
            </span>
          )}

          <p className="text-sm font-medium text-slate-900 mb-1">{paperData.title}</p>
          {paperData.authors?.length > 0 && (
            <p className="text-xs text-slate-600 mb-3">
              by {paperData.authors.slice(0, 5).join(', ')}
              {paperData.authors.length > 5 ? ' et al.' : ''}
            </p>
          )}

          <div className="bg-slate-50 rounded p-3 text-sm text-slate-700 max-h-24 overflow-y-auto mb-3">
            {paperData.abstract || 'No abstract available — debate will use available sections.'}
          </div>

          {paperData.sections && Object.keys(paperData.sections).length > 0 && (
            <p className="text-xs text-green-700 mb-3">
              {Object.keys(paperData.sections).length} section(s) loaded: {Object.keys(paperData.sections).join(', ')}
            </p>
          )}

          {paperData.categories?.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-4">
              {paperData.categories.map((cat, i) => (
                <span key={i} className="px-2 py-1 bg-slate-200 rounded text-xs">
                  {cat}
                </span>
              ))}
            </div>
          )}

          <button
            onClick={onStartDebate}
            disabled={disabled}
            className={`w-full py-2 px-4 rounded-md transition-colors font-medium ${
              disabled
                ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                : 'bg-green-600 text-white hover:bg-green-700'
            }`}
          >
            Start Agent Debate
          </button>
        </div>
      )}
    </div>
  );
};

export default PaperPreview;
