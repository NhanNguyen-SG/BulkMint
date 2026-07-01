# Local Development

This guide starts BulkMint from a clean clone. The backend and frontend run as
separate local processes.

## Prerequisites

- Python 3.11 through 3.14
- [uv](https://docs.astral.sh/uv/)
- Node.js 20.9 or newer
- npm or pnpm
- A Supabase project with the existing `cards` table
- An OpenAI API key

Do not commit populated environment files.

## Backend

From the repository root:

```sh
cd backend
cp .env.example .env
```

Set `OPENAI_API_KEY` in `backend/.env`, then create the environment and install
the locked runtime and development dependencies:

```sh
uv sync --all-groups
```

Start FastAPI on the loopback interface:

```sh
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Useful backend checks:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy main.py
uv run pytest
```

No backend test suite exists yet, so `pytest` will report that no tests were
collected until tests are added in a later phase.

## Frontend

Open another terminal from the repository root:

```sh
cd frontend
cp .env.example .env.local
```

Set the Supabase URL and public anon key in `frontend/.env.local`.

The committed `package-lock.json` makes npm the canonical reproducible
installer:

```sh
npm ci
npm run dev
```

The frontend is available at <http://localhost:3000>.

If dependencies are already installed, pnpm can run the same scripts:

```sh
pnpm dev
pnpm lint
pnpm build
```

To use pnpm as the installer instead, run `pnpm install`, but do not mix npm and
pnpm installations in the same working tree. Standardizing on pnpm would
require committing and maintaining a `pnpm-lock.yaml` in a separate change.

## Validation

Backend:

```sh
cd backend
uv sync --locked --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy main.py
```

Frontend:

```sh
cd frontend
npm ci
npm run lint
npm run build
```

The current frontend calls the backend at `http://localhost:8000`, and the
backend CORS configuration permits `http://localhost:3000`. Deployment
configuration is intentionally outside this foundation phase.
