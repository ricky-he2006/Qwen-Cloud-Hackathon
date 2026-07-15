import React from 'react';

const AGENT_COLORS = {
  'Dr. Structure': 'border-blue-400 bg-blue-50',
  'Dr. Novelty': 'border-green-400 bg-green-50',
  'Dr. Methods': 'border-red-400 bg-red-50',
  'Dr. Context': 'border-amber-400 bg-amber-50',
};

const AssignmentBoard = ({ assignments }) => {
  if (!assignments?.length) {
    return (
      <div className="text-sm text-slate-500 italic p-4">
        Task assignments will appear when debate starts...
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-4">
      {assignments.map((a, i) => (
        <div
          key={i}
          className={`border-l-4 rounded-lg p-3 ${AGENT_COLORS[a.owner_name] || 'border-slate-400 bg-slate-50'}`}
        >
          <div className="flex justify-between items-start mb-1">
            <span className="font-semibold text-sm text-slate-800">{a.owner_name}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              a.status === 'complete' ? 'bg-green-100 text-green-800' :
              a.status === 'in_progress' ? 'bg-blue-100 text-blue-800' :
              'bg-slate-100 text-slate-600'
            }`}>
              {a.status}
            </span>
          </div>
          <p className="text-sm text-slate-700 mb-2">{a.task}</p>
          {a.sections?.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {a.sections.map((s) => (
                <span key={s} className="text-xs bg-white border px-1.5 py-0.5 rounded text-slate-500">
                  {s}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default AssignmentBoard;
