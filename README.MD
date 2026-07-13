# Distributed Chat Application

A horizontally scalable, real-time messaging platform built with **Next.js**, **FastAPI**, **PostgreSQL**, and **Redis**.

**Author:** Kota Manohar

[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://distributed-chat-application.vercel.app)
[![GitHub](https://img.shields.io/badge/github-repo-blue)](https://github.com/manoharkota1/Distributed-Chat-Application)
[![LinkedIn](https://img.shields.io/badge/linkedin-connect-0A66C2)](https://linkedin.com/in/manoharkota-in)

---

## 🔗 Links

- **GitHub Repository:** [github.com/manoharkota1/Distributed-Chat-Application](https://github.com/manoharkota1/Distributed-Chat-Application)
- **Live Demo:** [distributed-chat-application.vercel.app](https://distributed-chat-application.vercel.app)
- **LinkedIn:** [linkedin.com/in/manoharkota-in](https://linkedin.com/in/manoharkota-in)

---

## 📖 Project Overview

Distributed Chat Application is a production-grade, real-time messaging platform designed to demonstrate the same architectural patterns used by large-scale chat systems (Slack, WhatsApp Web, Discord) at a portfolio-appropriate scale. It supports one-to-one and group conversations over authenticated WebSocket connections, with read receipts, typing indicators, live presence, and infinite-scroll message history.

The core engineering challenge this project solves is **horizontal scaling of stateful WebSocket connections**. A single backend instance can only hold connections it directly owns in memory — the moment traffic is spread across multiple instances behind a load balancer, an instance needs a way to deliver a message to a client connected to a different instance. This project solves that using **Redis Publish/Subscribe** as a cross-instance message bus, decoupling "who received the request" from "who needs to deliver the response."

### Problem Statement

Most tutorial-level chat applications work only on a single server process and break the moment traffic is scaled horizontally, because in-memory WebSocket connection maps are not shared across instances. This project is built to correctly handle that failure mode from the ground up, while also implementing the security and UX details (revocable auth, cursor pagination, optimistic UI) that separate a demo from a deployable product.

### Why This Project Matters

- Demonstrates real distributed-systems reasoning, not just CRUD and UI work.
- Covers the full stack end to end: frontend, backend, database, cache/broker, auth, DevOps.
- Implements security practices used in production systems — hashed refresh tokens, token rotation, revocation.
- Uses efficient, production-safe pagination (cursor-based) instead of a naive `OFFSET` query that degrades at scale.

---

## ✨ Key Features

### Messaging
- One-to-one and group conversations
- Real-time message delivery over authenticated WebSockets
- Optimistic UI — messages appear instantly and reconcile on server acknowledgment
- Cursor-based pagination for efficient infinite scroll through large chat histories

### Presence & Engagement
- Live typing indicators (auto-expiring, no explicit "stop typing" event required)
- Online/offline presence tracking via Redis TTL keys
- Per-message and per-conversation read receipts

### Authentication & Security
- JWT-based authentication with short-lived access tokens
- Revocable, rotating refresh tokens stored as hashes (never raw) in PostgreSQL
- Session management — users can view and revoke individual logged-in devices
- Rate limiting on message sends via Redis sliding-window counters

### Platform & Delivery
- Dockerized services (frontend, backend, PostgreSQL, Redis, Nginx)
- CI/CD pipeline via GitHub Actions — lint, test, build, deploy on push
- Horizontally scalable backend — verified by running multiple FastAPI instances behind a load balancer

---

## 🛠 Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Next.js (React) | UI, routing, WebSocket client, optimistic rendering |
| Backend API | FastAPI (Python) | REST endpoints and WebSocket gateway |
| Database | PostgreSQL | Durable storage — users, conversations, messages |
| Cache / Broker | Redis | Pub/Sub fanout, presence, typing indicators, rate limiting |
| Auth | JWT (access) + opaque rotating tokens (refresh) | Stateless auth with server-side revocation |
| Containerization | Docker / Docker Compose | Reproducible local and production environments |
| CI/CD | GitHub Actions | Automated lint, test, build, and deploy pipeline |
| Hosting (Demo) | Vercel | Frontend deployment |

---

## 🏗 High-Level Design (HLD)

The system is composed of five cooperating services: the Next.js client, a load balancer, a horizontally scaled pool of FastAPI instances, Redis, and PostgreSQL. The load balancer does **not** need sticky sessions for correctness — any FastAPI instance can serve any client, because Redis Pub/Sub ensures a message is delivered regardless of which instance a recipient happens to be connected to.

```
Next.js Client (Browser)
        │  HTTPS / WSS
        ▼
Load Balancer / Nginx
        │
   ┌────┴─────┐
   ▼          ▼
FastAPI     FastAPI
Instance 1  Instance 2
   │  \      /  │
   │   \    /   │
   ▼    ▼  ▼    ▼
 Redis          PostgreSQL
 (Pub/Sub,      (Users, Messages,
  Presence,      Conversations)
  Typing)
```

### Component Responsibilities

| Component | Responsibility |
|---|---|
| Next.js Client | Renders UI, manages a single WebSocket connection, handles optimistic message state and cursor-based infinite scroll |
| Load Balancer | Distributes incoming HTTP/WSS connections across FastAPI instances; no session affinity required |
| FastAPI Instances | Authenticate requests, serve REST endpoints, manage local WebSocket connections, publish/subscribe to Redis |
| Redis | Cross-instance Pub/Sub bus, presence TTL keys, typing-indicator TTL keys, rate-limit counters |
| PostgreSQL | System of record — users, conversations, membership, messages, refresh tokens |

### Message Delivery Flow Across Instances

This is the flow that makes horizontal scaling actually work end to end: a message sent by a client on Instance 1 is correctly delivered to a recipient connected to Instance 2, with no direct coupling between the two instances.

1. Client A sends a message over its WebSocket connection to Instance 1.
2. Instance 1 persists the message to PostgreSQL and receives back the generated `id` and `timestamp`.
3. Instance 1 publishes the message to a Redis channel scoped to that conversation.
4. Every instance — including Instance 1 itself — is subscribed to that channel and pushes the message to any locally connected clients that are members of the conversation.
5. Instance 1 also sends a direct acknowledgment back to Client A so the UI can reconcile its optimistic message bubble.

### Scalability Strategy

- Backend is stateless with respect to routing — no instance needs to know where a given user's connection lives.
- Redis Pub/Sub decouples message origin from message delivery, allowing any number of FastAPI instances to be added or removed without reconfiguring routing.
- PostgreSQL remains the single source of truth; Redis holds only ephemeral, reconstructable state (presence, typing, rate limits).
- Cursor-based pagination keeps message history retrieval performant regardless of conversation size.

---

## 🧩 Low-Level Design (LLD)

### Database Schema

PostgreSQL is the system of record. The schema is normalized around five core tables, with the composite index on `messages(conversation_id, created_at, id)` being the single most important index in the system — it is what makes cursor-based pagination performant.

| Table | Key Columns | Notes |
|---|---|---|
| `users` | `id` (PK), `email` (unique), `password_hash`, `display_name` | Core identity table |
| `refresh_tokens` | `id` (PK), `user_id` (FK), `token_hash`, `revoked_at`, `replaced_by` | Stores a hash only; `replaced_by` forms a rotation chain for theft detection |
| `conversations` | `id` (PK), `type` (direct/group), `name` | A conversation is the container for both DMs and groups |
| `conversation_members` | `conversation_id` (FK), `user_id` (FK), `last_read_message_id` | Composite PK; tracks membership and read position |
| `messages` | `id` (PK), `conversation_id` (FK), `sender_id` (FK), `content`, `created_at` | Indexed on `(conversation_id, created_at DESC, id DESC)` for pagination |
| `message_reads` | `message_id` (FK), `user_id` (FK), `read_at` | Per-message read receipts for group conversations |

### REST API Contract

All responses follow a consistent envelope: `{"data": ..., "error": null}` on success, and `{"data": null, "error": {"code", "message"}}` on failure.

| Method & Path | Auth | Purpose |
|---|---|---|
| `POST /auth/register` | – | Create account, issue access token + refresh cookie |
| `POST /auth/login` | – | Authenticate, issue access token + refresh cookie |
| `POST /auth/refresh` | Refresh cookie | Rotate refresh token, issue new access token |
| `POST /auth/logout` | Access token | Revoke the current refresh token |
| `GET /users/me/sessions` | Access token | List active sessions/devices |
| `DELETE /users/me/sessions/{id}` | Access token | Revoke a specific session (remote logout) |
| `GET /conversations` | Access token | Paginated list of the user's conversations |
| `POST /conversations` | Access token | Create a direct or group conversation |
| `GET /conversations/{id}/messages` | Access token | Cursor-paginated message history |
| `POST /conversations/{id}/messages` | Access token | Send a message (REST fallback path) |
| `PATCH /conversations/{id}/read` | Access token | Update the caller's last-read message |

### WebSocket Protocol

A single persistent connection is opened per client at `wss://.../ws?token=<jwt>`. All messages share a common envelope: `{"type", "payload", "request_id"}`.

| Event Type | Direction | Payload Summary |
|---|---|---|
| `message.send` | Client → Server | `conversation_id`, `content`, `client_temp_id` |
| `message.new` | Server → Client | Full message object, broadcast to all members |
| `message.ack` | Server → Client | Confirms receipt; reconciles optimistic UI bubble |
| `typing.start` / `typing.stop` | Client → Server | `conversation_id` |
| `typing.update` | Server → Client | `conversation_id`, `user_id`, `is_typing` |
| `presence.update` | Server → Client | `user_id`, `status`, `last_seen` |
| `read.update` / `read.receipt` | Bidirectional | `conversation_id`, `message_id`, `user_id` |

### Redis Key Design

| Key Pattern | Type | TTL | Purpose |
|---|---|---|---|
| `presence:{user_id}` | String | 30s (refreshed) | Presence — key absence means offline |
| `typing:{conversation_id}:{user_id}` | String | 5s | Typing indicator, auto-expires without an explicit stop event |
| `chan:convo:{conversation_id}` | Pub/Sub channel | – | Cross-instance message fanout, scoped per conversation |
| `ratelimit:msg:{user_id}` | Counter / sorted set | 10s window | Throttles message send rate per user |

### Authentication Design

Access tokens are short-lived (15 minutes), stateless JWTs verified purely by signature and expiry — no database lookup needed on the hot path. Refresh tokens are opaque 256-bit random strings, stored server-side only as a SHA-256 hash, and delivered to the client as an `httpOnly`, `Secure`, `SameSite=Strict` cookie so they are never exposed to client-side JavaScript.

**Rotation & Theft Detection**

1. Every refresh call issues a new access + refresh token pair and immediately marks the old refresh token row as revoked, linking to its replacement via `replaced_by`.
2. If a client ever presents a refresh token that has already been marked revoked, the entire rotation chain is treated as compromised and revoked, forcing re-authentication.
3. This design detects stolen-and-reused refresh tokens without needing to track device fingerprints.

### Cursor-Based Pagination

Message history is paginated using an opaque cursor encoding `(created_at, id)` of the last row seen, rather than a numeric `OFFSET`. This keeps retrieval performant at any scroll depth, since the database can seek directly using the composite index instead of scanning and discarding rows.

```sql
WHERE (created_at, id) < (:cursor_created_at, :cursor_id)
ORDER BY created_at DESC, id DESC
LIMIT :limit + 1
```

### Module Structure

**Backend (FastAPI)**
```
core/       # configuration, JWT security helpers, shared dependencies
api/        # REST route handlers (auth, conversations, users)
ws/         # WebSocket router, connection manager, per-event handlers
services/   # business logic for auth, messaging, presence
pubsub/     # Redis bridge that fans out published events to locally connected clients
```

**Frontend (Next.js)**
```
app/        # route-based pages: login, register, inbox, chat, group settings, profile, sessions
lib/ws/     # WebSocket client singleton with reconnect and backoff logic
lib/api/    # typed HTTP client with automatic 401 → refresh → retry handling
hooks/      # useInfiniteMessages (cursor pagination), useTypingIndicator
```

---

## 🔒 Security Considerations

- Refresh tokens are never stored in plaintext — only a SHA-256 hash is persisted.
- Refresh tokens live in `httpOnly` cookies, eliminating XSS-based token theft.
- Refresh token rotation detects reuse of a stolen token and revokes the entire session chain.
- WebSocket connections are authenticated at handshake time before being accepted.
- All conversation-scoped endpoints verify membership before returning data, preventing unauthorized access to other users' messages.
- Rate limiting on message sends mitigates spam and abuse.

---

## 🚀 Deployment & CI/CD

The application is fully containerized. Docker Compose defines the frontend, a scalable pool of FastAPI instances, PostgreSQL, Redis, and an Nginx load balancer for local and staging environments. The live demo frontend is deployed on Vercel.

## 💻 Run Locally

Docker Desktop is the quickest way to run the complete stack. It starts PostgreSQL,
Redis, two backend instances, Nginx, and the frontend; the database migration runs
automatically before either backend starts.

For the non-Docker workflow, use Python 3.12 (the supported backend runtime) and
Node.js 22 with pnpm.

1. Copy `.env.example` to `.env` and replace the example database password and JWT
   secret before using this outside local development.
2. Start Docker Desktop, then run:

   ```bash
   docker compose up --build
   ```

3. Open `http://localhost:3000`. The API health check is available at
   `http://localhost/health`.

For a non-Docker backend, start PostgreSQL and Redis, create `.env` from the example,
then run the following from `backend/`:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal, run the frontend from `frontend/`:

```bash
pnpm install --frozen-lockfile
pnpm dev
```

Use `COOKIE_SECURE=false` only when testing on local HTTP. Set it to `true` for an
HTTPS deployment.

**CI/CD Pipeline (GitHub Actions)**

1. Lint and static analysis on every push
2. Automated test suite execution
3. Docker image build
4. Deployment to the target environment on merge to `main`

### Git Branching Strategy

This project follows a professional branching model to ensure stability:
- **`main`**: Production-ready branch. Automated Vercel deployments are triggered on push.
- **`develop`**: Integration and staging branch where features are consolidated and tested.
- **`feat/*` or `fix/*`**: Short-lived feature or bugfix branches for isolated development.

---

## ✅ Testing Strategy

- Unit tests for auth logic — token issuance, rotation, and revocation edge cases
- Integration tests for REST endpoints against a test database
- WebSocket integration tests validating message delivery, including simulated multi-instance delivery via Redis
- Manual horizontal-scaling verification — two backend instances running simultaneously, confirming a message sent while connected to one instance is received by a client connected to the other

---

## 💡 Challenges & Key Learnings

- Designing cross-instance WebSocket delivery required decoupling connection ownership from message delivery — solved with Redis Pub/Sub rather than trying to share connection state directly.
- Naive `OFFSET`-based pagination degrades under large chat histories; switching to a cursor-based, index-backed approach kept retrieval fast regardless of history depth.
- Balancing refresh token security with usability led to the rotation-with-reuse-detection design, which revokes an entire session chain only when theft is actually detected.

---

## 🔮 Future Enhancements

- End-to-end encryption for message content
- Media/file attachments with object storage (S3-compatible)
- Push notifications for offline users
- Message search across conversation history
- Admin/moderation tooling for group conversations

---

## 📝 Conclusion

Distributed Chat Application demonstrates a complete, production-oriented approach to building real-time systems: correct handling of horizontal scaling for stateful WebSocket connections, secure and revocable authentication, efficient pagination at scale, and a fully containerized, CI/CD-driven delivery pipeline. The project reflects the kind of systems-level thinking required to take a feature from "works on my machine" to "works reliably under real, distributed load."

---
