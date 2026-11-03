# Demo Linux Server Monitoring

Local demo for viewing Linux server metrics. This step serves a placeholder dashboard only.

## Run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

The app listens on `127.0.0.1` only. Do not commit `.env` files or database files.
