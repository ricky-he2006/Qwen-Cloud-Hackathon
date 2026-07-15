import React from 'react';

const ChatLog = ({ messages }) => {
  const agentColors = {
    executive_moderator: 'bg-purple-100 border-purple-300',
    structure_analyst: 'bg-blue-100 border-blue-300',
    paper_structure_analyst: 'bg-blue-100 border-blue-300',
    contribution_scout: 'bg-green-100 border-green-300',
    contribution_specialist: 'bg-green-100 border-green-300',
    methodology_critic: 'bg-red-100 border-red-300',
    methodology_expert: 'bg-red-100 border-red-300',
    literature_reviewer: 'bg-yellow-100 border-yellow-300',
    literature_specialist: 'bg-yellow-100 border-yellow-300',
  };

  const agentIcons = {
    executive_moderator: '⚖️',
    structure_analyst: '🏗️',
    paper_structure_analyst: '🏗️',
    contribution_scout: '✨',
    contribution_specialist: '✨',
    methodology_critic: '🔬',
    methodology_expert: '🔬',
    literature_reviewer: '📚',
    literature_specialist: '📚',
  };

  const formatRole = (role) =>
    role.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  const typeStyles = {
    opening: 'bg-blue-100 text-blue-700',
    debate: 'bg-purple-100 text-purple-700',
    rebuttal: 'bg-orange-100 text-orange-700',
    synthesis: 'bg-slate-800 text-white',
    planning: 'bg-indigo-100 text-indigo-700',
  };

  const typeLabels = {
    opening: 'opening',
    debate: 'crossfire',
    rebuttal: 'rebuttal',
    synthesis: 'synthesis',
    planning: 'planning',
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
      {messages.length === 0 ? (
        <p className="text-center text-slate-400 italic">Debate hasn't started yet...</p>
      ) : (
        messages.map((msg, index) => (
          <div key={index} className={`flex ${index % 2 === 0 ? 'justify-start' : 'justify-end'}`}>
            <div
              className={`max-w-[80%] rounded-lg p-4 border ${
                agentColors[msg.role] || 'bg-white border-gray-300'
              } ${msg.message_type === 'debate' ? 'ring-2 ring-purple-200' : ''}`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg">{agentIcons[msg.role] || '🤖'}</span>
                <span className="font-semibold text-sm">
                  {msg.agent_name || formatRole(msg.role || '')}
                </span>
                {msg.message_type && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${typeStyles[msg.message_type] || 'bg-slate-100 text-slate-600'}`}>
                    {typeLabels[msg.message_type] || msg.message_type}
                  </span>
                )}
                {msg.stance && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    msg.stance === 'agree' ? 'bg-green-100 text-green-700' :
                    msg.stance === 'disagree' ? 'bg-red-100 text-red-700' :
                    'bg-slate-100 text-slate-600'
                  }`}>
                    {msg.stance}
                  </span>
                )}
                <span className="text-xs text-slate-400 ml-auto">
                  Round {msg.round_num} • Turn {msg.turn}
                </span>
              </div>
              {msg.message_type === 'debate' && (
                <div className="text-xs font-semibold text-purple-700 mb-2">
                  Direct response to another reviewer
                </div>
              )}
              <p className="text-sm text-slate-800 whitespace-pre-wrap leading-relaxed">
                {msg.content}
              </p>
              {typeof msg.confidence === 'number' && msg.confidence > 0 && (
                <div className="mt-3">
                  <div className="flex justify-between text-[11px] text-slate-500 mb-1">
                    <span>confidence</span>
                    <span>{Math.round(msg.confidence * 100)}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/70 overflow-hidden">
                    <div
                      className="h-full bg-slate-700/50"
                      style={{ width: `${Math.round(msg.confidence * 100)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  );
};

export default ChatLog;
