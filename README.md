# Synseer Vendor Database

A production-ready Flask application for tracking, scoring, and visualizing component vendors. Built with Notion as the datastore and designed for AWS App Runner deployment.

## Architecture

**Clean Separation of Concerns:**
- **`populate_databases.py`** - Standalone script to populate Notion with demo data
- **Web Application** - Production-ready app that reads from Notion databases
- **No Mock Data** - Always connects to real Notion databases

## Quick Start

### 1. Prerequisites
- Python 3.11+
- Notion account with API access
- Real Notion credentials (no mock data support)

### 2. Environment Setup
```bash
# Clone and install
git clone <repository-url>
cd vendor-database
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file with your Notion credentials
NOTION_API_KEY=your_integration_api_key
VENDORS_DB_ID=your_vendors_database_id
PARTS_DB_ID=your_parts_database_id
SCORES_DB_ID=your_scores_database_id
```

### 3. Notion Database Setup
1. Create 3 databases in Notion: **Vendors**, **Parts**, **Scores**
2. Add your integration to all databases (Share → Add Integration)
3. Copy database IDs from URLs to your `.env` file

### 4. Populate Databases
```bash
# Validate database schemas
python populate_databases.py --validate

# Populate with 30 vendors + 60 parts of realistic demo data
python populate_databases.py

# Force populate (if data already exists)
python populate_databases.py --force
```

### 5. Run Application
```bash
# Development
python app.py

# Open http://localhost:8080
```

## Features

### Core Functionality
- ✅ **Vendor Scoring**: 4-pillar scoring system (Cost, Time, Reliability, Capacity)
- ✅ **Interactive Weights**: Real-time scoring adjustments (PDF page 11 style)
- ✅ **Risk Detection**: Automated identification of cost spikes, delays, capacity issues
- ✅ **Analytics Dashboard**: Trends, rankings, and executive summaries
- ✅ **Responsive Design**: Mobile-friendly interface with modern styling

### Technical Features
- ✅ **Pure Notion Integration**: No mock data - always live data
- ✅ **REST API**: Complete JSON API for all operations
- ✅ **AWS App Runner Ready**: Production deployment optimized
- ✅ **Rate Limiting**: Respects Notion API limits with automatic retries
- ✅ **Error Handling**: Graceful failures with detailed logging

## Database Population

The `populate_databases.py` script generates realistic supply chain data:

### 30 Vendors Across 7 Regions:
- **Asian** (KR, CN, VN): High volume, competitive pricing
- **European** (EU): Premium quality, higher costs
- **North American** (US, MX): Balanced performance  
- **Indian** (IN): Emerging market opportunities

### 60 Parts Including:
- **Batteries**: Li-ion, Li-poly, LiFePO4 variants
- **Sensors**: Heart rate, SpO2, temperature, accelerometer
- **Chips**: ARM Cortex, Nordic nRF, ESP32, Qualcomm
- **Components**: Displays, haptics, connectors, housings

### Realistic Data:
- **Regional pricing** variations and authentic component costs
- **Lead times** 2-12 weeks based on supplier reliability
- **Transit times** by shipping mode (Air: 1-9d, Ocean: 7-50d)
- **Current tariff rates** reflecting real trade policies
- **Production capacity** 5K-200K units based on supplier size

## API Documentation

### Core Endpoints

- **GET /api/vendors** - Ranked vendor list with filtering
- **GET /api/vendors/{id}** - Detailed vendor information  
- **POST /api/weights** - Update scoring weights
- **POST /api/recompute** - Trigger score recalculation
- **GET /api/analytics/trends** - Trend data for charts
- **GET /api/healthz** - Health check (AWS App Runner)

### Query Parameters for /api/vendors:
- `sort`: final_score, total_cost, total_time, reliability, capacity
- `component`: Filter by component name (partial match)
- `region`: Filter by vendor region (US, EU, KR, CN, VN, MX, IN)
- `limit`: Max results (default 50)

## Scoring Methodology

### Formula
```
Final Score = Σ (weight_p × score_p,v)
```

### Default Weights
1. **Total Cost (40%)** - Average landed cost (FOB + freight + tariff)
2. **Total Time (30%)** - Combined lead time + transit time  
3. **Reliability (20%)** - Historical performance score
4. **Capacity (10%)** - Monthly production capability

### Risk Detection
- **Cost Spikes**: >10% month-over-month increases
- **Delay Risk**: Extended transit times by mode
- **Capacity Shortfall**: Insufficient production capacity
- **Stale Data**: Information >30 days old

## AWS App Runner Deployment

### Build and Deploy
```bash
# Create ECR repository
aws ecr create-repository --repository-name synseer-vendor-db

# Build and push
docker build -t synseer-vendor-db .
docker tag synseer-vendor-db:latest $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/synseer-vendor-db:latest
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/synseer-vendor-db:latest

# Create App Runner service
aws apprunner create-service \
  --service-name synseer-vendor-db \
  --source-configuration file://apprunner-config.json
```

### Environment Variables for AWS
- `NOTION_API_KEY` - Store in AWS Secrets Manager
- `VENDORS_DB_ID` - Your Notion vendors database ID
- `PARTS_DB_ID` - Your Notion parts database ID  
- `SCORES_DB_ID` - Your Notion scores database ID

