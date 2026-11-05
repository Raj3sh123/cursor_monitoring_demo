# Demo Linux Server Monitoring

Local demo for viewing live Linux CPU, memory, network, and listening ports. The app binds to `127.0.0.1` only.

Internal support teams sign in, register a server by name and IP, and read CPU, memory, network, and listening ports collected over SSH. Metrics stay read-only. SSH credentials stay in the environment, not in the form or the API response.

## Run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

`APP_ENV` selects `development` (the default), `testing`, or `production`. Production refuses to start unless `SECRET_KEY` is set. For a WSGI process, bind localhost:

```bash
gunicorn --bind 127.0.0.1:5000 app:app
```

API docs are at [http://127.0.0.1:5000/apidocs/](http://127.0.0.1:5000/apidocs/) and [http://127.0.0.1:5000/api/openapi.json](http://127.0.0.1:5000/api/openapi.json). The metrics endpoint accepts the browser session or an `Authorization: Bearer` token issued at sign-in.

## Sign in

Username `admin`, password `admin123`.

The password is stored only as a Werkzeug hash in SQLite. A failed sign-in shows a generic error. Set `SECRET_KEY` in the environment for anything beyond this local demo. If it is unset, the app uses a local development default.

## Database

SQLite file: `monitor.db` in the project directory. Override the path with `DATABASE`. The file is created on first run and the admin user is added when missing. `*.db` is gitignored.

## Add a server

After sign-in, enter a display name (1–64 characters) and an IP address. Open the server to view metrics, then use **Remove** to delete it. The form does not ask for SSH credentials.

## SSH

Set these in the environment, or in a gitignored `.env` file (see `.env.example`):

```bash
export SSH_USER=monitor
export SSH_KEY_PATH=/path/to/id_ed25519
```

`SSH_PASSWORD` can be used instead of a key. The host must accept SSH from this machine on port 22. This demo accepts the server host key on connect. If SSH fails, the server page shows an error and does not crash.

## Refresh, alerts, and export

The server page requests fresh metrics every **5 seconds**. The app keeps the last **60** samples. A badge shows **Alert** when CPU is above **80%** or memory is above **85%**. **Export CSV** on the server page downloads those samples. The file contains metrics only.

## Tests and CI

```bash
pytest
```

GitHub Actions (`.github/workflows/ci.yml`) installs dependencies and runs `pytest` on push and pull request. The workflow has no secrets. Tests use a temporary SQLite database.

Do not commit `.env` or `*.db`.

## Usage examples

Sign in in the browser, then add a server named `edge` with IP `192.0.2.10`. Open that server to see the live page. It refreshes every 5 seconds.

Download the saved samples:

```bash
curl -b cookies.txt -o metrics.csv http://127.0.0.1:5000/servers/1/export
```

Read the same server as JSON. A browser session cookie works. So does the bearer token stored in the session at sign-in:

```bash
curl -b cookies.txt http://127.0.0.1:5000/servers/1/metrics
curl -H "Authorization: Bearer <token>" http://127.0.0.1:5000/servers/1/metrics
```

A successful body includes `server`, `cpu_percent`, `memory`, `network`, `ports`, `alert`, and `history`. An unknown server returns 404. A request with no session and no token returns 401.

Remove the server from the dashboard with **Remove**, or:

```bash
curl -b cookies.txt -X POST \
  -d "csrf_token=<token from the page>" \
  http://127.0.0.1:5000/servers/1/delete
```

## Project layout

```text
app.py                 Application factory, hooks, and localhost entry point
config.py              development, testing, and production settings
auth.py                Session check, bearer token check, and CSRF
blueprints/            HTTP routes for sign-in, server pages, metrics, and OpenAPI
services/auth.py       Password check; returns id and username only
services/metrics.py    SSH collection and sample storage
present.py             Dashboard, metrics JSON, and CSV formatting
schemas.py             Request validation and response schemas
collector.py           Fixed SSH command and metric parsing
db.py                  Parameterized SQLite access
templates/             Sign-in, dashboard, server, and error pages
static/                CSS and the 5-second refresh script
tests/                 App, collector, and service tests
docs/requirements.md   Product requirements for the demo
.github/workflows/     Pytest on push and pull request
```

Pages call the services, then format the plain dicts those services return. SQL stays in `db.py`. The remote command stays in `collector.py`.
