# Vendor Database

A vendor logistics scoring and analytics app with a Streamlit UI and Notion as the datastore. It helps you compare suppliers, detect risks, map your portfolio (Kraljic), track compliance, and export snapshots for reporting.

## What it does (high level)

- Unified supplier score
  - Combines four pillars (Cost, Time, Vendor Maturity, Capacity) into one comparable score
  - Pillar weights are configurable in the app (defaults 40/30/20/10)
- Risk visibility
  - Flags compliance issues (e.g., UFLPA, Conflict Minerals, audits, ISO cert coverage)
  - Highlights operational and supply chain risks (staleness, delays, cost spikes, short capacity)
  - Thresholds are adjustable in Settings
- Portfolio view (Kraljic)
  - Places suppliers into Strategic / Leverage / Bottleneck / Routine quadrants
  - Uses spend and risk; fallback logic provided when explicit risk is missing
- Compliance overview
  - Quick, transparent vendor-level compliance scoring with part-level rollups (RoHS/REACH)
- Analytics & insights
  - KPIs, trends (prototype), and cost-vs-time bubble charts to spot outliers
- Save & export
  - Save the current vendor scores to Notion (snapshot per vendor per click)
  - Download current scores as CSV/XLSX
- Built-in documentation
  - About page consolidates how scoring, risks, Kraljic, compliance, analytics, and export work

## Notion setup (minimal)

Create 3 Notion databases and connect your integration:
- Vendors (VENDORS_DB_ID)
- Parts (PARTS_DB_ID)
- Scores (SCORES_DB_ID)

Recommended properties
- Vendors: Name (Title), Region (Select), Contact Email (Email), Last Verified (Date). Optional: enhanced maturity fields (see About).
- Parts: Component Name (Title), Vendor (Relation → Vendors), Unit Price, Freight Cost, Tariff Rate, Lead Time, Transit Days, Shipping Mode, Monthly Capacity, Last Verified.
- Scores (app writes): Title (auto-filled), Vendor (Relation), Total Cost/Time/Vendor Maturity/Capacity/Final Score (Percent), Snapshot (Date+time), Weights JSON, Inputs JSON.

## Quick start (Streamlit)

Prereqs: Python 3.11+, Notion integration + DB IDs

```bash
git clone <repo>
cd vendor_tracking_app
python -m venv venv
# Windows PowerShell:
./venv/Scripts/Activate.ps1
# macOS/Linux:
source venv/bin/activate
pip install -r requirements.txt

# Env (or use Streamlit Secrets below)
set NOTION_API_KEY=...
set VENDORS_DB_ID=...
set PARTS_DB_ID=...
set SCORES_DB_ID=...

streamlit run streamlit_app.py
```

Streamlit Secrets (Cloud) → Settings → Secrets (TOML):
```toml
NOTION_API_KEY="..."
VENDORS_DB_ID="..."
PARTS_DB_ID="..."
SCORES_DB_ID="..."
```

## Using the app

- Vendors page: sort/filter, compare scores, open details, scan risk badges
- Analytics: view KPIs, trend (prototype), and cost–time scatter
- Kraljic: see suppliers mapped to quadrants; adjust thresholds in Settings
- Compliance: vendor-level score with part-level indicators
- Settings: adjust weights and thresholds; Save Scores to Notion or download CSV/XLSX
- About: concise reference for scoring, risks, Kraljic, compliance, analytics, and export

## Save & export

- Notion: one snapshot per vendor per save; auto Title “{Vendor} – {YYYY‑MM‑DD HH:MM:SS}”; Snapshot (date‑time)
- CSV/XLSX: export current scores from the Settings page

## Demo data (optional)

```bash
python populate_databases.py --validate   # check schemas
python populate_databases.py              # generate demo vendors/parts
# add --force to add more data when Notion isn’t empty
```

## Troubleshooting (brief)

- No vendors or zero data: verify Notion IDs/API key; populate demo data if desired
- Notion save fails: confirm SCORES_DB_ID and schema; integration has access
- Rate limits: retries are built in; try again in a few seconds

---
Purpose-built for transparent supplier comparison, risk awareness, and portfolio decisions, with a simple Notion backend and Streamlit UI.