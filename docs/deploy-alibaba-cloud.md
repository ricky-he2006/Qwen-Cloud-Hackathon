# Deploy Research Society on Alibaba Cloud

One-command Docker deployment for ECS with **Qwen (DashScope)** as the LLM backend.

## Architecture

```
Internet → ECS Security Group (:80) → Docker (uvicorn :8000)
                                      ├── React UI (static)
                                      ├── /api/* REST
                                      └── /ws/chat WebSocket
                    └── DashScope API (Qwen)
                    └── OpenAlex / PubMed / arXiv (paper discovery)
```

## Prerequisites

1. [Alibaba Cloud](https://www.alibabacloud.com/) account
2. **DashScope API key** from [Model Studio](https://www.alibabacloud.com/help/en/model-studio/get-api-key)
3. ECS instance (recommended: **2 vCPU, 4 GB RAM**, Ubuntu 22.04+)
4. Security group: allow **TCP 22** (SSH), **TCP 80** (HTTP), optionally **443** (HTTPS)

## Step 1 — Create ECS instance

1. Console → **Elastic Compute Service** → Create Instance
2. Region: pick same region as your DashScope endpoint when possible
   - China workloads → Beijing endpoint
   - International → Singapore endpoint
3. Image: **Ubuntu 22.04 LTS**
4. Network: assign **public IP** (or use SLB later)
5. Security group: open ports **22**, **80**

## Step 2 — Configure Qwen API

On the ECS instance, choose the `API_BASE_URL` for your region:

| Region | `API_BASE_URL` |
|--------|----------------|
| China (Beijing) | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| International (Singapore) | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| US (Virginia) | `https://dashscope-us.aliyuncs.com/compatible-mode/v1` |

See [OpenAI-compatible Qwen docs](https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope).

## Step 3 — Install Docker on ECS

```bash
ssh root@YOUR_ECS_PUBLIC_IP
git clone https://github.com/YOUR_USER/Research_Society.git
cd Research_Society
sudo bash deploy/bootstrap-ecs.sh
```

## Step 4 — Configure environment

```bash
cp .env.example .env
nano .env
```

Required (pay-as-you-go `sk-...` key — not Token Plan `sk-sp-...`):

```env
API_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
API_KEY=sk-your-real-key
MODEL_NAME=qwen3.7-plus
APP_PORT=80
```

## Step 5 — Deploy

```bash
bash deploy/deploy.sh
```

Open in browser:

```
http://YOUR_ECS_PUBLIC_IP
```

Health check:

```bash
curl http://YOUR_ECS_PUBLIC_IP/api/health
```

## Step 6 — Security group reminder

If the site does not load, open **port 80** in:

**ECS → Security Groups → Inbound rules → Allow TCP 80 from 0.0.0.0/0** (or your IP for testing)

## Optional — HTTPS with nginx profile

For longer proxy timeouts (debates can run 10+ minutes):

```bash
docker compose --profile nginx up -d
```

Place TLS certs in `deploy/certs/` and extend `deploy/nginx.conf` for SSL.

Or use **Alibaba Cloud SLB + HTTPS certificate** in front of the ECS instance.

## Operations

```bash
# Logs
docker compose logs -f

# Restart after .env change
docker compose up -d --build

# Stop
docker compose down
```

## Hackathon checklist

- [ ] Public URL works (`http://ECS_IP`)
- [ ] `/api/health` shows Qwen model name
- [ ] Natural language paper search works
- [ ] Debate completes with WebSocket updates
- [ ] Devpost: repo link + demo video + live URL

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Connection refused` | Open port 80 in security group |
| LLM errors | Check `API_KEY` and regional `API_BASE_URL` match |
| Debate times out | Use nginx profile or increase proxy `proxy_read_timeout` |
| Paper fetch fails | Paste DOI if publisher blocks bots; discovery uses OpenAlex/PubMed |

## Cost notes

- ECS: ~$10–30/mo for small instance (varies by region)
- DashScope: pay per token — debates use many LLM calls; test with `qwen3.7-plus` first

### Optional nginx (long debate timeouts)

```bash
APP_PORT=8000 docker compose --profile nginx up -d
```

Set `APP_PORT=8000` so the app does not also bind host port 80 (nginx owns 80/443).
