# PRD: Demo Linux Server Monitoring

## 1. Overview

Local demo app for internal L1/L2/L3 and app teams to view **real-time Linux server metrics** (CPU, memory, network, listening ports) without SSH’ing into each host.

**Scope:** Demo only. Run on the same machine as Cursor via `python app.py`.

## 2. Problem

Operators must log into each Linux server to check live CPU, memory, network, and port usage. That is slow and error-prone for shared support teams.

## 3. Goals

- Show live metrics in a simple read-only UI.
- Collect **real** data over **SSH** from registered Linux hosts.
- Single admin login; add servers by name + IP.
- Minimal local setup (Flask + SQLite).

## 4. Non-goals

- Multi-user / L1–L3 role model
- Agents installed on targets
- Cloud / production HA deploy
- Windows/non-Linux hosts
- Per-server SSH credentials in the UI

## 5. Users

| Role | Access |
|------|--------|
| Admin (only account) | Sign in, add/remove servers, view all metrics |

Default username: `admin`  
Default password: `admin123` (stored **hashed** in SQLite; never plain text)

## 6. Core features

### F1 — Read-only monitoring UI

- After login, metric views are **read-only** (no remote commands from the UI beyond metric collection).
- Writable actions limited to: **add server**, **remove server**, **sign out**.
- Friendly layout (cards/tables) for CPU, memory, network, listening ports.
- **Auto-refresh** every **5 seconds** (AJAX/fetch; no full page reload required).
- UI stack: **Bootstrap** + Flask/Jinja templates (plain CSS only where needed).

### F2 — Sign-in

- Login page with username + password.
- Single seeded user: `admin` / `admin123` (password hashed, e.g. Werkzeug).
- Session-based auth; unauthenticated users redirected to login.
- No registration / password reset in demo.

### F3 — Add Linux servers

- Form fields: **Name**, **IP** only.
- Persist in SQLite.
- List registered servers; open a detail view per server.
- Allow remove from the list.
- SSH access uses **shared credentials from config** (not entered per server), e.g. env or `config.py`:
  - `SSH_USER`
  - `SSH_KEY_PATH` (preferred) or `SSH_PASSWORD`
- Target hosts must allow SSH from the demo machine with that identity.

### F4 — Live metrics (must-have)

Collected via SSH on each refresh (example commands; implementation may use `paramiko`):

| Metric | What to show |
|--------|----------------|
| CPU | Overall usage % (and optionally load average) |
| Memory | Used / total / available (and %) |
| Network | Per-interface RX/TX bytes or rates |
| Ports | **Listening** ports (proto, port, optional process if cheap to fetch) |

Show last-updated time and clear error state if SSH/collection fails.

### F5 — Alerts, history, export (must-have, demo-light)

| Capability | Demo behavior |
|------------|----------------|
| Alerts | Thresholds: CPU > 80% or memory > 85% → badge/banner on dashboard/server page |
| History | Keep last **N** samples in SQLite (e.g. N=60); simple line charts (CPU & memory) |
| Export | Button to download current metrics (and/or recent history) as **CSV** |

## 7. Tech stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3, Flask |
| Frontend | Bootstrap + Jinja2 |
| DB | SQLite |
| Remote | Paramiko (SSH) |
| Charts | Lightweight JS chart lib (e.g. Chart.js) |
| Run | `python app.py` (default `http://127.0.0.1:5000`) |

## 8. Data model (minimal)

**users:** id, username, password_hash  

**servers:** id, name, ip, created_at  

**metric_samples:** id, server_id, collected_at, cpu_percent, mem_used, mem_total, network_json, ports_json  

## 9. Screens (minimal)

1. **Login**
2. **Dashboard** — server list, status (OK / error / alert), sparklines or % summary
3. **Server detail** — live CPU/memory/network/ports, history charts, export, remove
4. **Add server** — name + IP

## 10. Local run (minimal)

1. Create venv and install deps (`flask`, `paramiko`, etc.).
2. Set SSH config for targets (`SSH_USER`, key/password).
3. Ensure demo host can SSH to each listed IP.
4. `python app.py`
5. Open `http://127.0.0.1:5000` → login `admin` / `admin123` → add server → view metrics.

## 11. Acceptance criteria

- [ ] Login works only with `admin` + correct password; hash stored in DB.
- [ ] Wrong password rejected; protected pages require session.
- [ ] Add server with name + IP; appears on dashboard.
- [ ] Detail page shows real CPU, memory, network, listening ports via SSH.
- [ ] UI auto-refreshes ~every 5s.
- [ ] Metric UI is read-only; only inventory add/remove (and logout) mutate app state.
- [ ] Alert badges when thresholds exceeded.
- [ ] Recent history chart for CPU/memory.
- [ ] CSV export available.
- [ ] App starts with `python app.py` on the Cursor host.

## 12. Out of scope notes for implementers

- Do not build role-based access for L1/L2/L3 (they share the admin demo account).
- Do not put SSH passwords in the Add Server form.
- Prefer fail-soft UI messages over crashes when a host is unreachable.
