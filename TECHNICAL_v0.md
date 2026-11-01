# WajhUni — Technical Requirements Document
**Version:** 0.1 (v0 — MVP)  
**Last updated:** April 2026  
**Status:** Locked for v0 development

---

## 1. Architecture overview

WajhUni follows a standard three-tier architecture: a Next.js frontend, a FastAPI backend, and a PostgreSQL database — all hosted on Microsoft Azure using the Azure for Students ($200/year) plan. Everything lives in one Azure region to minimize latency and cost.

```
Browser / Mobile
      │
      ▼
Azure Static Web Apps     ← Next.js frontend (SSR + static)
      │
      ▼
Azure Container Apps      ← FastAPI backend (Dockerized)
      │
      ├──▶ Azure Database for PostgreSQL (Flexible Server)
      ├──▶ Azure Cache for Redis
      └──▶ Azure Blob Storage (photos)

GitHub Actions            ← CI/CD pipeline
Azure Monitor             ← Logs, errors, performance
```

---

## 2. Tech stack — decision log

Every choice below was made deliberately. The reason is documented so future contributors understand why, not just what.

### 2.1 Frontend — Next.js 14 (App Router)

**Why Next.js:**
- Server-side rendering (SSR) means university pages are pre-rendered on the server. A parent browsing on a slow mobile connection gets a fast, fully-rendered page — not a blank screen waiting for JavaScript.
- SEO matters for WajhUni. When someone Googles "TBS Tunis university review," we want to rank. SSR pages are indexed by Google; client-only SPAs are not.
- App Router enables per-route caching — the university listing page can be cached at the CDN level, the rating submission form cannot. This distinction is handled declaratively.
- Chosen over Vite/React because the SSR and routing story is simpler for a team of one.

**Key libraries:**
- `next-auth` — authentication session management on the client side
- `react-hook-form` + `zod` — rating form validation (multi-step, one category per screen)
- `@tanstack/react-query` — data fetching and caching
- `tailwindcss` — styling
- `shadcn/ui` — component library (accessible, unstyled base, Tailwind-integrated)

### 2.2 Backend — FastAPI (Python 3.12)

**Why FastAPI over Flask:**
- Async support out of the box — important for database queries under concurrent load
- Pydantic v2 models give you automatic request validation and serialization. Every API endpoint has a typed schema — no silent data corruption.
- Auto-generated OpenAPI docs at `/docs` — invaluable when debugging and when you eventually bring in collaborators
- Previous experience with Python web frameworks (bariatric forum project) means no new language to learn

**Key libraries:**
- `sqlalchemy` (async) + `alembic` — ORM and migrations
- `python-jose` — JWT encoding/decoding
- `passlib[bcrypt]` — password hashing
- `redis-py` — refresh token storage and rate limiting
- `azure-storage-blob` — photo uploads to Blob Storage
- `pydantic-settings` — environment variable management

### 2.3 Database — PostgreSQL 16 (Azure Flexible Server)

**Why PostgreSQL:**
- Relational data with complex aggregations (average scores per category per university) — PostgreSQL handles this trivially with window functions and GROUP BY
- UUID primary keys supported natively
- Row-level constraints (UNIQUE, CHECK) enforce business rules at the database layer — not just the application layer
- Azure Flexible Server free tier covers v0 usage comfortably

### 2.4 Cache — Azure Cache for Redis

**Two jobs in v0:**
1. Refresh token storage — tokens are stored as `refresh:{token_hash}` keys with 7-day TTL. On logout, the key is deleted. This makes token revocation instant without a database query on every request.
2. Rate limiting — limit rating submission attempts to prevent abuse. Implementation: sliding window counter keyed by `ratelimit:{user_id}:{endpoint}`.

### 2.5 File storage — Azure Blob Storage

Photos are never stored in the database or on the application server. They go to Blob Storage with a CDN URL returned to the client.

**Container structure:**
```
wajhuni-photos/
  universities/{university_id}/
    approved/
    pending/
```

Pending photos land in `pending/`. Admin approval moves them to `approved/`. URLs are constructed deterministically — no separate URL column needed.

### 2.6 Hosting — Azure (Student Pack)

| Service | Azure product | Tier |
|---|---|---|
| Frontend | Static Web Apps | Free tier |
| Backend | Container Apps | Consumption plan (scales to zero) |
| Database | PostgreSQL Flexible Server | Burstable B1ms (free 12 months) |
| Cache | Cache for Redis | Basic C0 |
| Storage | Blob Storage | LRS, pay-as-you-go (< $1/month at v0 scale) |
| Monitoring | Application Insights | Free tier (5GB/month) |

