# SmartSpend AI deployment (Render)

## Local Windows
1. Open this folder in VS Code.
2. `py -m venv .venv`
3. ` .\.venv\Scripts\Activate.ps1` (without the leading space)
4. `python -m pip install -r requirements.txt`
5. `python app.py` and open http://127.0.0.1:5000

## Deploy to Render
1. Create a GitHub repository and upload the contents of this folder (not the ZIP itself).
2. In Render, choose **New + → Web Service**, connect the GitHub repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variable `SECRET_KEY` with a long random value.
6. For persistent SQLite data, attach a persistent disk mounted at `/var/data`. The included `render.yaml` expects that path. Persistent disks may require a paid Render plan. Without persistent storage, SQLite data on a free ephemeral instance can be lost on restart/redeploy.
7. Deploy and open the Render-provided HTTPS URL.

## Important
- This is a demo prototype. It has no login or multi-user isolation; do not enter sensitive financial information.
- Chart.js loads from a CDN, so the browser needs internet access for charts.
- Keep `SECRET_KEY` private. Never commit real secrets.
