# UCP Shopping Agent

An AI shopping assistant built with **Google ADK** and **Gemini** that uses the **Universal Commerce Protocol (UCP)** to browse products, link user identity, and complete purchases — all through conversation.

**Live Agent**: [Cloud Run](https://ucp-shopping-agent-189730860966.us-central1.run.app) | **UCP API**: [ucp.c0a1.in](https://ucp.c0a1.in) | **Store**: [ucp-demo-1f0cf.web.app](https://ucp-demo-1f0cf.web.app)

![Google ADK](https://img.shields.io/badge/Google_ADK-1.28-blue?logo=google) ![Gemini](https://img.shields.io/badge/Gemini_2.0-Flash-orange) ![UCP](https://img.shields.io/badge/UCP-1.0-green) ![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)

---

## How It Works

The agent only needs **one URL** — the UCP discovery endpoint. From there, it knows how to browse, authenticate, checkout, and track orders.

```
User: "What do you sell?"
Agent: [calls GET /products via UCP] → Shows catalog with prices in ₹

User: "I want to buy 2 headphones"
Agent: [calls link_account()] → "Please sign in here: [link]"
       User clicks → signs in with Google → closes tab
Agent: [polls /agent/session/{id}] → "Account linked!"
       [calls POST /checkout/sessions] → "Checkout started. Shipping address?"

User: "123 MG Road, Bangalore, KA 560001, arjun@test.com"
Agent: [calls POST /checkout/sessions/{id}/update]
       "Order: 2x Headphones = ₹9,998. Confirm?"

User: "Yes"
Agent: [calls POST /checkout/sessions/{id}/complete]
       "Order placed! ID: ORD-A1B2C3D4"
```

---

## Architecture

```
[User] ↔ [ADK Agent (Gemini)] ↔ [UCP API (ucp.c0a1.in)] ↔ [Store (Firebase)]
                |
                |── link_account()     → OAuth URL for user sign-in
                |── check_auth()       → Polls for token (seamless)
                |── browse_products()  → GET /products
                |── start_checkout()   → POST /checkout/sessions
                |── add_buyer_info()   → POST /checkout/sessions/{id}/update
                |── complete_purchase() → POST /checkout/sessions/{id}/complete
                |── check_order_status() → GET /orders/{id}
```

The agent has **zero store-specific code**. It talks to the UCP merchant API, which proxies to the store. Any UCP-compliant merchant can be plugged in.

---

## Tools (10)

### Identity Linking (3)

| Tool | Purpose |
|------|---------|
| `link_account()` | Generates OAuth sign-in URL. User clicks, signs in with Google. |
| `check_auth()` | Polls UCP for auth token. Picks it up automatically after sign-in. |
| `get_auth_status()` | Quick check if user is already authenticated. |

### Commerce (7)

| Tool | UCP Endpoint | Auth |
|------|-------------|------|
| `browse_products(category?)` | `GET /products` | No |
| `get_product_details(id)` | `GET /products/{id}` | No |
| `start_checkout(items)` | `POST /checkout/sessions` | Yes |
| `add_buyer_info(email, city, state, ...)` | `POST /sessions/{id}/update` | Yes |
| `complete_purchase()` | `POST /sessions/{id}/complete` | Yes |
| `check_order_status(order_id)` | `GET /orders/{id}` | Yes |
| `list_my_orders()` | `GET /orders` | Yes |

### Session State

| Key | Set By | Used By |
|-----|--------|---------|
| `agent_session_id` | `link_account` | `check_auth` |
| `auth_token` | `check_auth` | All authenticated tools |
| `checkout_session_id` | `start_checkout` | `add_buyer_info`, `complete_purchase` |
| `last_order_id` | `complete_purchase` | `check_order_status` |

---

## Identity Linking Flow

No copy-pasting tokens. No browser automation. Fully seamless.

```
1. Agent generates a session_id (UUID)
2. Agent builds OAuth URL:
   https://ucp.c0a1.in/oauth/authorize?client_id=adk_agent
     &redirect_uri=.../agent/callback?session_id={id}
3. User clicks → signs in with Google on the storefront
4. Storefront redirects to /agent/callback → verifies token → stores JWT in Firestore
5. User sees "Success! Close this tab."
6. Agent polls GET /agent/session/{id} → picks up the JWT
7. JWT stored in session state → used for all subsequent calls
```

---

## Project Structure

```
ucp_agent/
├── __init__.py          # ADK discovery: from . import agent
├── agent.py             # root_agent — Gemini 2.0 Flash, 10 tools
├── tools.py             # 3 auth + 7 commerce tool functions
├── ucp_client.py        # httpx wrapper for UCP REST API
├── .env                 # GOOGLE_API_KEY, UCP_BASE_URL
├── requirements.txt     # google-adk, httpx
├── pyproject.toml       # uv project config
└── uv.lock              # Locked dependencies
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Gemini API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

### 1. Clone and Install

```bash
git clone https://github.com/arjunagi-a-rehman/ucp-agent.git
cd ucp-agent
uv sync
```

### 2. Configure

Create `.env`:

```env
GOOGLE_API_KEY=your_gemini_api_key
UCP_BASE_URL=https://ucp.c0a1.in
```

### 3. Run Locally (Web UI)

```bash
# From the PARENT directory (the one containing ucp_agent/)
cd ..
uv run --project ucp-agent adk web .
```

Open [http://localhost:8000](http://localhost:8000), select `ucp_agent`, and start chatting.

### 4. Run in Terminal Mode

```bash
cd ..
uv run --project ucp-agent adk run ucp_agent
```

---

## Deploy to Cloud Run

```bash
# From the parent directory
uv run --project ucp-agent adk deploy cloud_run \
    --project=your-gcp-project \
    --region=us-central1 \
    --service_name=ucp-shopping-agent \
    --with_ui \
    ucp_agent
```

Set environment variables:

```bash
gcloud run services update ucp-shopping-agent \
    --region=us-central1 \
    --set-env-vars="GOOGLE_API_KEY=your_key,UCP_BASE_URL=https://ucp.c0a1.in"
```

Rate limit for safety (Vertex AI costs):

```bash
gcloud run services update ucp-shopping-agent \
    --region=us-central1 \
    --max-instances=2 \
    --concurrency=10
```

> **Note**: On Cloud Run, the agent uses **Vertex AI** (not the Gemini API key). Enable the Vertex AI API in your GCP project. Set a billing budget alert as a safety net.

---

## Use UCP with Any Agent

You don't need this specific agent. Give the discovery URL to **any** AI that can make HTTP calls:

```
https://ucp.c0a1.in/.well-known/ucp
```

Works with:
- **Claude Code** — reads the discovery, calls APIs, places orders
- **Cursor / Windsurf** — same approach
- **ChatGPT with function calling** — auto-discovers endpoints
- **Any custom agent** with HTTP access

The discovery endpoint is self-describing: capabilities, flows, endpoints, field mappings, auth instructions, and examples. **One URL is all an agent needs.**

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes (local) | Gemini API key from Google AI Studio |
| `UCP_BASE_URL` | Yes | UCP merchant URL (default: `https://ucp.c0a1.in`) |

> On Cloud Run, `GOOGLE_API_KEY` is optional — Vertex AI authenticates via the service account.

---

## Related Repos

| Repo | Description |
|------|-------------|
| [ucp-demo-store](https://github.com/arjunagi-a-rehman/ucp-demo-store) | Next.js e-commerce storefront (Firebase + Razorpay) |
| [ucp-merchant](https://github.com/arjunagi-a-rehman/ucp-merchant) | UCP merchant API (FastAPI) — the protocol layer |
| [UCP Spec](https://github.com/Universal-Commerce-Protocol/ucp) | Official UCP specification |

## License

MIT
