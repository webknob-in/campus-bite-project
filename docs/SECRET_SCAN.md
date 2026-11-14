# Secret scan

Run from the repo root: `powershell -File scripts/secret_scan.ps1` (exit 0 = clean, 1 = findings).
It uses `gitleaks detect --source . --log-opts="--all"` when installed, otherwise regex searches over
`git log --all -p` (added lines only), plus checks that no `.env` file (other than `.env.example`) was ever
committed or is tracked, and that `backend/.env` and `frontend/.env` are gitignored.

## Latest run (task 17.3)

- Date: 2026-11-14 (local clock)
- Tool: git-history regex fallback (gitleaks not installed)
- Scope: all commits on all refs; `.kiro/` is untracked and not scanned
- Real secrets found: **0**

| Pattern | Hits | Classification |
|---|---|---|
| `sk-[A-Za-z0-9]{20,}` | 0 | none |
| `postgresql(+psycopg)://user:pass@` | 11 | placeholders (`DB_USER:DB_PASSWORD@`, `USER:PASSWORD@`), test fixtures (`u:p@`), dev default `campusbite:campusbite@` (local docker database, accepted) |
| `JWT_SECRET=` | 7 | placeholder in `.env.example`, test fixtures (`VALID_SECRET`, `TEST_JWT_SECRET`) |
| `OPENAI_API_KEY=` | 4 | empty in `.env.example`, test fixtures (`sk-secret-123` log-redaction test), doc text |
| `password=` | 20 | test/demo fixtures, form validation code, `hide_password=False` |
| `BEGIN ... PRIVATE KEY` | 0 | none |
| `.env` files ever added | only `backend/.env.example`, `frontend/.env.example` | ok |

Other checks: `git check-ignore -v` shows `.gitignore:2:.env` for `backend/.env` and `frontend/.env`;
`git ls-files` lists only the two `.env.example` files; `docker compose config` shows only placeholders
and the dev default `POSTGRES_PASSWORD: campusbite`; `git status --short` showed only `.kiro/` untracked.
The demo seed password `Password123!` is a documented demo credential, not a secret.
