"""
Concept Map Generator - layered scientific flow visualization.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import json
import hashlib
import math
import re
import textwrap

from utils.llm_client import LLMClient, Message


@dataclass
class MapNode:
    """A node in the concept map."""
    id: str
    label: str
    type: str
    description: str = ""
    position_x: float = 0.0
    position_y: float = 0.0
    width: int = 140
    height: int = 72
    color: str = "#3b82f6"
    layer: int = 0
    importance: int = 1


@dataclass
class MapEdge:
    """An edge connecting nodes in the concept map."""
    source_id: str
    target_id: str
    label: str = ""
    type: str = "relation"


class ConceptMapGenerator:
    """Generates clear left-to-right concept maps from scientific papers."""

    CATEGORY_COLORS = {
        "background": "#6366f1",
        "theory": "#8b5cf6",
        "method": "#10b981",
        "dataset": "#14b8a6",
        "result": "#f59e0b",
        "conclusion": "#ef4444",
        "concept": "#3b82f6",
    }

    LAYER_ORDER = {
        "background": 0,
        "theory": 1,
        "method": 2,
        "dataset": 2,
        "result": 3,
        "conclusion": 4,
        "concept": 2,
    }

    LAYER_LABELS = {
        0: "Background",
        1: "Theory",
        2: "Methods",
        3: "Results",
        4: "Conclusions",
    }

    LAYER_BG = {
        0: "#eef2ff",
        1: "#f5f3ff",
        2: "#ecfdf5",
        3: "#fffbeb",
        4: "#fef2f2",
    }

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.nodes: List[MapNode] = []
        self.edges: List[MapEdge] = []
        self.llm = llm_client or LLMClient()
        self.paper_title: str = ""
        self.central_concept: str = ""
        self.summary: str = ""
        self.key_points: List[str] = []
        self.takeaways: Dict[str, str] = {}

    def _generate_id(self, text: str) -> str:
        return "node_" + hashlib.md5(text.encode()).hexdigest()[:8]

    async def generate_map(
        self,
        paper_sections: Dict[str, str],
        paper_title: str = "",
    ) -> List[MapNode]:
        self.nodes = []
        self.edges = []
        self.key_points = []
        self.takeaways = {}
        self.paper_title = paper_title or "Research Paper"

        concepts, relations, meta = await self._extract_concepts(paper_sections)
        self.central_concept = meta.get("central_concept", "")
        self.summary = meta.get("summary", "")
        self.key_points = meta.get("key_points", []) or []
        self.takeaways = meta.get("takeaways", {}) or {}
        self._position_nodes_layered(concepts)
        self._build_edges(concepts, relations)
        return self.nodes

    def _parse_json_response(self, raw: str) -> dict:
        from utils.json_parse import parse_json_payload

        data = parse_json_payload(raw)
        if isinstance(data, dict):
            return data
        raise json.JSONDecodeError("No JSON object found", raw or "", 0)

    async def _extract_concepts(
        self, paper_sections: Dict[str, str]
    ) -> Tuple[List[Dict], List[Dict], Dict]:
        combined = "\n\n".join(
            f"## {section}\n{content}"
            for section, content in paper_sections.items()
            if content and len(content) > 30
        )

        if not combined.strip():
            concepts = self._fallback_extract(paper_sections)
            return concepts, [], {}

        prompt = f"""You are building a DETAILED scientific concept map and briefing for peer reviewers.

Paper Content:
{combined[:12000]}

Return JSON only with this shape:
{{
  "central_concept": "main thesis / primary finding (short phrase)",
  "summary": "2-4 sentences covering problem, approach, and outcome using specifics from the paper",
  "key_points": [
    "5-8 concrete bullets: sample size, design, key stats, comparisons, claims — no vague fluff"
  ],
  "takeaways": {{
    "contribution": "what is new vs prior work (1-2 sentences)",
    "methods": "design, cohort/data, measures, analysis (1-2 sentences with numbers when present)",
    "findings": "main results with effect sizes / metrics when available",
    "limitations": "key caveats stated or clearly implied",
    "open_questions": "what a reviewer should still probe"
  }},
  "concepts": [
    {{
      "name": "Short label (2-6 words)",
      "category": "background|theory|method|dataset|result|conclusion",
      "description": "1-2 detailed sentences grounded in the paper (include numbers/terms)",
      "importance": 1
    }}
  ],
  "relations": [
    {{
      "from": "exact concept name",
      "to": "exact concept name",
      "type": "leads_to|measures|causes|supports|contrasts|uses|finds"
    }}
  ]
}}

