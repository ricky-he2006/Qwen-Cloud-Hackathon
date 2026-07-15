# Research Society

**Track:** Agent Society (Qwen Cloud Hackathon)  
**Live demo:** http://47.90.163.80  
**Code:** https://github.com/ricky-he2006/Qwen-Cloud-Hackathon  
**Cloud:** Alibaba Cloud ECS (US Virginia) + Qwen Cloud (DashScope)

---

## Elevator pitch

Research Society is a **simulated academic review board** powered by Qwen Cloud. A moderator decomposes a scientific paper into specialist tasks; four review agents debate with openings, named crossfire, and rebuttals; minority opinions are preserved in a dissent ledger; and a final verdict is compared against a **solo reviewer baseline** so multi-agent gain is measurable—not just theatrical.

---

## Inspiration

Peer review in the real world is multi-agent by nature: methodologists, novelty/contribution reviewers, structure critics, and literature experts often disagree before a consensus forms. Most “AI review” demos collapse that into a single chat response. We wanted an agent society that mirrors how scientists actually argue—**task division, negotiation, conflict, and resolution**—and that can prove it outperforms a lone agent on a shared scoring rubric.

---

## What it does

1. **Paper intake** — Load via arXiv ID, DOI, URL, PDF path, or natural-language search (OpenAlex / PubMed / arXiv), including “best papers on X” style discovery.
2. **Concept map + judge briefing** — Qwen extracts a central finding, multi-sentence summary, key points, and takeaways (contribution, methods, findings, limitations, open questions), plus an interactive concept flow.
3. **Planning / assignment board** — The executive moderator decomposes review work into paper-specific tasks for four specialists (can preview planning *without* running a full debate).
4. **Multi-agent debate**
   - Opening positions with evidence anchors  
   - **Crossfire** (agents address each other by name)  
   - **Rebuttals** when dissent appears  
   - Live WebSocket streaming to the Debate Chamber  
5. **Verdict + dissent ledger** — ACCEPT / REVISE / REJECT with scores; minority positions kept visible (not erased by majority vote).
6. **Benchmark Arena** — Society output vs a single-agent comprehensive review on shared review dimensions, with a coverage/impact delta for Track 3 judging.
7. **Optional literature check** — Claims are cross-referenced against related arXiv hits (corroborated vs inconclusive—not a blunt “true/false”).

A **Judge Demo** preset (2 rounds, 1 crossfire pass, auto-benchmark) keeps demos token-efficient while still showing the full Track 3 story.

---

## Featured demo paper (use this for the main debate)

| Field | Value |
|-------|--------|
| **Title** | Attention Is All You Need |
| **Authors** | Vaswani et al. |
| **arXiv ID** | `1706.03762` |
| **arXiv link** | https://arxiv.org/abs/1706.03762 |
| **PDF** | https://arxiv.org/pdf/1706.03762 |
| **Why this paper** | Iconic, short enough for a video, clear methods/novelty axes so Structure / Novelty / Methods / Literature agents have distinct jobs |

**How to load it in the app**

- Paste into the paper field: `1706.03762`  
  **or**  
- Paste the full URL: `https://arxiv.org/abs/1706.03762`

---

## What to search in the video (discovery cold open)

Show **search first** (~15–20 seconds), then hard-cut to Attention for the society demo. Do **not** run a second full debate on a search hit.

### Recommended search queries (pick one)

| Priority | Type this exactly | What it shows |
|----------|-------------------|---------------|
| **Best (recommended)** | `best papers on transformers and attention mechanisms` | “Best papers on X” discovery → OpenAlex / PubMed / arXiv |
| Strong alt | `transformer attention neural machine translation` | Lands near classic NMT / Attention papers |
| Strong alt | `Attention Is All You Need Vaswani` | Title search that surfaces the exact demo paper |
| Optional flavor | `best papers on slow-wave sleep loss and dementia for a clinical researcher` | Built-in example style in the UI (different domain) |

**Video tip:** After results appear, **click one result briefly** (or hover) so judges see pick-to-load works—then cut to `1706.03762` already loaded for Concept Map → Judge Demo.

---

## Demo video script (~90–120 seconds)

**Prep before recording**

1. Open http://47.90.163.80  
2. Run **Judge Demo** once on Attention (`1706.03762`) so Chamber / Verdict / Dissent / Benchmark are ready  
3. Keep that finished tab available (or refresh path ready)  
4. Start a clean session for the search cold open

| Time | On screen | Say (approx.) |
|------|-----------|----------------|
| 0:00–0:20 | Search: `best papers on transformers and attention mechanisms` → results | “Research Society finds papers from natural language—OpenAlex, PubMed, and arXiv.” |
| 0:20–0:35 | Load `1706.03762` / cut to Attention already open · show arXiv link in address or title | “Our main review: Attention Is All You Need—arxiv.org/abs/1706.03762.” |
| 0:35–0:50 | Concept Map + key points / takeaways | “Qwen builds a judge briefing and concept map so the society starts aligned on the paper.” |
| 0:50–1:00 | Plan Assignments | “The moderator decomposes review into specialist tasks—task division, not one blob of text.” |
| 1:00–1:30 | Finished Judge Demo: Debate Chat / Chamber → Dissent → Verdict | “Specialists open, crossfire by name, and minority dissent stays in the ledger—even when the board says REVISE.” |
| 1:30–1:50 | Benchmark Arena (% / delta) | “We measure multi-agent gain against a solo Qwen reviewer on the same rubric—Track 3 proof, not theater.” |
| 1:50–2:00 | Browser bar: `http://47.90.163.80` | “Live on Alibaba Cloud ECS, powered by Qwen Cloud.” |

