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
