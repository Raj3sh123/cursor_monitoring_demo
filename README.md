# Demo Linux Server Monitoring

Local demo for viewing live Linux CPU, memory, network, and listening ports. The app binds to `127.0.0.1` only.

## Run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

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