**Editing:** Cut spinner waits and long token streaming. Keep search live; keep debate as a finished run.

---

## How we built it

### Architecture

```
Browser (React + Vite)
    ├── REST /api/*  (FastAPI)
    └── WebSocket /ws/chat  (live agent turns)
            │
            ▼
   Debate Manager
    ├── Executive Moderator (plan, agenda, synthesize, verdict)
    └── Specialists: Structure · Novelty · Methods · Literature
            │
            ▼
   Qwen Cloud (DashScope OpenAI-compatible API)
            │
   Paper ingest: arXiv / DOI / OpenAlex / PubMed / Unpaywall
```

### Stack

| Layer | Choice |
|-------|--------|
| LLM | Qwen Cloud / DashScope (`qwen3.7-plus`, OpenAI-compatible client) |
| Backend | FastAPI, Uvicorn, WebSockets |
| Frontend | React 18, Tailwind, Vite |
| Deploy | Docker Compose on **Alibaba Cloud ECS** |
| Repo | Public MIT — https://github.com/ricky-he2006/Qwen-Cloud-Hackathon |

### Agent society design (Track 3 mapping)

| Capability | Implementation |
|------------|----------------|
| Task division | Moderator `decompose_tasks` → Assignment Board |
| Dialogue / negotiation | Openings → crossfire → rebuttals over WebSocket |
| Conflict resolution | Consensus detector + dissent ledger + REVISE/ACCEPT/REJECT |
| Measurable vs single agent | Benchmark Arena (society vs solo coverage/impact) |

Agents return structured JSON (stance, confidence, evidence anchors). The literature specialist can lightly query arXiv for related work before stating its opening position.

---

## Qwen Cloud usage

- **Endpoint:** DashScope OpenAI-compatible chat completions (`dashscope-intl`)
- **Model:** `qwen3.7-plus` for debate, mapping, fact/literature analysis, and solo benchmark baseline
- **Config:** Non-streaming Qwen3 calls pass `enable_thinking: false` for reliable dashscope completions
- **One pay-as-you-go API key** for all text agents (no Token Plan keys for backend)

We intentionally **did not** burn free Wan video quota; Track 3 value is the society, not video generation. Demo video for Devpost is a **screen recording** of the live product.

---

## Challenges we ran into

1. **Qwen3 hybrid thinking** — Non-streaming calls need `enable_thinking: false` or DashScope rejects/empties responses.
2. **API key / region mismatch** — US ECS + intl Model Studio key requires the **intl** `API_BASE_URL`, not `dashscope-us`.
3. **Long debates vs demo time** — Full 5-round debates are expensive; Judge Demo (2 rounds + auto-benchmark) keeps the story judge-complete and token-aware.
4. **Consensus ≠ “success”** — Low agreement with a REVISE verdict is a *feature* for conflict demos; we surface dissent instead of forcing fake unanimity.
5. **Naïve “fact check” labels** — External literature search often cannot “verify” paper-native claims. We reframed UI as corroboration / inconclusive so judges aren’t misled by “0% verified.”

---

## Accomplishments we’re proud of

- End-to-end **agent society** with visible planning, crossfire, dissent, and verdict  
- Natural-language **paper discovery** plus precise arXiv load for demos  
- **Live** debate chamber (not a batch dump of text)  
- **Society vs solo** benchmark as Track 3 evidence  
- Conceptual **paper briefing** (map + key points + takeaways) for rapid judge comprehension  
- Public open-source repo + **running Alibaba Cloud deployment**

---

## What we learned

- Multi-agent value shows up in **process transparency** (who owns what, who disagrees, how it’s resolved), not only in longer text.  
- Hackathon demos need a **short preset** that still hits all judging axes.  
- Cloud proof and API wiring (region, key type, thinking flags) are as important as agent prompts.

---

## What’s next

- Stronger tool-use (OpenAlex mid-debate citations with citations UI)  
- Persistent society memory across papers/sessions (MemoryAgent crossover ideas)  
- Stricter blinded human evaluation rubrics alongside the automated benchmark  
- Optional MCP/skills integrations for richer Qwen Cloud platform usage  

---

## How to try it (judges / readers)

1. Open the live app: **http://47.90.163.80**  
2. Optional discovery: search `best papers on transformers and attention mechanisms`  
3. Load the featured paper: **`1706.03762`** — https://arxiv.org/abs/1706.03762  
4. Concept Map → Plan Assignments → **Judge Demo**  
5. Watch Chamber / Verdict / Dissent → Benchmark  

Local setup and ECS deploy details are in the [README](https://github.com/ricky-he2006/Qwen-Cloud-Hackathon) and `docs/deploy-alibaba-cloud.md`.

---

## Built with

- Qwen Cloud / Alibaba DashScope  
- FastAPI · React · Docker · Alibaba Cloud ECS  
- arXiv · OpenAlex · PubMed  

---

## Team note (one-liner for Devpost)

> Research Society turns peer review into an observable agent society on Qwen Cloud—search the literature, send specialists into debate, preserve dissent, and measure multi-agent gain against a solo baseline on Alibaba Cloud.
