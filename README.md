# Digital MRV — Community Invasive-Species Removal & Biomass Monitoring

A prototype Measurement, Reporting & Verification (MRV) tool for tracking
biomass and land use on a community working plot across three phases:

- **Baseline** — before invasive removal
- **During removal** — clearing operations / biomass removed
- **Post-removal** — after removal, restoration outcomes, land-use change

## Files

| File | Purpose |
|---|---|
| `mrv_core.py` | Core engine — plots, species/allometry database, biomass→carbon→CO2e calculations, verification checks, JSON persistence |
| `app.py` | Streamlit web app (data entry + dashboard + reports) |
| `demo_run.py` | Standalone script that runs a worked example and generates a markdown report + charts without needing Streamlit |
| `requirements.txt` | Python dependencies |

## 1. Run it locally (2 minutes)

```bash
pip install -r requirements.txt
streamlit run app.py
```

This opens the app at `http://localhost:8501`. Click **"Load demo scenario"**
in the sidebar to explore it immediately with sample data, or start
registering your own plot.

> **Note on data persistence:** this prototype keeps data in memory for the
> browser session (`st.session_state`). Use the **Data Export / Import**
> page to download a JSON snapshot and re-upload it later, or on another
> device. For production use with many plots/monitors, replace this with a
> real database (see "Next steps" below).

## 2. Deploy it for free — Streamlit Community Cloud (recommended, ~5 min)

Streamlit Community Cloud will host the app at a public URL
(`https://<your-app-name>.streamlit.app`) for free.

1. **Create a GitHub repository** and push these four files to it
   (`app.py`, `mrv_core.py`, `demo_run.py`, `requirements.txt`):
   ```bash
   git init
   git add app.py mrv_core.py demo_run.py requirements.txt README.md
   git commit -m "Digital MRV prototype"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
2. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in
   with your GitHub account.
3. Click **"New app"**, select your repository, branch `main`, and set the
   main file path to `app.py`.
4. Click **Deploy**. Streamlit installs `requirements.txt` automatically
   and gives you a public URL within a minute or two.
5. Any time you push new commits to the repo, the deployed app
   auto-updates.

## 3. Alternative free/low-cost hosts

- **Hugging Face Spaces** — create a new Space, choose the "Streamlit" SDK,
  and push the same files (via `git` or the web UI). Free tier available.
- **Render.com** — create a new "Web Service" from your GitHub repo,
  set the start command to `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`.
- **Railway.app** — similar flow to Render; auto-detects `requirements.txt`.

All three work the same way: connect a GitHub repo, point at `app.py`, and
the platform handles the server for you — no infrastructure to manage.

## Next steps for a production deployment

This is a working prototype, not a production system. Before real
community deployment, consider:

- **Locally validated allometric equations** — replace the placeholder
  coefficients in `SPECIES_DB` (`mrv_core.py`) with equations validated for
  your actual invasive/native species and region (national biomass tables,
  IPCC default values, or field-calibrated regressions).
- **Persistent database** — swap the in-memory `MRVSystem`/JSON export for
  SQLite or PostgreSQL so data survives app restarts and supports many
  concurrent plots/monitors.
- **Photo storage** — wire the file uploader to real object storage
  (e.g., S3-compatible bucket) instead of just recording filenames.
- **User accounts / roles** — separate community monitors (data entry)
  from verifiers (who sign off on events), with login and audit trail.
- **Offline-first mobile capture** — for field use without connectivity,
  consider a lightweight mobile form (e.g., KoBoToolbox, ODK) that syncs
  into this system's data model when back online.
- **Independent verification** — the current `verify_event()` checks are
  basic completeness rules; a real MRV process typically needs third-party
  spot-checks and remote-sensing cross-validation (e.g., satellite NDVI)
  for higher assurance.
