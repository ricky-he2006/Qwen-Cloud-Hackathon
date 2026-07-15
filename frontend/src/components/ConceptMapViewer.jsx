import React from 'react';

const LAYER_BG = {
  0: '#eef2ff',
  1: '#f5f3ff',
  2: '#ecfdf5',
  3: '#fffbeb',
  4: '#fef2f2',
};

const TAKEAWAY_LABELS = [
  ['contribution', 'Contribution'],
  ['methods', 'Methods'],
  ['findings', 'Findings'],
  ['limitations', 'Limitations'],
  ['open_questions', 'Open questions'],
];

function ConceptMapViewer({ conceptMap }) {
  if (!conceptMap?.map?.nodes?.length) {
    if (conceptMap?.svg) {
      return (
        <div
          className="w-full overflow-auto rounded-lg border border-slate-200 bg-white p-2"
          dangerouslySetInnerHTML={{ __html: conceptMap.svg }}
        />
      );
    }
    return null;
  }

  const { map } = conceptMap;
  const nodes = map.nodes;
  const edges = map.edges || [];
  const nodeById = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const keyPoints = conceptMap.key_points || map.key_points || [];
  const takeaways = conceptMap.takeaways || map.takeaways || {};
  const summary = conceptMap.summary || map.summary;
  const central = conceptMap.central_concept || map.central_concept;

  const padding = 80;
  const maxX = Math.max(...nodes.map((n) => n.x + n.width / 2), 400) + padding;
  const maxY = Math.max(...nodes.map((n) => n.y + n.height / 2), 300) + padding;
  const minY = Math.min(...nodes.map((n) => n.y - n.height / 2), 0) - padding;
  const width = maxX + padding;
  const height = maxY - minY + padding;
  const offsetY = -minY + padding / 2;

  const edgePath = (sx, sy, tx, ty) => {
    const dx = tx - sx;
    if (Math.abs(dx) < 40) return `M ${sx} ${sy} L ${tx} ${ty}`;
    const cx1 = sx + dx * 0.45;
    const cx2 = tx - dx * 0.45;
    return `M ${sx} ${sy} C ${cx1} ${sy}, ${cx2} ${ty}, ${tx} ${ty}`;
  };

  const layers = [...new Set(nodes.map((n) => n.layer))].sort((a, b) => a - b);
  const detailNodes = [...nodes].sort((a, b) => (b.importance || 0) - (a.importance || 0));

  return (
    <div className="space-y-4">
      {central && (
        <div className="bg-indigo-50 border border-indigo-100 rounded-lg px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Central finding</p>
          <p className="text-sm font-medium text-indigo-950 mt-1">{central}</p>
          {summary && <p className="text-sm text-indigo-900 mt-2 leading-relaxed">{summary}</p>}
        </div>
      )}

      {keyPoints.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-lg px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
            Key points (judge briefing)
          </p>
          <ul className="space-y-1.5 list-disc list-inside text-sm text-slate-800">
            {keyPoints.map((point, i) => (
              <li key={i} className="leading-snug">{point}</li>
            ))}
          </ul>
        </div>
      )}

      {TAKEAWAY_LABELS.some(([k]) => takeaways[k]) && (
        <div className="grid sm:grid-cols-2 gap-3">
          {TAKEAWAY_LABELS.map(([key, label]) =>
            takeaways[key] ? (
              <div key={key} className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
                <p className="text-sm text-slate-800 mt-1 leading-snug">{takeaways[key]}</p>
              </div>
            ) : null
          )}
        </div>
      )}

      <div className="overflow-auto rounded-lg border border-slate-200 bg-slate-50">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full min-w-[720px]"
          role="img"
          aria-label="Paper concept map"
        >
          <rect width={width} height={height} fill="#f8fafc" />

          <defs>
            <marker id="map-arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
              <path d="M0,0 L10,4 L0,8 z" fill="#64748b" />
            </marker>
            <filter id="map-shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.15" />
            </filter>
          </defs>

          {layers.map((layer) => {
            const colX = 120 + layer * 200 - 70;
            const label = map.layer_labels?.[layer] || map.layer_labels?.[String(layer)] || 'Concepts';
            return (
              <g key={`layer-${layer}`}>
                <rect
                  x={colX}
                  y={offsetY + 20}
                  width={180}
                  height={height - offsetY - 60}
                  rx={12}
                  fill={LAYER_BG[layer] || '#f1f5f9'}
                  opacity={0.9}
                />
                <text
                  x={colX + 90}
                  y={offsetY + 8}
                  textAnchor="middle"
                  fontSize={11}
                  fontWeight={600}
                  fill="#475569"
                >
                  {label}
                </text>
              </g>
            );
          })}

          {edges.map((edge, i) => {
            const src = nodeById[edge.source];
            const tgt = nodeById[edge.target];
            if (!src || !tgt) return null;
            const x1 = src.x + src.width / 2;
            const y1 = src.y + offsetY;
            const x2 = tgt.x - tgt.width / 2;
            const y2 = tgt.y + offsetY;
            const mx = (x1 + x2) / 2;
            const my = (y1 + y2) / 2 - 6;
            return (
              <g key={`edge-${i}`}>
                <path
                  d={edgePath(x1, y1, x2, y2)}
                  fill="none"
                  stroke="#94a3b8"
                  strokeWidth={2}
                  markerEnd="url(#map-arrow)"
                />
                {edge.label && (
                  <>
                    <rect x={mx - 38} y={my - 10} width={76} height={16} rx={4} fill="white" opacity={0.95} />
                    <text x={mx} y={my + 2} textAnchor="middle" fontSize={9} fill="#64748b">
                      {edge.label.slice(0, 16)}
                    </text>
                  </>
                )}
              </g>
            );
          })}

          {nodes.map((node) => {
            const x = node.x - node.width / 2;
            const y = node.y + offsetY - node.height / 2;
            const imp = node.importance || 1;
            return (
              <g key={node.id}>
                <rect
                  x={x}
                  y={y}
                  width={node.width}
                  height={node.height}
                  rx={10}
                  fill={node.color}
                  stroke={imp >= 3 ? '#1e293b' : '#334155'}
                  strokeWidth={imp >= 3 ? 3 : 2}
                  filter="url(#map-shadow)"
                />
                <text
                  x={node.x}
                  y={node.y + offsetY + 4}
                  textAnchor="middle"
                  fontSize={11}
                  fontWeight="bold"
                  fill="white"
                >
                  {node.label.length > 20 ? `${node.label.slice(0, 18)}…` : node.label}
                </text>
                {node.description && <title>{node.description}</title>}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
          Node details
        </p>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {detailNodes.map((node) => (
            <div key={node.id} className="flex gap-3 text-sm border-b border-slate-100 pb-2 last:border-0">
              <span
                className="mt-1 h-2.5 w-2.5 rounded-full shrink-0"
                style={{ backgroundColor: node.color }}
              />
              <div>
                <p className="font-medium text-slate-900">
                  {node.label}{' '}
                  <span className="text-xs font-normal text-slate-400">({node.type})</span>
                </p>
                {node.description && (
                  <p className="text-slate-600 mt-0.5 leading-snug">{node.description}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <p className="text-xs text-slate-500">
        Flow reads left → right: background → methods → results → conclusions. Hover nodes for details.
      </p>
    </div>
  );
}

export default ConceptMapViewer;