Rules:
- Prefer 10-16 concepts covering the full argument arc
- Use REAL paper terms (variables, populations, outcomes, models)
- Mark the central finding concept with importance 3; supporting results importance 2
- Relations must reflect scientific logic (hypothesis → method → result → conclusion)
- key_points must be specific enough for a demo / judge briefing
Return ONLY valid JSON."""

        response = await self.llm.generate_async(
            messages=[Message("user", prompt)],
            temperature=0.3,
            max_tokens=3500,
        )

        try:
            data = self._parse_json_response(response)
            concepts = []
            for c in data.get("concepts", []):
                name = c.get("name", "").strip()
                if not name:
                    continue
                category = c.get("category", "concept").lower()
                if category not in self.CATEGORY_COLORS:
                    category = "concept"
                concepts.append({
                    "id": self._generate_id(name),
                    "label": name[:40],
                    "type": category,
                    "description": str(c.get("description", ""))[:400],
                    "color": self.CATEGORY_COLORS.get(category, "#3b82f6"),
                    "layer": self.LAYER_ORDER.get(category, 2),
                    "importance": min(3, max(1, int(c.get("importance", 1)))),
                })
            relations = data.get("relations", [])
            takeaways = data.get("takeaways") or {}
            if not isinstance(takeaways, dict):
                takeaways = {}
            key_points = data.get("key_points") or []
            if isinstance(key_points, str):
                key_points = [key_points]
            key_points = [str(p).strip() for p in key_points if str(p).strip()][:10]
            meta = {
                "central_concept": data.get("central_concept", ""),
                "summary": data.get("summary", ""),
                "key_points": key_points,
                "takeaways": {
                    "contribution": str(takeaways.get("contribution", ""))[:500],
                    "methods": str(takeaways.get("methods", ""))[:500],
                    "findings": str(takeaways.get("findings", ""))[:500],
                    "limitations": str(takeaways.get("limitations", ""))[:500],
                    "open_questions": str(takeaways.get("open_questions", ""))[:500],
                },
            }
            if concepts:
                return concepts, relations, meta
        except (json.JSONDecodeError, TypeError, KeyError, ValueError):
            pass

        return self._fallback_extract(paper_sections), [], {
            "central_concept": "",
            "summary": "Fallback map from section headings (LLM parse failed).",
            "key_points": [],
            "takeaways": {},
        }

    def _fallback_extract(self, paper_sections: Dict[str, str]) -> List[Dict]:
        concepts = []
        category_order = {
            "abstract": "background",
            "introduction": "background",
            "methodology": "method",
            "methods": "method",
            "results": "result",
            "discussion": "conclusion",
            "conclusion": "conclusion",
        }

        for section, content in paper_sections.items():
            if not content:
                continue
            cat = category_order.get(section.lower(), "concept")
            label = section.replace("_", " ").title()
            concepts.append({
                "id": self._generate_id(section),
                "label": label[:36],
                "type": cat,
                "description": content[:220],
                "color": self.CATEGORY_COLORS.get(cat, "#3b82f6"),
                "layer": self.LAYER_ORDER.get(cat, 2),
                "importance": 2 if cat == "result" else 1,
            })

        return concepts

    def _node_dimensions(self, concept: Dict) -> Tuple[int, int]:
        label = concept["label"]
        importance = concept.get("importance", 1)
        width = min(200, max(120, 8 * len(label) + 24))
        height = 64 if importance < 3 else 80
        return width, height

    def _position_nodes_layered(self, concepts: List[Dict]):
        if not concepts:
            return

        by_layer: Dict[int, List[Dict]] = {}
        for c in concepts:
            layer = c.get("layer", self.LAYER_ORDER.get(c["type"], 2))
            by_layer.setdefault(layer, []).append(c)

        margin_x, margin_y = 120, 130
        col_gap = 200
        row_gap = 100
        base_y = 200

        for layer in sorted(by_layer.keys()):
            group = by_layer[layer]
            group.sort(key=lambda c: (-c.get("importance", 1), c["label"]))
            x = margin_x + layer * col_gap
            total_height = len(group) * row_gap
            start_y = base_y - total_height / 2 + row_gap / 2

            for i, concept in enumerate(group):
                w, h = self._node_dimensions(concept)
                y = start_y + i * row_gap

                self.nodes.append(MapNode(
                    id=concept["id"],
                    label=concept["label"],
                    type=concept["type"],
                    description=concept.get("description", ""),
                    position_x=x,
                    position_y=y,
                    width=w,
                    height=h,
                    color=concept.get("color", "#3b82f6"),
                    layer=layer,
                    importance=concept.get("importance", 1),
                ))

    def _build_edges(self, concepts: List[Dict], relations: List[Dict]):
        label_to_id = {}
        for c in concepts:
            label_to_id[c["label"].lower()] = c["id"]
            label_to_id[c["label"].lower().strip()] = c["id"]

        for rel in relations:
            src = rel.get("from", "").strip().lower()
            tgt = rel.get("to", "").strip().lower()
            source_id = label_to_id.get(src)
            target_id = label_to_id.get(tgt)
            if not source_id or not target_id or source_id == target_id:
                continue
            self.edges.append(MapEdge(
                source_id=source_id,
                target_id=target_id,
                label=rel.get("type", "related"),
                type=rel.get("type", "relation"),
            ))

        if self.edges:
            return

        sorted_nodes = sorted(self.nodes, key=lambda n: (n.layer, n.label))
        for i in range(len(sorted_nodes) - 1):
            if sorted_nodes[i].layer <= sorted_nodes[i + 1].layer:
                self.edges.append(MapEdge(
                    source_id=sorted_nodes[i].id,
                    target_id=sorted_nodes[i + 1].id,
                    label="flows to",
                    type="flows_to",
                ))

    def _wrap_label(self, text: str, max_chars: int = 16) -> List[str]:
        return textwrap.wrap(text, width=max_chars) or [text[:max_chars]]

    def _edge_path(self, sx: float, sy: float, tx: float, ty: float) -> str:
        dx = tx - sx
        if abs(dx) < 40:
            return f"M {sx} {sy} L {tx} {ty}"
        cx1 = sx + dx * 0.45
        cx2 = tx - dx * 0.45
        return f"M {sx} {sy} C {cx1} {sy}, {cx2} {ty}, {tx} {ty}"

    def _svg_width(self) -> int:
        if not self.nodes:
            return 1000
        max_x = max(n.position_x + n.width / 2 for n in self.nodes)
        return int(max(1000, max_x + 160))

    def _svg_height(self) -> int:
        if not self.nodes:
            return 640
        ys = [n.position_y for n in self.nodes]
        span = max(ys) - min(ys) if ys else 0
        return int(max(640, span + 280))

    def to_svg(self) -> str:
        width = self._svg_width()
        height = self._svg_height()
        node_by_id = {n.id: n for n in self.nodes}

        if not self.nodes:
            return (
                f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
                f'<text x="{width/2}" y="{height/2}" text-anchor="middle" fill="#64748b" font-size="14">'
                f"No concepts extracted — load a paper with section text first.</text></svg>"
            )

        parts = [
            f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="Concept map">',
            "<defs>",
            '<marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">',
            '<path d="M0,0 L10,4 L0,8 z" fill="#64748b"/></marker>',
            '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">',
            '<feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.15"/></filter>',
            "</defs>",
            f'<rect width="{width}" height="{height}" fill="#f8fafc"/>',
        ]

        # Layer column backgrounds
        layers_present = sorted({n.layer for n in self.nodes})
        col_w = 200
        for layer in layers_present:
            x = 120 + layer * col_w - 70
            label = self.LAYER_LABELS.get(layer, "Concepts")
            bg = self.LAYER_BG.get(layer, "#f1f5f9")
            parts.append(
                f'<rect x="{x}" y="95" width="180" height="{height - 150}" rx="12" fill="{bg}" opacity="0.85"/>'
            )
            parts.append(
                f'<text x="{x + 90}" y="82" text-anchor="middle" font-size="11" '
                f'font-weight="600" fill="#475569">{label}</text>'
            )

        # Title block
        title = (self.paper_title or "Concept Map")[:70]
        parts.append(f'<text x="{width/2}" y="36" text-anchor="middle" font-size="16" font-weight="700" fill="#0f172a">{self._escape(title)}</text>')
        if self.central_concept:
            parts.append(
                f'<text x="{width/2}" y="58" text-anchor="middle" font-size="12" fill="#6366f1">'
                f'Central: {self._escape(self.central_concept[:80])}</text>'
            )

        # Edges behind nodes
        for edge in self.edges:
            src = node_by_id.get(edge.source_id)
            tgt = node_by_id.get(edge.target_id)
            if not src or not tgt:
                continue
            x1 = src.position_x + src.width / 2
            y1 = src.position_y
            x2 = tgt.position_x - tgt.width / 2
            y2 = tgt.position_y
            path = self._edge_path(x1, y1, x2, y2)
            parts.append(
                f'<path d="{path}" fill="none" stroke="#94a3b8" stroke-width="2" '
                f'marker-end="url(#arrow)" opacity="0.9"/>'
            )
            if edge.label:
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 8
                parts.append(
                    f'<rect x="{mx - 36}" y="{my - 10}" width="72" height="16" rx="4" fill="white" opacity="0.9"/>'
                )
                parts.append(
                    f'<text x="{mx}" y="{my + 2}" text-anchor="middle" font-size="9" fill="#64748b">'
                    f'{self._escape(edge.label[:14])}</text>'
                )

        # Nodes
        for node in self.nodes:
            x = node.position_x - node.width / 2
            y = node.position_y - node.height / 2
            stroke = "#1e293b" if node.importance >= 3 else "#334155"
            sw = 3 if node.importance >= 3 else 2
            parts.append(
                f'<rect x="{x}" y="{y}" width="{node.width}" height="{node.height}" rx="10" '
                f'fill="{node.color}" filter="url(#shadow)" stroke="{stroke}" stroke-width="{sw}"/>'
            )
            lines = self._wrap_label(node.label, max_chars=14)
            line_height = 14
            start_y = node.position_y - (len(lines) - 1) * line_height / 2
            for i, line in enumerate(lines):
                parts.append(
                    f'<text x="{node.position_x}" y="{start_y + i * line_height + 4}" '
                    f'text-anchor="middle" font-size="11" font-weight="bold" fill="white">'
                    f'{self._escape(line)}</text>'
                )
            if node.description:
                parts.append(f'<title>{self._escape(node.description)}</title>')

        # Legend
        lx, ly = 20, height - 28
        for label, color in [
            ("Background", "#6366f1"), ("Methods", "#10b981"),
            ("Results", "#f59e0b"), ("Conclusions", "#ef4444"),
        ]:
            parts.append(f'<rect x="{lx}" y="{ly}" width="12" height="12" rx="2" fill="{color}"/>')
            parts.append(f'<text x="{lx + 18}" y="{ly + 10}" font-size="10" fill="#64748b">{label}</text>')
            lx += 105

        parts.append("</svg>")
        return "\n".join(parts)

    def _escape(self, text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def to_json(self) -> Dict:
        return {
            "paper_title": self.paper_title,
            "central_concept": self.central_concept,
            "summary": self.summary,
            "key_points": self.key_points,
            "takeaways": self.takeaways,
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "type": n.type,
                    "description": n.description,
                    "x": n.position_x,
                    "y": n.position_y,
                    "width": n.width,
                    "height": n.height,
                    "color": n.color,
                    "layer": n.layer,
                    "importance": n.importance,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "label": e.label,
                    "type": e.type,
                }
                for e in self.edges
            ],
            "layer_labels": self.LAYER_LABELS,
        }
