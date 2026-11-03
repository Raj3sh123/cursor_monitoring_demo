# TODO: Demo Linux Server Monitoring

Small increments for local demo (`python app.py`). Check items in order. Each step includes security and a short doc note.

## 1. Project initialization and basic UI

- [x] Create Python project layout: `app.py`, `requirements.txt`, `templates/`, `static/`
- [x] Add Flask app that serves one page on `http://127.0.0.1:5000`
- [x] Add Bootstrap layout: nav + placeholder dashboard (no live data yet)
- [x] Add `.gitignore` (venv, `__pycache__`, `*.db`, `.env`)
- [x] **Security:** bind to `127.0.0.1` only; do not commit secrets
- [x] **Docs:** `README.md` — create venv, `pip install -r requirements.txt`, `python app.py`

## 2. Sign-in and unit tests

- [ ] Add login page (username + password) and logout
- [ ] Seed one user: `admin` / `admin123` with a hashed password (Werkzeug)
- [ ] Session cookie; redirect unauthenticated users to login
- [ ] Add `pytest` tests: good login, bad password, protected route redirects
- [ ] **Security:** store password hash only; generic login error; `SECRET_KEY` from env (dev default only locally)
- [ ] **Docs:** README — default login and that the password is hashed

## 3. CI (GitHub Actions)

- [ ] Add `.github/workflows/ci.yml`: install deps, run `pytest` on push/PR
- [ ] **Security:** no secrets in the workflow; tests use a temp SQLite DB
- [ ] **Docs:** README — CI runs tests on GitHub

## 4. SQLite persistence

- [ ] Add SQLite init for `users` and `servers`
- [ ] Create admin user on first run if missing
- [ ] **Security:** DB file gitignored; parameterized queries only
- [ ] **Docs:** README — DB file path

## 5. Add and remove servers

- [ ] Add server form: **name** + **IP** only; save and list on dashboard
- [ ] Remove server action; detail page stub
- [ ] **Security:** login required; validate name length and IP format; CSRF on forms
- [ ] **Docs:** README — how to add a server

## 6. SSH metric collection

- [ ] Add shared SSH settings via env: `SSH_USER`, `SSH_KEY_PATH` (or `SSH_PASSWORD`)
- [ ] Collect CPU, memory, network, listening ports (Paramiko); fail with a message if SSH fails
- [ ] Show values on the server page (read-only)
- [ ] **Security:** credentials only in env; no SSH fields in the UI; no shell input from the user
- [ ] **Docs:** README — set `SSH_USER` and key path

## 7. Auto-refresh

- [ ] JSON endpoint for one server’s latest metrics
- [ ] Refresh the detail page every 5s via fetch
- [ ] **Security:** endpoint requires login; return only that server’s metrics
- [ ] **Docs:** README — refresh interval

## 8. Alerts, history, and CSV export

- [ ] Store last 60 samples; badge when CPU > 80% or memory > 85%
- [ ] CPU and memory line chart (Chart.js)
- [ ] CSV download of recent samples
- [ ] **Security:** login required; CSV contains metrics only (no secrets)
- [ ] **Docs:** README — thresholds, history size, export button

## 9. Finish local demo

- [ ] Confirm `python app.py` on this machine: login → add server → live metrics
- [ ] **Security:** confirm `.env` and `*.db` are not committed
- [ ] **Docs:** README matches the steps above