## Database Schemas

### Vendors Database
- **Name** (Title) - Company name
- **Region** (Select) - US, EU, KR, CN, VN, MX, IN
- **Reliability Score** (Number) - 0.0-1.0 performance metric
- **Contact Email** (Email) - Primary contact
- **Last Verified** (Date) - Data freshness tracking

### Parts Database  
- **Component Name** (Title) - Part identifier
- **Vendor** (Relation) - Link to vendors database
- **ODM Destination** (Text) - Target ODM facility
- **ODM Region** (Text) - ODM location
- **Unit Price** (Number) - FOB price per unit
- **Freight Cost** (Number) - Shipping cost per unit
- **Tariff Rate** (Number) - Import duty percentage (as decimal)
- **Lead Time (weeks)** (Number) - Production lead time
- **Transit Days** (Number) - Shipping duration
- **Shipping Mode** (Select) - Air, Ocean, Ground
- **Monthly Capacity** (Number) - Production capacity
- **Last Verified** (Date) - Data update timestamp

### Scores Database (Auto-populated by app)
- **Vendor** (Relation) - Link to vendors database
- **Total Cost Score** (Number) - Normalized cost score
- **Total Time Score** (Number) - Normalized time score
- **Reliability Score** (Number) - Reliability metric  
- **Capacity Score** (Number) - Normalized capacity score
- **Final Score** (Number) - Weighted final score
- **Weights JSON** (Text) - Configuration snapshot
- **Inputs JSON** (Text) - Input data snapshot
- **Snapshot Date** (Date) - Computation timestamp

## Development Workflow

```bash
# 1. Set up environment
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure Notion
# Create .env with your Notion credentials

# 3. Populate databases  
python populate_databases.py --validate
python populate_databases.py

# 4. Run application
python app.py

# 5. Test and iterate
# Edit data in Notion, refresh scoring in app
```

## File Structure

```
├── app.py                  # Main application entry point
├── populate_databases.py   # Standalone database population script
├── Dockerfile             # Production container
├── apprunner.yaml         # AWS App Runner configuration
├── requirements.txt       # Python dependencies
├── app/
│   ├── __init__.py        # Flask app factory  
│   ├── api.py            # REST API endpoints
│   ├── routes.py         # Web routes  
│   ├── models.py         # Data models
│   ├── notion_repo.py    # Notion integration
│   ├── scoring.py        # Scoring engine
│   ├── utils.py          # Utility functions
│   ├── templates/
│   │   └── index.html    # SPA shell
│   └── static/
│       ├── css/styles.css
│       └── js/app.js
└── tests/                # Test suite
    ├── test_api.py
    └── test_scoring.py
```

## Troubleshooting

### Connection Issues
- Verify `NOTION_API_KEY` is correct
- Ensure integration has access to all databases
- Check database IDs are copied correctly from Notion URLs

### Population Script Issues  
```bash
# Schema validation errors
python populate_databases.py --validate

# Import/dependency errors  
pip install -r requirements.txt

# Rate limiting (automatic retries built-in)
# Just wait - script handles Notion rate limits automatically
```

### Application Issues
```bash
# Empty vendor list
# Run populate_databases.py first

# API errors
# Check logs and verify .env configuration

# Health check failures (AWS)
# Ensure app binds to 0.0.0.0:$PORT and /api/healthz returns 200
```

## Production Deployment

### Pre-deployment
1. **Populate databases** with production data using `populate_databases.py`
2. **Test locally** with real Notion credentials
3. **Validate** all functionality works with your data

### AWS App Runner
- Uses `Dockerfile` and `apprunner.yaml`
- Requires environment variables in AWS Secrets Manager
- Automatic scaling and health checks included
- Deploy from ECR or directly from source code

### Security
- Store secrets in AWS Secrets Manager
- Enable HTTPS through App Runner custom domains  
- Use non-root container user (implemented)
- Enable CloudTrail for audit logging

---

**Production-ready vendor logistics database for modern supply chain management.**

## Streamlit App (alternative to Flask/App Runner)

A Streamlit UI is provided in `streamlit_app.py` that reuses the existing Notion and scoring logic.

### Run locally

1. Install deps:
   
   ```bash
   pip install -r requirements.txt
   ```

2. Export environment variables (or create a `.streamlit/secrets.toml` as below):
   
   ```bash
   set NOTION_API_KEY=...      # Windows PowerShell: $env:NOTION_API_KEY="..."
   set VENDORS_DB_ID=...
   set PARTS_DB_ID=...
   set SCORES_DB_ID=...
   ```

3. Start Streamlit:
   
   ```bash
   streamlit run streamlit_app.py
   ```

### Streamlit Cloud deployment

1. Push this repo to GitHub.
2. In Streamlit Cloud, create a new app pointing to your repo.
3. Set the app entrypoint to `streamlit_app.py`.
4. Configure Secrets (Settings → Secrets) as TOML:
   
   ```toml
   NOTION_API_KEY = "..."
   VENDORS_DB_ID = "..."
   PARTS_DB_ID = "..."
   SCORES_DB_ID = "..."
   SECRET_KEY = "change-me"
   ```

No additional build steps are required; `requirements.txt` includes Streamlit and Altair.