**Container Apps on consumption plan** means you pay per request, not per hour. When nobody is using WajhUni at 3am, you pay nothing. At student-project scale this keeps the monthly bill well within $200.

### 2.7 CI/CD — GitHub Actions

**Pipeline (on push to `main`):**
1. Run tests (pytest for backend, jest for frontend)
2. Build Docker image for FastAPI
3. Push image to Azure Container Registry
4. Deploy to Container Apps (zero-downtime revision rollout)
5. Build and deploy Next.js to Static Web Apps

**On pull request:**
1. Run tests only — no deployment

Branch strategy: `main` is production. `dev` is staging. Feature branches merge into `dev`, `dev` merges into `main` after manual review.

---

## 3. Repository structure

```
wajhuni/
├── frontend/                  # Next.js application
│   ├── app/
│   │   ├── (public)/
│   │   │   ├── page.tsx              # University listing
│   │   │   └── universities/
│   │   │       └── [id]/
│   │   │           └── page.tsx      # University detail
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── (protected)/
│   │   │   ├── rate/page.tsx         # Rating submission
│   │   │   └── profile/page.tsx
│   │   └── admin/                    # Admin panel
│   ├── components/
│   ├── lib/
│   └── public/
│
├── backend/                   # FastAPI application
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── universities.py
│   │   │       ├── ratings.py
│   │   │       ├── photos.py
│   │   │       └── admin.py
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   ├── core/              # Config, security, deps
│   │   └── db/                # Session, migrations
│   ├── alembic/               # Migration files
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── .github/
│   └── workflows/
│       ├── ci.yml             # PR checks
│       └── deploy.yml         # Main branch deploy
│
└── docs/
    ├── FEATURES_v0.md         # This project's features doc
    ├── TECHNICAL_v0.md        # This file
    └── SCHEMA_v0.sql          # Database schema and seed
```

---

## 4. API design

**Base URL:** `https://api.wajhuni.tn/api/v1`  
**Auth:** Bearer token (JWT access token) in Authorization header  
**Format:** JSON request and response bodies  
**Versioning:** URL path versioning (`/v1/`) — allows breaking changes in future without affecting existing clients

### Core endpoints

```
AUTH
POST   /api/v1/auth/register          Register with university email
POST   /api/v1/auth/verify-email      Verify email token
POST   /api/v1/auth/login             Get access + refresh tokens
POST   /api/v1/auth/refresh           Rotate refresh token
POST   /api/v1/auth/logout            Invalidate refresh token

UNIVERSITIES
GET    /api/v1/universities           List all active universities
GET    /api/v1/universities/{id}      University detail + aggregated scores
GET    /api/v1/universities/{id}/photos   Approved photos
GET    /api/v1/universities/{id}/reviews  Paginated approved reviews

RATINGS
GET    /api/v1/ratings/categories     List all active rating categories
POST   /api/v1/ratings                Submit a rating (auth required)
PATCH  /api/v1/ratings/{id}           Update a rating (6 month rule enforced)
GET    /api/v1/ratings/mine           Get current user's submission

PHOTOS
POST   /api/v1/photos                 Upload a photo (auth required)

ADMIN  (role = admin only)
GET    /api/v1/admin/queue            Pending submissions + photos
PATCH  /api/v1/admin/ratings/{id}     Approve / flag / reject
PATCH  /api/v1/admin/comments/{id}    Feature / flag a comment
PATCH  /api/v1/admin/photos/{id}      Approve / reject a photo
POST   /api/v1/admin/universities     Create a university
PATCH  /api/v1/admin/universities/{id} Update university info
POST   /api/v1/admin/domains          Add email domain
PATCH  /api/v1/admin/users/{id}       Suspend / reinstate a user
```

---

## 5. Security requirements

### 5.1 Authentication security
- Passwords hashed with bcrypt, cost factor 12
- Access tokens expire in 15 minutes
- Refresh tokens stored in Redis (not the database) — instant revocation on logout
- Refresh tokens are rotated on every use (token rotation) — a stolen token can only be used once
- HTTPS enforced everywhere — HTTP redirects to HTTPS at the Azure gateway level

### 5.2 Authorization
- Every protected endpoint checks JWT validity and expiry
- Role check (`admin`) applied at the route level using FastAPI dependencies
- Own-university check on rating submission: `current_user.university_id == submission.university_id`
- Admin endpoints are on a separate router prefix — easier to audit and lock down

