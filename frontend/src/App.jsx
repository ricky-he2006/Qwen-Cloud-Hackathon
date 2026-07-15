import React, { useState, useEffect, useRef, useCallback } from 'react';
import ChatLog from './components/ChatLog.jsx';
import StatusBoard from './components/StatusBoard.jsx';
import AssignmentBoard from './components/AssignmentBoard.jsx';
import VerdictCard from './components/VerdictCard.jsx';
import BenchmarkArena from './components/BenchmarkArena.jsx';
import ConsensusThermometer from './components/ConsensusThermometer.jsx';
import DemoImpactBar from './components/DemoImpactBar.jsx';
import DebateStage from './components/DebateStage.jsx';
import CrossfireHighlights from './components/CrossfireHighlights.jsx';
import ResearchHub from './components/ResearchHub.jsx';
import ConceptMapViewer from './components/ConceptMapViewer.jsx';
import DemoChecklist from './components/DemoChecklist.jsx';

const DEBATE_PRESETS = {
  judge: {
    max_rounds: 2,
    min_rounds: 1,
    crossfire_passes: 1,
    consensus_threshold: 0.75,
    autoBenchmark: true,
    label: 'Judge Demo',
  },
  full: {
    max_rounds: 5,
    min_rounds: 3,
    crossfire_passes: 2,
    consensus_threshold: 0.8,
    autoBenchmark: false,
    label: 'Full Debate',
  },
};

function getWebSocketUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/chat`;
}

function App() {
  const [activeTab, setActiveTab] = useState('paper');
  const [paperData, setPaperData] = useState(null);
  const [debateStarted, setDebateStarted] = useState(false);
  const [messages, setMessages] = useState([]);
  const [finalReport, setFinalReport] = useState('');
  const [loadingPaper, setLoadingPaper] = useState(false);
  const [debateStatus, setDebateStatus] = useState({
    round: 0,
    agentsActive: [],
    consensusReached: false,
  });

  const [conceptMap, setConceptMap] = useState(null);
  const [factCheckResults, setFactCheckResults] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [verdict, setVerdict] = useState(null);
  const [dissentLedger, setDissentLedger] = useState([]);
  const [agreementHistory, setAgreementHistory] = useState([]);
  const [benchmark, setBenchmark] = useState(null);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [debateLoading, setDebateLoading] = useState(false);
  const [mapLoading, setMapLoading] = useState(false);
  const [factCheckLoading, setFactCheckLoading] = useState(false);
  const [debateEvents, setDebateEvents] = useState([]);
  const [topicResearchRunning, setTopicResearchRunning] = useState(false);
  const [topicEvents, setTopicEvents] = useState([]);
  const [planLoading, setPlanLoading] = useState(false);
  const [lastPreset, setLastPreset] = useState(null);

  const wsRef = useRef(null);

  const getSections = useCallback(() => {
    if (!paperData) return {};
    if (paperData.sections && Object.keys(paperData.sections).length > 0) {
      return paperData.sections;
    }
    return { abstract: paperData.abstract || '' };
  }, [paperData]);

  useEffect(() => {
    if (!debateStarted && !topicResearchRunning) return;

    const ws = new WebSocket(getWebSocketUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('Connected to agent stream');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type?.startsWith('topic_')) {
          setTopicEvents((prev) => [...prev, data]);
          return;
        }
        if (data.type === 'agent_message') {
          setMessages((prev) => [...prev, data]);
          setDebateStatus((prev) => ({
            ...prev,
            round: Math.max(prev.round, data.round_num || 0),
          }));
        } else if (data.type === 'planning_complete') {
          setAssignments(data.assignments || []);
          setDebateEvents((prev) => [...prev, data]);
        } else if (data.type === 'consensus_update') {
          setAgreementHistory((prev) => [...prev, data.agreement_level]);
          setDebateStatus((prev) => ({
            ...prev,
            round: data.round,
            consensusReached: data.consensus_reached,
          }));
          setDebateEvents((prev) => [...prev, data]);
        } else if (data.type === 'verdict_ready') {
          setVerdict(data.verdict);
          setDissentLedger(data.dissent_ledger || []);
          setDebateEvents((prev) => [...prev, data]);
        } else if (data.type === 'debate_complete') {
          setFinalReport(data.final_report || '');
          setVerdict(data.verdict || null);
          setDissentLedger(data.dissent_ledger || []);
          setAssignments(data.assignments || []);
          setAgreementHistory(data.agreement_history || []);
          setDebateStatus((prev) => ({
            ...prev,
            round: data.rounds_completed || prev.round,
            consensusReached: true,
          }));
          setDebateLoading(false);
          setDebateEvents((prev) => [...prev, data]);
        } else if (['debate_started', 'round_started', 'rebuttal_started', 'rebuttal_complete'].includes(data.type)) {
          setDebateEvents((prev) => [...prev, data]);
        }
      } catch (e) {
        console.log(event.data);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket connection closed');
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [debateStarted, topicResearchRunning]);

  const handlePaperLoaded = (data) => {
    if (data?.success !== false && data?.title) {
      setPaperData(data);
      setActiveTab('paper');
    }
  };

  const handlePaperIdentify = async (identifier) => {
    setLoadingPaper(true);
    try {
      const response = await fetch('/api/paper/fetch-full', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier }),
      });
      const data = await response.json();
      if (data.success) {
        setPaperData(data);
        setActiveTab('paper');
      } else {
        alert(data.hint || data.error_message || 'Could not find paper. Try a DOI, PubMed URL, or search terms.');
      }
    } catch (e) {
      console.error('Failed to fetch paper:', e);
      alert('Failed to connect to backend. Is the server running on port 8000?');
    } finally {
      setLoadingPaper(false);
    }
  };

  const runBenchmarkWithReport = async (paperTitle, sections, societyReport, societyMessages = []) => {
    if (!societyReport) return null;
    setBenchmarkLoading(true);
    setActiveTab('benchmark');
    try {
      const response = await fetch('/api/benchmark/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paper_title: paperTitle,
          sections,
          society_report: societyReport,
          society_messages: societyMessages,
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || 'Benchmark failed');
      }
      setBenchmark(result);
      return result;
    } catch (e) {
      console.error('Benchmark failed:', e);
      alert(e.message || 'Benchmark failed');
      return null;
    } finally {
      setBenchmarkLoading(false);
    }
  };

  const handleStartDebate = async (presetKey = 'full') => {
    if (!paperData) return;

    const preset = DEBATE_PRESETS[presetKey] || DEBATE_PRESETS.full;
    setLastPreset(presetKey);
    const sections = getSections();
    setDebateStarted(true);
    setActiveTab('assignments');
    setMessages([]);
    setFinalReport('');
    setVerdict(null);
    setDissentLedger([]);
    setAssignments([]);
    setAgreementHistory([]);
    setBenchmark(null);
    setDebateEvents([]);
    setDebateLoading(true);
    setDebateStatus({ round: 0, agentsActive: [], consensusReached: false });

    // Let WebSocket connect before long-running POST (live chamber events)
    await new Promise((r) => setTimeout(r, 400));

    try {
      const response = await fetch('/api/debate/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paper_id: paperData.paper_id,
          paper_title: paperData.title,
          sections,
          config: {
            max_rounds: preset.max_rounds,
            min_rounds: preset.min_rounds,
            crossfire_passes: preset.crossfire_passes,
            consensus_threshold: preset.consensus_threshold,
          },
        }),
      });

      if (!response.ok) {
        let detail = 'Debate failed to start';
        try {
          const err = await response.json();
          detail = err.detail || detail;
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }

      const result = await response.json();

      if (result.messages?.length) {
        setMessages(
          result.messages.map((m, i) => ({
            ...m,
            type: 'agent_message',
            turn: m.turn || i + 1,
          }))
        );
      }

      const report = result.final_report || '';
      setFinalReport(report);
      setVerdict(result.verdict || null);
      setDissentLedger(result.dissent_ledger || []);
      setAssignments(result.assignments || []);
      setAgreementHistory(result.agreement_history || []);
      setDebateStatus((prev) => ({
        ...prev,
        round: result.rounds_completed,
        consensusReached: true,
      }));
      setActiveTab('chat');

      if (preset.autoBenchmark && report) {
        const societyMessages = (result.messages || []).map(
          (m) =>
            `${m.agent_name} (${m.role}, ${m.message_type}, ${m.stance || 'neutral'}): ${m.content}`
        );
        await runBenchmarkWithReport(paperData.title, sections, report, societyMessages);
      }
    } catch (e) {
      console.error('Failed to start debate:', e);
      alert(`Debate error: ${e.message}`);
      setDebateStarted(false);
      setDebateStatus({ round: 0, agentsActive: [], consensusReached: false });
    } finally {
      setDebateLoading(false);
    }
  };

  const handlePlanOnly = async () => {
    if (!paperData) return;
    setPlanLoading(true);
    try {
      const response = await fetch('/api/debate/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paper_title: paperData.title,
          sections: getSections(),
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || 'Planning failed');
      }
      setAssignments(result.assignments || []);
      setActiveTab('paper');
    } catch (e) {
      console.error('Plan failed:', e);
      alert(e.message || 'Could not plan assignments');
    } finally {
      setPlanLoading(false);
    }
  };

  const handleBenchmark = async () => {
    if (!paperData || !finalReport) {
      alert('Run a debate first to generate a society report for comparison.');
      return;
    }

    const societyMessages = messages.map(
      (m) =>
        `${m.agent_name} (${m.role}, ${m.message_type}, ${m.stance || 'neutral'}): ${m.content}`
    );
    await runBenchmarkWithReport(paperData.title, getSections(), finalReport, societyMessages);
  };

  const handleGenerateMap = async () => {
    if (!paperData) return;
    setMapLoading(true);
    setConceptMap(null);

    try {
      const response = await fetch('/api/map/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paper_title: paperData.title,
          sections: getSections(),
        }),
      });

      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || 'Map generation failed');
      }
      setConceptMap(result);
      setActiveTab('map');
    } catch (e) {
      console.error('Failed to generate map:', e);
      alert(e.message || 'Concept map failed. Check backend and LLM connection.');
    } finally {
      setMapLoading(false);
    }
  };

  const handleFactCheck = async () => {
    if (!paperData) return;
    setFactCheckLoading(true);
    setFactCheckResults(null);

    try {
      const response = await fetch('/api/fact-check/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sections: getSections(),
          max_claims: 8,
        }),
      });

      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || 'Fact check failed');
      }
      setFactCheckResults(result);
      setActiveTab('factcheck');
    } catch (e) {
      console.error('Failed to run fact-check:', e);
      alert(e.message || 'Fact check failed. Check backend and LLM connection.');
    } finally {
      setFactCheckLoading(false);
    }
  };

  const handleExportReport = () => {
    if (!paperData) return;

    const crossfire = messages.filter((m) => m.message_type === 'debate' || m.message_type === 'rebuttal');
    const markdown = [
      `# Research Society Report: ${paperData.title}`,
      '',
      `Paper ID: ${paperData.paper_id || 'unknown'}`,
      `Rounds: ${debateStatus.round || 0}`,
      `Verdict: ${verdict?.verdict || 'pending'}`,
      '',
      '## Track 3 Proof Points',
      `- Task assignments: ${assignments.length}`,
      `- Debate messages: ${messages.length}`,
      `- Direct crossfire/rebuttal turns: ${crossfire.length}`,
      `- Dissent items: ${dissentLedger.length}`,
      `- Consensus history: ${agreementHistory.map((v) => `${Math.round(v * 100)}%`).join(' -> ') || 'pending'}`,
      '',
      '## Paper briefing (concept map)',
      conceptMap?.central_concept ? `Central finding: ${conceptMap.central_concept}` : 'Central finding: generate a concept map first.',
      conceptMap?.summary || '',
      '',
      '### Key points',
      ...((conceptMap?.key_points || []).map((p) => `- ${p}`)),
      '',
      '### Takeaways',
      conceptMap?.takeaways?.contribution ? `- Contribution: ${conceptMap.takeaways.contribution}` : '',
      conceptMap?.takeaways?.methods ? `- Methods: ${conceptMap.takeaways.methods}` : '',
      conceptMap?.takeaways?.findings ? `- Findings: ${conceptMap.takeaways.findings}` : '',
      conceptMap?.takeaways?.limitations ? `- Limitations: ${conceptMap.takeaways.limitations}` : '',
      conceptMap?.takeaways?.open_questions ? `- Open questions: ${conceptMap.takeaways.open_questions}` : '',
      '',
      '## Verdict',
      verdict?.consensus_summary || finalReport || 'Verdict pending.',
      '',
      '## Crossfire Highlights',
      ...crossfire.slice(-8).map((m) => `- **${m.agent_name}** (${m.stance || m.message_type}, round ${m.round_num}): ${m.content?.replace(/\n/g, ' ').slice(0, 500)}`),
      '',
      '## Full Report',
      finalReport || 'Final report pending.',
    ].filter((line) => line !== undefined).join('\n');

    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `research-society-${paperData.paper_id || 'report'}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const renderMapPanel = () => (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="bg-slate-100 px-4 py-3 border-b">
        <h2 className="font-semibold text-slate-800">Concept Map & Paper Briefing</h2>
        <p className="text-sm text-slate-600">
          Detailed key points, takeaways, and concept flow for judges
        </p>
      </div>
      <div className="p-6 min-h-[400px] bg-slate-50">
        {mapLoading ? (
          <div className="text-center text-slate-500 py-12">Generating concept map from paper…</div>
        ) : conceptMap ? (
          <ConceptMapViewer conceptMap={conceptMap} />
        ) : (
          <div className="text-center text-slate-500 py-12">Click Generate Concept Map to build visualization.</div>
        )}
      </div>
    </div>
  );

  const renderFactCheckPanel = () => (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="bg-slate-100 px-4 py-3 border-b">
        <h2 className="font-semibold text-slate-800">Fact Check Report</h2>
        {factCheckResults && (
          <p className="text-sm text-slate-600">
            {factCheckResults.claims_verified} of {factCheckResults.total_claims} claims verified
            {factCheckResults.total_claims > 0 &&
              ` (${Math.round((factCheckResults.claims_verified / factCheckResults.total_claims) * 100)}%)`}
          </p>
        )}
      </div>
      <div className="p-6 space-y-4">
        {factCheckLoading && (
          <div className="text-center text-slate-500 py-8">Extracting and cross-referencing claims…</div>
        )}
        {factCheckResults?.results?.length === 0 && !factCheckLoading && (
          <div className="text-center text-slate-500 py-8">No verifiable claims found in paper sections.</div>
        )}
        {factCheckResults?.results?.map((result, index) => (
          <div
            key={index}
            className={`border rounded-lg p-4 ${result.is_verified ? 'bg-green-50 border-green-100' : 'bg-red-50 border-red-100'}`}
          >
            <span
              className={`inline-block px-2 py-1 rounded text-xs font-bold mb-2 ${
                result.is_verified ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}
            >
              {result.is_verified ? 'VERIFIED' : 'UNVERIFIED'} ({(result.confidence * 100).toFixed(0)}%)
            </span>
            <p className="text-sm font-medium mt-2">{result.claim_text}</p>
            {result.cross_references?.length > 0 && (
              <div className="mt-3 pt-3 border-t">
                <p className="text-xs font-semibold text-slate-500 mb-2">Cross-References:</p>
                <ul className="space-y-1">
                  {result.cross_references.map((ref, i) => (
                    <li key={i} className="text-sm text-slate-700">
                      • {ref.title || ref.id}
                      {ref.url && (
                        <a href={ref.url} target="_blank" rel="noreferrer" className="text-blue-600 ml-1">link</a>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-primary-600 text-white shadow-lg">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold">Research Society</h1>
          <p className="text-sm opacity-80">Single-paper debate or topic-based paper ranking</p>
        </div>

        {(paperData || debateStarted) && (
          <nav className="border-t border-primary-500">
            <div className="container mx-auto px-4 flex flex-wrap gap-4 py-2 text-sm font-medium">
              {paperData && (
                <button onClick={() => setActiveTab('paper')} className={`pb-3 border-b-2 ${activeTab === 'paper' ? 'border-white text-white' : 'border-transparent text-primary-100 hover:text-white'}`}>
                  Paper
                </button>
              )}
              {paperData && (
                <>
                  <button onClick={handleGenerateMap} disabled={mapLoading} className={`pb-3 border-b-2 ${activeTab === 'map' ? 'border-white text-white' : 'border-transparent text-primary-100 hover:text-white'} disabled:opacity-50`}>
                    {mapLoading ? 'Map…' : 'Concept Map'}
                  </button>
                  <button onClick={handleFactCheck} disabled={factCheckLoading} className={`pb-3 border-b-2 ${activeTab === 'factcheck' ? 'border-white text-white' : 'border-transparent text-primary-100 hover:text-white'} disabled:opacity-50`}>
                    {factCheckLoading ? 'Checking…' : 'Fact Check'}
                  </button>
                </>
              )}
              {debateStarted && (
                <>
                  <button onClick={() => setActiveTab('assignments')} className={`pb-3 border-b-2 ${activeTab === 'assignments' ? 'border-white text-white' : 'border-transparent text-primary-100 hover:text-white'}`}>
                    Assignment Board
                  </button>
                  <button onClick={() => setActiveTab('chat')} className={`pb-3 border-b-2 ${activeTab === 'chat' ? 'border-white text-white' : 'border-transparent text-primary-100 hover:text-white'}`}>
                    Debate Chat
                  </button>
                  <button onClick={() => setActiveTab('verdict')} className={`pb-3 border-b-2 ${activeTab === 'verdict' ? 'border-white text-white' : 'border-transparent text-primary-100 hover:text-white'}`}>
                    Verdict
                  </button>
                  <button onClick={handleBenchmark} disabled={!finalReport || benchmarkLoading} className={`pb-3 border-b-2 ${activeTab === 'benchmark' ? 'border-white text-white' : 'border-transparent text-primary-100 hover:text-white'} disabled:opacity-50`}>
                    Benchmark
                  </button>
                </>
              )}
            </div>
          </nav>
        )}
      </header>

      <main className="container mx-auto px-4 py-6">
        {!debateStarted ? (
          <div className="space-y-6">
            {paperData && (
              <>
                <DemoImpactBar
                  paperData={paperData}
                  assignments={assignments}
                  messages={messages}
                  agreementHistory={agreementHistory}
                  verdict={verdict}
                  benchmark={benchmark}
                  dissentLedger={dissentLedger}
                />
                <DemoChecklist
                  paperData={paperData}
                  conceptMap={conceptMap}
                  assignments={assignments}
                  debateStarted={debateStarted}
                  debateDone={Boolean(finalReport && verdict)}
                  dissentCount={
                    dissentLedger.length +
                    messages.filter((m) => m.stance === 'disagree' || m.message_type === 'rebuttal').length
                  }
                  benchmark={benchmark}
                  onRunJudgeDemo={() => handleStartDebate('judge')}
                  onPlanOnly={handlePlanOnly}
                  onGenerateMap={handleGenerateMap}
                  onBenchmark={handleBenchmark}
                  busy={
                    debateLoading ||
                    mapLoading ||
                    planLoading ||
                    benchmarkLoading ||
                    factCheckLoading ||
                    topicResearchRunning
                  }
                />
              </>
            )}

            {(activeTab === 'paper' || !['map', 'factcheck'].includes(activeTab)) && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-1 space-y-6">
                  <ResearchHub
                    paperData={paperData}
                    onPaperLoaded={handlePaperLoaded}
                    onSelectPaper={handlePaperIdentify}
                    onStartDebate={() => handleStartDebate('judge')}
                    debateDisabled={!paperData || debateStarted || loadingPaper || topicResearchRunning}
                    loadingPaper={loadingPaper}
                    topicEvents={topicEvents}
                    topicResearchRunning={topicResearchRunning}
                    debateStarted={debateStarted}
                    onResearchBegin={() => {
                      setTopicEvents([]);
                      setTopicResearchRunning(true);
                    }}
                    onResearchEnd={() => setTopicResearchRunning(false)}
                  />
                  <StatusBoard status={debateStatus} />
                </div>

                <div className="lg:col-span-2 bg-white rounded-lg shadow-md p-6">
                  {paperData ? (
                    <>
                  <h2 className="text-xl font-bold mb-4 text-slate-800">Next Steps</h2>
                  {paperData.sections && (
                    <p className="text-sm text-green-700 mb-4">
                      Loaded {Object.keys(paperData.sections).length} section(s)
                      {lastPreset ? ` · last run: ${DEBATE_PRESETS[lastPreset]?.label}` : ''}
                    </p>
                  )}
                      {assignments.length > 0 && !debateStarted && (
                        <div className="mb-6 border border-indigo-100 rounded-lg overflow-hidden">
                          <div className="bg-indigo-50 px-4 py-2 border-b border-indigo-100">
                            <h3 className="text-sm font-semibold text-indigo-900">Planned assignments</h3>
                            <p className="text-xs text-indigo-700">Task split preview — start Judge Demo next</p>
                          </div>
                          <AssignmentBoard assignments={assignments} />
                        </div>
                      )}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <button
                          onClick={() => handleStartDebate('judge')}
                          disabled={debateLoading}
                          className="p-4 border-2 border-indigo-400 bg-indigo-50 rounded-lg hover:border-indigo-600 hover:bg-indigo-100 transition-all text-center disabled:opacity-50 md:col-span-2"
                        >
                          <div className="text-3xl mb-2">⚖️</div>
                          <h3 className="font-semibold text-indigo-800">
                            {debateLoading ? 'Society debating…' : 'Judge Demo (recommended)'}
                          </h3>
                          <p className="text-sm text-slate-600 mt-1">
                            2 rounds · 1 crossfire · auto-benchmark — best for hackathon demo / tokens
                          </p>
                        </button>

                        <button
                          onClick={handleGenerateMap}
                          disabled={mapLoading}
                          className="p-4 border-2 border-dashed border-primary-300 rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-all text-center disabled:opacity-50"
                        >
                          <div className="text-3xl mb-2">🗺️</div>
                          <h3 className="font-semibold text-primary-700">{mapLoading ? 'Generating…' : 'Concept Map + Key Points'}</h3>
                          <p className="text-sm text-slate-600 mt-1">Detailed briefing for judges</p>
                        </button>

                        <button
                          onClick={handlePlanOnly}
                          disabled={planLoading}
                          className="p-4 border-2 border-dashed border-blue-300 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all text-center disabled:opacity-50"
                        >
                          <div className="text-3xl mb-2">📋</div>
                          <h3 className="font-semibold text-blue-700">{planLoading ? 'Planning…' : 'Plan Assignments Only'}</h3>
                          <p className="text-sm text-slate-600 mt-1">Show task split without a full debate</p>
                        </button>

                        <button
                          onClick={handleFactCheck}
                          disabled={factCheckLoading}
                          className="p-4 border-2 border-dashed border-red-300 rounded-lg hover:border-red-500 hover:bg-red-50 transition-all text-center disabled:opacity-50"
                        >
                          <div className="text-3xl mb-2">🔍</div>
                          <h3 className="font-semibold text-red-700">{factCheckLoading ? 'Checking…' : 'Run Fact Check'}</h3>
                          <p className="text-sm text-slate-600 mt-1">Cross-reference claims with related literature</p>
                        </button>

                        <button
                          onClick={() => handleStartDebate('full')}
                          disabled={debateLoading}
                          className="p-4 border-2 border-dashed border-purple-300 rounded-lg hover:border-purple-500 hover:bg-purple-50 transition-all text-center disabled:opacity-50"
                        >
                          <div className="text-3xl mb-2">🗣️</div>
                          <h3 className="font-semibold text-purple-700">Full Debate (longer)</h3>
                          <p className="text-sm text-slate-600 mt-1">5 rounds · more tokens — use after Judge Demo</p>
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="flex flex-col items-center justify-center h-[400px] text-slate-400 px-6">
                      <h2 className="text-lg font-semibold mb-2 text-slate-600">Two ways to get started</h2>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl w-full mt-4 text-left">
                        <div className="border border-indigo-100 rounded-lg p-4 bg-indigo-50/50">
                          <h3 className="font-medium text-indigo-900 text-sm">Single paper</h3>
                          <p className="text-xs text-slate-600 mt-2">
                            Paste a URL, DOI, or title — or search and pick one paper — then run a full multi-agent debate on it.
                          </p>
                        </div>
                        <div className="border border-amber-100 rounded-lg p-4 bg-amber-50/50">
                          <h3 className="font-medium text-amber-900 text-sm">Topic ranking</h3>
                          <p className="text-xs text-slate-600 mt-2">
                            Describe what you need. Agents discover papers, debate each candidate, and rank the best fits for your goal.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'map' && renderMapPanel()}
            {activeTab === 'factcheck' && renderFactCheckPanel()}
          </div>
        ) : (
          <div className="space-y-6">
            {debateLoading && (
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 text-center text-purple-800">
                Agent society is debating... This may take a few minutes.
              </div>
            )}

            <DemoImpactBar
              paperData={paperData}
              assignments={assignments}
              messages={messages}
              agreementHistory={agreementHistory}
              verdict={verdict}
              benchmark={benchmark}
              dissentLedger={dissentLedger}
            />

            <DebateStage
              debateStatus={debateStatus}
              debateEvents={debateEvents}
              messages={messages}
              assignments={assignments}
            />

            <ConsensusThermometer
              agreementHistory={agreementHistory}
              currentLevel={agreementHistory.length ? agreementHistory[agreementHistory.length - 1] : 0}
            />

            {activeTab === 'assignments' && (
              <div className="bg-white rounded-lg shadow-md overflow-hidden">
                <div className="bg-slate-100 px-4 py-3 border-b">
                  <h2 className="font-semibold text-slate-800">Assignment Board</h2>
                  <p className="text-sm text-slate-600">Moderator task decomposition — who reviews what</p>
                </div>
                <AssignmentBoard assignments={assignments} />
              </div>
            )}

            {activeTab === 'chat' && (
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                <div className="xl:col-span-2 bg-white rounded-lg shadow-md overflow-hidden h-[620px] flex flex-col">
                  <div className="bg-slate-100 px-4 py-3 border-b flex justify-between items-center">
                    <h2 className="font-semibold text-slate-800">Debate Chamber</h2>
                    <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">
                      {debateStatus.consensusReached ? 'Complete' : 'Live'} · {debateStatus.round} rounds
                    </span>
                  </div>

                  {messages.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center text-slate-400">
                      Agents are debating... messages will appear here
                    </div>
                  ) : (
                    <ChatLog messages={messages} />
                  )}

                  {finalReport && (
                    <div className="border-t p-4 bg-slate-50 max-h-48 overflow-y-auto">
                      <h3 className="font-semibold text-slate-800 mb-2">Final Report</h3>
                      <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans">{finalReport}</pre>
                    </div>
                  )}
                </div>

                <CrossfireHighlights messages={messages} onExport={handleExportReport} />
              </div>
            )}

            {activeTab === 'verdict' && (
              <div className="space-y-4">
                <VerdictCard verdict={verdict} dissentLedger={dissentLedger} />
                <CrossfireHighlights messages={messages} onExport={handleExportReport} />
                {finalReport && (
                  <div className="bg-white rounded-lg shadow-md p-4 max-h-96 overflow-y-auto">
                    <h3 className="font-semibold text-slate-800 mb-2">Full Report</h3>
                    <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans">{finalReport}</pre>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'benchmark' && (
              <div className="bg-white rounded-lg shadow-md overflow-hidden">
                <div className="bg-slate-100 px-4 py-3 border-b">
                  <h2 className="font-semibold text-slate-800">Benchmark Arena</h2>
                  <p className="text-sm text-slate-600">Agent Society vs Solo Reviewer</p>
                </div>
                <BenchmarkArena benchmark={benchmark} loading={benchmarkLoading} />
              </div>
            )}

            {activeTab === 'map' && renderMapPanel()}
            {activeTab === 'factcheck' && renderFactCheckPanel()}
          </div>
        )}

        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-semibold text-blue-900 mb-2">Hackathon demo script (Track 3)</h3>
          <ul className="text-sm text-blue-700 space-y-1">
            <li>1. Load a short paper (arXiv/DOI)</li>
            <li>2. Concept Map → show key points / takeaways</li>
            <li>3. Plan Assignments → prove task split</li>
            <li>4. <strong>Judge Demo</strong> → watch Assignment Board → Chamber (crossfire) → Verdict + Dissent</li>
            <li>5. Benchmark runs automatically after Judge Demo — call out society vs solo %</li>
            <li>6. Keep ECS Workbench screenshot + 1–3 min screen recording for Devpost</li>
          </ul>
        </div>
      </main>
    </div>
  );
}

export default App;
