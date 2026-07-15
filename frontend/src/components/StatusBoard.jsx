import React from 'react';

const StatusBoard = ({ status }) => {
  const { round, agentsActive, consensusReached } = status;

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="bg-slate-100 px-4 py-3 border-b">
        <h2 className="font-semibold text-slate-800">Debate Status</h2>
      </div>

      <div className="p-4 space-y-3">
        {/* Round Indicator */}
        <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
          <span className="text-sm text-slate-600">Current Round</span>
          <span className={`px-2 py-1 rounded text-sm font-semibold ${
            consensusReached ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
          }`}>
            {consensusReached ? 'Final Report' : `Round ${round}`}
          </span>
        </div>

        {/* Agent Status */}
        <div>
          <h4 className="text-xs font-medium text-slate-500 mb-2">Active Agents</h4>
          <div className="grid grid-cols-2 gap-2">
            <AgentBadge name="Executive Moderator" role="moderator" active={true} />
            <AgentBadge name="Structure Analyst" role="analyst" active={round > 0} />
            <AgentBadge name="Contribution Scout" role="scout" active={round > 1} />
            <AgentBadge name="Methodology Critic" role="critic" active={round > 2} />
          </div>
        </div>

        {/* Progress Bar */}
        <div>
          <h4 className="text-xs font-medium text-slate-500 mb-2">Progress</h4>
          <div className="w-full bg-slate-200 rounded-full h-2">
            <div
              className={`h-2 rounded-full ${
                consensusReached ? 'bg-green-500' : 'bg-primary-600'
              }`}
              style={{ width: `${consensusReached ? 100 : Math.min(round * 20, 100)}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {consensusReached
              ? 'Debate complete. Final report generated.'
              : `${Math.min(round * 20, 100)}% complete`}
          </p>
        </div>
      </div>
    </div>
  );
};

const AgentBadge = ({ name, role, active }) => {
  const roleColors = {
    moderator: 'bg-purple-50 text-purple-700 border-purple-200',
    analyst: 'bg-blue-50 text-blue-700 border-blue-200',
    scout: 'bg-green-50 text-green-700 border-green-200',
    critic: 'bg-red-50 text-red-700 border-red-200',
  };

  return (
    <div
      className={`px-2 py-1 rounded text-xs border ${
        active ? roleColors[role] : 'bg-slate-50 text-slate-400 border-slate-200'
      }`}
    >
      {active ? '✓' : '○'} {name}
    </div>
  );
};

export default StatusBoard;
