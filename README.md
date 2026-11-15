# CampusBite

CampusBite is a full-stack restaurant ordering and delivery platform for a campus. Customers browse restaurants and menus, order with a dummy payment, track orders, review and request refunds, and read AI-generated insights about their past orders. Restaurant owners manage menus, orders, delivery assignment, refunds, reminders and statistics. Delivery partners manage their assigned deliveries. All prices are in INR.

## Submission and live links

| Item | URL |
| --- | --- |
| Repository (submission link) | https://github.com/webknob-in/campus-bite-project |
| Frontend (Vercel) | https://campusbite-two-gamma.vercel.app |
| Backend API docs (Vercel) | https://campusbite-api-three.vercel.app/docs |

The AI endpoints (`/ai/insights`) need `OPENAI_API_KEY` set on the backend; without it they return HTTP 503. The demo accounts listed under [Demo credentials](#demo-credentials) work on the live site.

Related documents: [Brief compliance matrix](docs/COMPLIANCE.md) and [Responsive check results](docs/RESPONSIVE_CHECK.md).

## Technologies used

| Layer | Technology |
| --- | --- |
| Frontend | React.js, JavaScript (ES6+), React Hooks, React Router DOM, Axios (Fetch API alternative allowed by the brief), Vite |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy ORM, JWT authentication (PyJWT, bcrypt password hashing), Alembic migrations, Docker and Docker Compose |
| Database | PostgreSQL 16 (SQL relational database), accessed only through SQLAlchemy with the psycopg v3 driver |
| AI integration | OpenAI API (default model `gpt-4o-mini`) |
| Version control | Git and GitHub |
| Testing | pytest and Hypothesis (backend), Vitest, Testing Library and fast-check (frontend) |
| Hosting | Vercel (frontend and backend as two projects), Supabase Postgres |

## Features implemented

**Customer**
- Register and log in; role-based access control.
- Browse restaurants (search by name or cuisine) and view menus and dish details.
- Search and filter dishes by name and price.
- Cart: add, change quantity, remove.
- Place orders with a dummy card payment.
- Order history and order status tracking.
- Cancel an order while it is `PLACED`.
- Rate and review after delivery.
- Request a return/refund after delivery.
- AI summary of the last five orders and free-form AI questions about past orders.

**Restaurant owner**
- Log in (owners register with a role and receive their restaurant).
- Add, edit, delete dishes; mark dishes available or unavailable.
- View incoming orders, filter by status and date range.
- Accept orders and move them to preparing and ready.
- Assign a delivery partner to a ready order.
- Approve or reject return/refund requests.
- Restaurant statistics (orders, revenue, ratings).
- Reminders for orders not updated within `REMINDER_THRESHOLD_MINUTES`.

**Delivery partner**
- Log in and see only orders assigned to them, with customer delivery details.
- Mark orders Out for Delivery and Delivered.
- Delivery history.

### Order state machine

```
PLACED -> ACCEPTED -> PREPARING -> READY -> ASSIGNED -> OUT_FOR_DELIVERY -> DELIVERED -> REFUNDED
   \-> CANCELLED (customer, only from PLACED)
```

| Transition | Performed by |
| --- | --- |
| PLACED -> CANCELLED | the customer who placed the order |
| PLACED -> ACCEPTED, ACCEPTED -> PREPARING, PREPARING -> READY, READY -> ASSIGNED | owner of the restaurant |
| ASSIGNED -> OUT_FOR_DELIVERY, OUT_FOR_DELIVERY -> DELIVERED | the assigned delivery partner |
| DELIVERED -> REFUNDED | owner, by approving a return request |

Any other transition returns HTTP 409. `CANCELLED` and `REFUNDED` are terminal.

### Payment (mock only)

Payment is simulated. No real card processing happens and no payment provider is called. The full card number, expiry and CVV are validated and discarded; only the last four digits (`card_last4`) are stored in the payment ledger. A refund writes a `REFUND` ledger entry.

### AI insights

`POST /ai/insights` and `GET /ai/insights/summary` call the OpenAI API with the customer's own orders as context. They need `OPENAI_API_KEY`; without it they return HTTP 503. Requests are rate limited to 5 per minute per user (HTTP 429 with `Retry-After`).

## Project structure

```
campus-bite-project/
├── README.md
├── docker-compose.yml          # db (Postgres 16) + api
├── project-brief.txt
├── docs/                       # COMPLIANCE.md, RESPONSIVE_CHECK.md
├── backend/
│   ├── Dockerfile
│   ├── docker-entrypoint.sh    # alembic upgrade head, then uvicorn
│   ├── docker/initdb/          # creates the campusbite_test database
│   ├── .env.example
│   ├── requirements.txt, requirements-dev.txt
│   ├── alembic/                # migrations
│   ├── app/
│   │   ├── main.py             # FastAPI instance `app`
│   │   ├── api/                # deps.py and routers/
│   │   ├── core/               # config, security, errors
│   │   ├── db/, models/, schemas/
│   │   ├── services/           # order state machine, AI, reminders, stats...
│   │   ├── middleware/
│   │   └── scheduler.py        # reminder scheduler
│   ├── scripts/                # seed.py 
│   └── tests/
└── frontend/
    ├── .env.example
    ├── vercel.json             # SPA rewrite
    ├── package.json
    └── src/                    # api/, components/, context/, hooks/, pages/, styles/, utils/
```

## Run the frontend locally

Requires Node.js 22.12 or later. The backend must be running (see below) for data to load.

```bash
cd frontend
npm install
cp .env.example .env      # PowerShell: Copy-Item .env.example .env
npm run dev
```

Open http://localhost:5173. `VITE_API_BASE_URL` in `frontend/.env` defaults to `http://localhost:8000`.

Other commands: `npm run build` (production build into `dist/`), `npm run preview`, `npm test`.

## Run the backend with Docker Compose

Requires Docker with Compose v2.

```bash
cp backend/.env.example backend/.env     # PowerShell: Copy-Item backend/.env.example backend/.env
# edit backend/.env: set JWT_SECRET (32+ characters), optionally OPENAI_API_KEY
docker compose up --build -d
```

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Compose starts a `db` service (Postgres 16, port 5432) and the `api` service (port 8000). Inside Compose, `DATABASE_URL` is overridden to point at the `db` service and `ENABLE_SCHEDULER` is `true`, so the values in `backend/.env` for those two do not matter.

- Health check: http://localhost:8000/health
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Stop with `docker compose down` (add `-v` to delete the database volume).

## Environment variables

Backend (`backend/.env`, template `backend/.env.example`):

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `DATABASE_URL` | Yes | none | SQLAlchemy URL, `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DB`. The app refuses to start without it. |
| `TEST_DATABASE_URL` | Tests only | none | Database used by pytest, normally `campusbite_test`. |
| `JWT_SECRET` | Yes | none | HS256 signing secret, at least 32 characters. |
| `JWT_EXPIRE_MINUTES` | No | `60` | Access token lifetime in minutes. |
| `OPENAI_API_KEY` | No | empty | Enables AI insights. Without it the AI endpoints return 503. |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model used for insights. |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Comma-separated list of allowed browser origins. |
| `ENABLE_SCHEDULER` | No | `false` | Run the background reminder scheduler. `true` under Compose, `false` on Vercel. |
| `REMINDER_THRESHOLD_MINUTES` | No | `15` | Minutes without a status update before a reminder is created. |
| `AI_RATE_LIMIT_PER_MINUTE` | No | `5` | AI requests allowed per user per minute. |

Frontend (`frontend/.env`, template `frontend/.env.example`):

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `VITE_API_BASE_URL` | Yes | `http://localhost:8000` (from the example) | Base URL of the backend, no trailing slash. Baked in at build time. |

`.env` files are gitignored. Never commit real values.

## Database setup

- **Migrations.** The container entrypoint runs `alembic upgrade head` on every start, so `docker compose up --build` creates the schema automatically. To run them by hand: `cd backend && alembic upgrade head` (with `DATABASE_URL` set).
- **Seed data.** After the stack is up, load the demo data (idempotent, safe to repeat):

  ```bash
  docker compose exec api python -m scripts.seed
  ```

  Without Docker: `cd backend && python -m scripts.seed`. The script prints the demo credentials.
- **Test database.** On first creation of the Postgres volume, `backend/docker/initdb/` creates a second database, `campusbite_test`. If your volume existed before, create it with `docker compose exec db psql -U campusbite -c "CREATE DATABASE campusbite_test;"`.

## API documentation

The API is self-documented by FastAPI: Swagger UI at `/docs`, ReDoc at `/redoc`, and the raw schema at `/openapi.json` (locally http://localhost:8000/docs). Protected endpoints take `Authorization: Bearer <token>` from `POST /auth/login`. Errors are 401 (not authenticated), 403 (wrong role), 404 (missing or belonging to another user or restaurant) and 409 (invalid state transition). List endpoints accept pagination parameters.

Roles: **Public** = no token, **Any** = any logged-in user, **Customer**, **Owner** (restaurant owner), **Partner** (delivery partner).

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | Public | Service and database health (200 or 503) |
| POST | `/auth/register` | Public | Register a user; an owner also gets a restaurant |
| POST | `/auth/login` | Public | Log in and receive a JWT and profile |
| GET | `/auth/me` | Any | Current user's profile |
| GET | `/restaurants` | Public | List restaurants with average rating; `search` by name or cuisine |
| GET | `/restaurants/{restaurant_id}` | Public | Restaurant details |
| GET | `/restaurants/{restaurant_id}/menu` | Public | A restaurant's menu |
| GET | `/restaurants/{restaurant_id}/reviews` | Public | A restaurant's reviews, newest first |
| GET | `/dishes` | Public | Search dishes across restaurants by name and price |
| POST | `/orders` | Customer | Place an order with a dummy card payment |
| GET | `/orders/me` | Customer | List my orders, newest first |
| GET | `/orders/{order_id}` | Customer | Get one of my orders |
| POST | `/orders/{order_id}/cancel` | Customer | Cancel my order while it is `PLACED` |
| POST | `/orders/{order_id}/review` | Customer | Review a delivered or refunded order |
| POST | `/orders/{order_id}/return` | Customer | Request a return for a delivered order |
| GET | `/owner/menu-items` | Owner | List my menu items |
| POST | `/owner/menu-items` | Owner | Create a menu item |
| PATCH | `/owner/menu-items/{item_id}` | Owner | Update a menu item |
| DELETE | `/owner/menu-items/{item_id}` | Owner | Delete a menu item |
| PATCH | `/owner/menu-items/{item_id}/availability` | Owner | Mark a dish available or unavailable |
| GET | `/owner/orders` | Owner | List my restaurant's orders; filter by status and date |
| PATCH | `/owner/orders/{order_id}/status` | Owner | Move an order to `ACCEPTED`, `PREPARING` or `READY` |
| GET | `/owner/delivery-partners` | Owner | List delivery partners available for assignment |
| POST | `/owner/orders/{order_id}/assign` | Owner | Assign a delivery partner to a `READY` order |
| GET | `/owner/returns` | Owner | List my restaurant's return requests |
| POST | `/owner/returns/{order_id}/approve` | Owner | Approve a return and refund the order |
| POST | `/owner/returns/{order_id}/reject` | Owner | Reject a return request |
| GET | `/owner/stats` | Owner | Restaurant statistics |
| GET | `/owner/reminders` | Owner | List my restaurant's reminders |
| PATCH | `/owner/reminders/{reminder_id}/resolve` | Owner | Resolve a reminder |
| GET | `/partner/orders` | Partner | My assigned orders (active by default) |
| GET | `/partner/orders/{order_id}` | Partner | One of my assigned orders |
| PATCH | `/partner/orders/{order_id}/status` | Partner | Move my order to `OUT_FOR_DELIVERY` or `DELIVERED` |
| GET | `/partner/history` | Partner | My delivered and refunded orders |
| POST | `/ai/insights` | Customer | Ask a question about my orders (AI) |
| GET | `/ai/insights/summary` | Customer | Summarize my last five orders (AI) |

## Demo credentials

Created by `python -m scripts.seed`. The password for every account is `Password123!` (demo data only).

| Role | Name | Email |
| --- | --- | --- |
| Customer | Alice Customer | `alice@campusbite.example.com` |
| Customer | Bob Customer | `bob@campusbite.example.com` |
| Restaurant owner | Priya Owner (Campus Curry House) | `owner.curry@campusbite.example.com` |
| Restaurant owner | Rahul Owner (Byte Burgers) | `owner.burgers@campusbite.example.com` |
| Restaurant owner | Mei Owner (Noodle Lab) | `owner.noodles@campusbite.example.com` |
| Delivery partner | Dave Rider | `dave@campusbite.example.com` |
| Delivery partner | Erin Rider | `erin@campusbite.example.com` |

The seed also creates 16 dishes and sample orders in the states `PLACED`, `ACCEPTED`, `READY`, `ASSIGNED`, `DELIVERED`, `CANCELLED` and `REFUNDED`. Use any 16-digit number for the dummy card, for example `4242424242424242`.

## Running tests

Backend tests run on your machine against the Compose `db` service (the `.dockerignore` keeps `tests/` out of the API image, so `docker compose exec api pytest` is not available).

```bash
docker compose up -d db
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
set TEST_DATABASE_URL=postgresql+psycopg://campusbite:campusbite@localhost:5432/campusbite_test
pytest
```

On macOS/Linux use `export TEST_DATABASE_URL=...` instead of `set`. In PowerShell use `$env:TEST_DATABASE_URL="..."`. The database credentials above are the local Compose defaults, not production values.

Frontend tests and build:

```bash
cd frontend
npm test
npm run build
```

## Deployment

The backend and frontend are two separate Vercel projects, with Supabase Postgres as the database. Install the Vercel CLI (`npm i -g vercel`) and log in with `vercel login`.

1. **Supabase.** Create a project. From Project Settings > Database copy two connection strings (replace the password, keep `sslmode=require`, and use the `postgresql+psycopg://` scheme):
   - Direct or session connection, port **5432**: used only to run migrations.
   - Transaction pooler, port **6543**: used by the Vercel backend.
2. **Migrate and seed the production database** from `backend/` with the port 5432 URL:

   ```bash
   cd backend
   export DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/postgres?sslmode=require"
   alembic upgrade head
   python -m scripts.seed
   ```

3. **Backend project** (root `backend/`, Vercel FastAPI runtime, `app/main.py` exports `app`):

   ```bash
   cd backend
   vercel link
   vercel env add DATABASE_URL production        # transaction pooler URL, port 6543
   vercel env add JWT_SECRET production
   vercel env add OPENAI_API_KEY production
   vercel env add CORS_ORIGINS production        # set after the frontend is deployed
   vercel env add ENABLE_SCHEDULER production    # false
   vercel deploy --prod
   ```

   Optional: `OPENAI_MODEL`, `JWT_EXPIRE_MINUTES`, `REMINDER_THRESHOLD_MINUTES`. On Vercel the app uses `NullPool` and `prepare_threshold=None`, which the pooler requires.
4. **Frontend project** (root `frontend/`; `vercel.json` rewrites all routes to `index.html`):

   ```bash
   cd frontend
   vercel link
   vercel env add VITE_API_BASE_URL production   # the backend URL from step 3
   vercel deploy --prod
   ```

5. **Update CORS.** Set the backend `CORS_ORIGINS` to the frontend production URL (`vercel env rm CORS_ORIGINS production`, then `vercel env add CORS_ORIGINS production`) and redeploy the backend with `vercel deploy --prod`.
6. **Smoke test** the Customer, Owner and Delivery partner flows with the demo accounts:

   ```bash
   cd backend
   python -m scripts.smoke_test https://<backend-url>
   ```
7. Record the live URLs in the table at the top of this README.

Environment variables live in Vercel project settings only, never in the repository.

## Known limitations

- On Vercel the AI rate limiter keeps its counters in memory, so the 5 per minute limit applies per function instance, not globally.
- Vercel has no long-running process, so the scheduler is disabled (`ENABLE_SCHEDULER=false`). Reminders are generated when the owner opens the dashboard or the reminders list. Under Docker Compose the scheduler runs in the background.
- Payments are simulated. No real money moves.
- AI insights require an OpenAI API key and network access.