### 5.3 Input validation
- All request bodies validated by Pydantic schemas before reaching business logic
- Rating scores constrained to integer 1–5 at schema level (not just the database)
- Photo uploads: file type validated by reading the file header (magic bytes), not just the extension — a renamed `.exe` does not pass as `.jpg`
- Comment body: stripped of HTML tags before storage — no XSS via stored comments

### 5.4 Rate limiting
- Rating submission: max 3 attempts per user per hour
- Login attempts: max 10 per IP per 15 minutes (then temporary block)
- Photo upload: max 5 uploads per user per day
- Implemented via Redis sliding window counter

### 5.5 OWASP basics
- SQL injection: not possible with SQLAlchemy ORM (parameterized queries)
- CORS: configured to allow only `wajhuni.tn` and `admin.wajhuni.tn` origins
- Security headers: `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options` set via FastAPI middleware

---

## 6. Environment variables

```bash
# Backend (.env)
DATABASE_URL=postgresql+asyncpg://user:pass@host/wajhuni
REDIS_URL=redis://host:6380
JWT_SECRET_KEY=<256-bit random secret>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

AZURE_STORAGE_ACCOUNT=wajhunistorage
AZURE_STORAGE_KEY=<key>
AZURE_STORAGE_CONTAINER=wajhuni-photos

SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=<sendgrid api key>
EMAIL_FROM=noreply@wajhuni.tn

ENVIRONMENT=production  # or development

# Frontend (.env.local)
NEXT_PUBLIC_API_URL=https://api.wajhuni.tn
NEXT_PUBLIC_GOOGLE_MAPS_KEY=<key>
NEXTAUTH_SECRET=<secret>
NEXTAUTH_URL=https://wajhuni.tn
```

---

## 7. Development environment setup

```bash
# Prerequisites
# - Python 3.12+
# - Node.js 20+
# - Docker Desktop
# - PostgreSQL 16 (local) or Azure Flexible Server

# Clone
git clone https://github.com/yourusername/wajhuni.git
cd wajhuni

# Backend
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Fill in local values
alembic upgrade head            # Run migrations
python -m pytest                # Run tests
uvicorn app.main:app --reload   # Start dev server on :8000

# Frontend
cd frontend
npm install
cp .env.example .env.local      # Fill in local values
npm run dev                     # Start dev server on :3000
```

---

## 8. Database constraints — critical business rules

These constraints are enforced at **both** the application layer (FastAPI) and the database layer (PostgreSQL). Both layers must enforce them — the database is the last line of defense.

```sql
-- One submission per student per university
ALTER TABLE rating_submissions
ADD CONSTRAINT uq_user_university UNIQUE (user_id, university_id);

-- Scores must be between 1 and 5
ALTER TABLE rating_scores
ADD CONSTRAINT chk_score_range CHECK (score >= 1 AND score <= 5);

ALTER TABLE rating_sub_scores
ADD CONSTRAINT chk_sub_score_range CHECK (score >= 1 AND score <= 5);

-- Comments cannot exceed 280 characters
ALTER TABLE comments
ADD CONSTRAINT chk_comment_length CHECK (char_length(body) <= 280);
```

---

## 9. Monitoring and observability

**Azure Application Insights** is connected to both the Next.js frontend and FastAPI backend.

**What is tracked:**
- API response times per endpoint
- Error rate and 5xx alerts (email alert if error rate > 1% for 5 minutes)
- Slow queries (PostgreSQL slow query log, threshold: 500ms)
- Failed login attempts (custom event tracked for security monitoring)
- Rating submission funnel (started → completed → approved) — measures drop-off

**Alerts configured:**
- Error rate spike → email to admin
- Database CPU > 80% for 10 minutes → email to admin
- Container App scaling event → logged (informational)

---

## 10. Deployment checklist (before going live)

- [ ] All environment variables set in Azure Key Vault and referenced in Container Apps config
- [ ] Database migrations run against production PostgreSQL
- [ ] Rating categories seeded (9 rows in `rating_categories`)
- [ ] At least 3 universities seeded with photos, coordinates, transport info
- [ ] At least 2 email domains registered in `email_domains`
- [ ] Admin account created
- [ ] HTTPS certificate active on custom domain
- [ ] GitHub Actions pipeline green on a test deployment
- [ ] Application Insights connected and receiving events
- [ ] Rate limiting tested against login and submission endpoints
- [ ] Photo upload tested end-to-end (upload → pending → admin approve → visible)
- [ ] Email verification flow tested end-to-end
- [ ] Verified that a student cannot submit a rating for a different university
- [ ] Verified that an unverified account cannot submit ratings
