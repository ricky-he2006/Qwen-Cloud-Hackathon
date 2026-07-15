# Research Society

Multi-agent scientific paper review board powered by **Qwen Cloud**. Specialists decompose a paper, debate with hand-raising and rebuttals, build concept maps, and fact-check claims.

Built for the [Qwen Cloud Hackathon](https://qwencloud-hackathon.devpost.com/) — **Track 3: Agent Society**.

### Judge Demo path (recommended)

1. Load a short paper → **Concept Map + Key Points**
2. **Plan Assignments Only** (show task split)
3. **Judge Demo** — 2 rounds, 1 crossfire, auto-benchmark (token-friendly)
4. Show Chamber crossfire → Verdict + **Dissent Ledger** → Benchmark % vs solo
5. Deploy on Alibaba ECS + Workbench screenshot + 1–3 min screen recording

---

## Do I only need an API key? Or cloud deploy too?

| Goal | What you need |
|------|----------------|
| **Run / develop locally** | One DashScope **pay-as-you-go** API key (`sk-...`) |
| **Hackathon submission (required proof)** | Same API key **plus** the app running on **Alibaba Cloud ECS or SAS** + screenshot from Workbench |

**Calling the Qwen API from your laptop is not enough** for Proof of Alibaba Cloud Deployment. Judges want the backend hosted on Alibaba Cloud (ECS/SAS), with a Workbench screenshot showing the running instance.

Paper discovery (OpenAlex / PubMed / arXiv) needs **no paid keys**. One DashScope key covers Qwen chat.

Use **pay-as-you-go** (`sk-...` + `dashscope-intl...`). Do **not** use Token Plan keys (`sk-sp-...`) for this backend — they use a different base URL and are for interactive tools only.

---

## Quick start (your machine + Qwen Cloud API)

### 1. Get your API key

1. Sign up at [qwencloud.com](https://qwencloud.com)
2. Create a key at [home.qwencloud.com/api-keys](https://home.qwencloud.com/api-keys) → `sk-...`
3. Free tier includes a large token allowance for new accounts

### 2. Configure environment

```bash
# From repo root — template with comments:
cp .env.example backend/.env
# Edit backend/.env → set API_KEY=sk-...
```

Only required fields:

```env
API_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
API_KEY=sk-your-real-key
MODEL_NAME=qwen3.7-plus
```

### 3. Run backend + frontend

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

Health check: `curl http://localhost:8000/api/health`

---

## Deploy on Alibaba Cloud (hackathon proof)

This hosts the **whole app** (UI + API) on Alibaba Cloud so outbound calls go to Qwen from that server.

Full guide: **[docs/deploy-alibaba-cloud.md](docs/deploy-alibaba-cloud.md)**

### Checklist

1. Create **ECS** or **SAS** (Ubuntu 22.04+; Docker image on SAS is fine)
2. Open security/firewall ports: **22** (SSH, your IP), **80** (HTTP)
3. SSH or **Workbench** into the instance
4. Clone this repo, install Docker (or use `deploy/bootstrap-ecs.sh`)
5. Configure secrets and deploy:

```bash
git clone <your-public-repo> && cd Research_Society
sudo bash deploy/bootstrap-ecs.sh   # if Docker not installed
cp .env.example .env
nano .env                           # set API_KEY=sk-...
bash deploy/deploy.sh
```

6. Open `http://<PUBLIC_IP>` in a browser
7. Screenshot **Workbench overview** of the running instance for Devpost proof

### API vs hosting (don’t confuse them)

```
Your laptop  ──API──►  DashScope (Qwen)     ← enough for local demos
     │
Alibaba ECS  ──API──►  DashScope (Qwen)     ← required for proof of deploy
     └── serves React + FastAPI on port 80
```

---

## Environment reference

Canonical template: **[`.env.example`](.env.example)** (comments for every variable).

| Variable | Required | Meaning |
|----------|----------|---------|
| `API_KEY` | Yes | DashScope pay-as-you-go key (`sk-...`) |
| `API_BASE_URL` | Yes | Must match key region (intl / China / US) |
| `MODEL_NAME` | Yes | e.g. `qwen3.7-plus`, `qwen3.7-max`, `qwen3.6-flash` |
| `UNPAYWALL_EMAIL` | Recommended | Contact for Unpaywall PDF lookup |
| `APP_PORT` | Docker only | Host port (default `80`) |

Local Ollama is optional for offline tests — see commented block in `backend/.env.example`.

---

## Features

- **Paper ingestion** — PDF, arXiv, DOI, or natural-language search
- **Agent society** — Executive Moderator + 4 specialists
- **Hand-raising debate** — live WebSocket rounds, rebuttals, dissent ledger
- **Concept maps** — interactive SVG
- **Fact-check** — claim verification with cross-references
- **Benchmark** — society vs single-agent baseline

### Agent roles

| Agent | Role |
|-------|------|
| Executive Moderator | Facilitates, synthesizes, assigns tasks |
| Structure Analyst | Organization and logic flow |
| Contribution Scout | Novelty and significance |
| Methodology Critic | Experiments and statistics |
| Literature Reviewer | Field context |

---

## Architecture

```
Internet → ECS/SAS (:80) → Docker (uvicorn :8000)
                            ├── React UI (static)
                            ├── /api/* REST
                            └── /ws/chat WebSocket
         → DashScope API (Qwen)
         → OpenAlex / PubMed / arXiv (papers)
```

Details: [docs/architecture.md](docs/architecture.md)

---

## Usage

1. Identify a paper (arXiv ID, DOI, URL, or search)
2. Run **Plan** / **Start Agent Debate**, or generate map / fact-check
3. Watch agents raise hands, debate, and reach a verdict over WebSocket

Example inputs: `2301.12345`, `10.1038/nature12345`, `attention is all you need`

```bash
curl -X POST http://localhost:8000/api/benchmark/compare \
  -H "Content-Type: application/json" \
  -d '{"paper_title":"...","sections":{...},"society_report":"..."}'
```

---

## Hackathon submission checklist

- [ ] Public GitHub repo + open-source **LICENSE** (MIT included)
- [ ] 1–3 min demo video of the agent society in action
- [ ] Architecture diagram ([docs/architecture.md](docs/architecture.md))
- [ ] Written summary of features
- [ ] **Proof of Alibaba Cloud deploy** (Workbench / ECS screenshot)
- [ ] Use Qwen Cloud APIs (not a clone of sample repos as the whole project)

---

## License

MIT
