# BrainWave3D Backend

Async FastAPI backend scaffold for the BrainWave3D mobile application. The stack uses FastAPI, MongoDB Atlas (via Motor), JWT auth with refresh tokens, and a modular service layout ready for future ML integrations.

## Prerequisites

- Python 3.10+
- MongoDB Atlas cluster (or any MongoDB instance)
- Recommended: virtual environment tool such as `venv` or `conda`

## Getting Started

1. **Clone & enter the project**
   ```cmd
   cd brainwave3d
   ```
2. **Create a virtual environment (example using `venv`)**
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. **Install dependencies**
   ```cmd
   pip install -r requirements.txt
   ```
4. **Configure environment variables**
   - Copy `.env.example` to `.env`.
   - Update `MONGO_URI` with your Atlas connection string (keep the query params).
   - Optionally adjust token lifetimes or the database name.

5. **Run the API**
   ```cmd
   uvicorn app.main:app --reload
   ```

The service listens on `http://127.0.0.1:8000` by default. Startup establishes the Mongo connection and ensures required indexes (unique email + TTL for token blacklist).

## Database & Indexes

- Users are stored in the `users` collection with a unique index on `email`.
- Refresh token JTIs are stored in `token_blacklist` with a TTL index on `expires_at` for automatic cleanup.
- Atlas credentials live only in `.env`; never commit sensitive values.

## Available Endpoints

| Method | Path           | Description                         |
| ------ | -------------- | ----------------------------------- |
| POST   | `/auth/signup` | Register user, issue access/refresh |
| POST   | `/auth/login`  | Authenticate, issue new tokens      |
| POST   | `/auth/logout` | Blacklist refresh token             |
| GET    | `/profile/me`  | Fetch authenticated profile         |
| PUT    | `/profile/me`  | Update profile fields               |
| DELETE | `/profile/me`  | Delete current account              |

### Simple Chatbot (Prototype)

Use these simplified routes (no conversation IDs needed from frontend):

| Method | Path             | Description                                      |
| ------ | ---------------- | ------------------------------------------------ |
| POST   | `/chat/message`  | Send one message and get assistant reply         |
| GET    | `/chat/history`  | Read current user's default chat history         |
| WS     | `/chat/ws`       | Real-time streaming chat (`?token=<access_token>`) |

WebSocket payload can be minimal:

```json
{
   "content": "Give me a quick overview of my profile",
   "prediction_summary": "optional latest report summary"
}
```

### Groq Setup (.env)

Set provider to Groq and place your API key in `.env`:

```env
LLM_PROVIDER=groq
LLM_MODEL_NAME=llama-3.1-8b-instant
GROQ_API_KEY=your_groq_api_key_here
```

You can start from `.env.example` in the repo root.

All profile routes require a valid `Authorization: Bearer <access_token>` header.

## Migrations

MongoDB does not require Alembic migrations. Schema changes are applied by updating documents and indexes. Index management happens during application startup inside `app/db/session.py`.

## Generating Tokens

1. **Signup**
   ```bash
   curl -X POST http://127.0.0.1:8000/auth/signup \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com", "password": "Passw0rd!"}'
   ```
   Response includes both `access_token` (15 min) and `refresh_token` (7 days).

2. **Login**
   ```bash
   curl -X POST http://127.0.0.1:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com", "password": "Passw0rd!"}'
   ```

Use the `access_token` in the `Authorization` header for protected routes. Refresh tokens can be invalidated via `/auth/logout` by sending the token in the body.

## Mobile Integration Notes

- Store both access and refresh tokens securely on the device.
- Refresh tokens should be sent to a dedicated refresh endpoint (add later) or to `/auth/logout` when signing out.
- Include the bearer access token on each API request. Handle `401` responses by prompting a silent re-auth via refresh token.
- API responses return ISO timestamps (`created_at`, `updated_at`) and normalized IDs (Mongo ObjectId as string).

## Future Work

- Implement refresh token rotation endpoint.
- Add rate limiting and audit logging.
- Flesh out the ML stubs in `app/ml/` once models are ready.
- Extend services for push notifications or analytics integrations as needed.

## Observability Stack (Prometheus + Grafana)

This repository now includes a complete monitoring setup:

- FastAPI metrics endpoint at `GET /metrics`
- Prometheus scrape configuration
- Grafana provisioning (datasource + dashboards)

### Start Everything With Docker Compose

```bash
docker compose up -d --build
```

### Service URLs

- API: `http://localhost:8000`
- API metrics: `http://localhost:8000/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (default login: `admin` / `admin`)

### Pre-Provisioned Dashboards

Grafana automatically loads dashboards from `monitoring/grafana/dashboards/`:

- `Backend API Overview`
- `Backend Status Breakdown`
- `Backend Runtime Health`

### Chat Metrics Exposed

The backend now exports chat-specific metrics at `/metrics`:

- `chat_messages_total{channel,role,status,provider}`
- `chat_response_duration_seconds{channel,provider}`
- `chat_active_connections{provider}`
- `llm_provider_errors_total{provider}`

### Key Monitoring Files

- Compose stack: `docker-compose.yml`
- Prometheus config: `monitoring/prometheus/prometheus.yml`
- Grafana datasource: `monitoring/grafana/provisioning/datasources/prometheus.yml`
- Grafana dashboard provider: `monitoring/grafana/provisioning/dashboards/dashboards.yml`

### Stop Stack

```bash
docker compose down
```
