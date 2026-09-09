# LabelBox

LabelBox is a mobile-first compliance scanner for packaged commodities. Legal Metrology enforcement officers can photograph a product label, extract visible mandatory declarations with OCR, and receive a cited compliance review under the Legal Metrology (Packaged Commodities) Rules, 2011.

> This is a hackathon demonstrator. OCR and rule outcomes support officer review; they are not legal advice or an automatic enforcement decision.

## What it does

- Officer login with JWT authentication and `@nic.in` email validation.
- Inspection sessions for grouping scans by store visit.
- Mobile camera capture or image upload.
- OpenCV image cleanup and EasyOCR text extraction.
- Extraction of MRP, net quantity, manufacture/packing date, manufacturer details, and consumer-care contact details.
- Five cited checks from Rule 6(1), with `critical`, `major`, and `minor` workflow severity tiers.
- Session summary, IndexedDB offline queue, service-worker app-shell caching, and retry on reconnect.
- Authenticated PDF export of a session report.


## UI 

![Officer Login](docs/images/Picture1.png)
![Start Session](docs/images/Picture2.png)
![Label Capture](docs/images/Picture3.png)
![Compliance Results](docs/images/Picture4.png)

## Stack

| Layer | Technology |
|---|---|
| Frontend | Plain HTML, CSS, vanilla JavaScript, Tailwind CSS CDN |
| PWA / offline | Web Manifest, Service Worker, IndexedDB |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy |
| Database | PostgreSQL on Neon, configured through `DATABASE_URL` |
| Authentication | JWT and bcrypt |
| OCR | EasyOCR and OpenCV |
| PDF reports | ReportLab |
| Tests | pytest, FastAPI TestClient, in-memory SQLite |

The frontend is deliberately framework-free: there is no React application, bundler, or Node build step.

## Project layout

```text
backend/
  app/
    api/            # Auth, session, and scan endpoints
    db/             # SQLAlchemy models and demo seeding
    rules/          # Rule 6(1) registry and individual checks
    services/       # Preprocessing, OCR, parser, session/PDF reports
    tests/          # Backend unit and API tests
  alembic/          # PostgreSQL migrations
  requirements.txt
frontend/
  index.html        # Vanilla-JS single-page application
  js/               # API client, application state, offline queue
  css/              # Tokens and interaction styles
  sw.js             # Service worker
  manifest.json
```

## Quick start

### 1. Create a Python environment

From the project root on Windows:

```powershell
py -3.12 -m venv sih2026venv
.\sih2026venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

### 2. Configure the database

Create `backend/.env` and set the Neon pooled connection string:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@YOUR-POOLER-HOST/DATABASE?sslmode=require
JWT_SECRET_KEY=replace-this-for-any-non-demo-deployment
```

Use the pooled Neon URL for normal application traffic. Run Alembic migrations with a direct, non-pooled connection string.

### 3. Run migrations and seed demo officers

```powershell
cd backend
..\sih2026venv\Scripts\python.exe -m alembic upgrade head
..\sih2026venv\Scripts\python.exe -m app.db.seed
```

### 4. Start the app

```powershell
cd backend
..\sih2026venv\Scripts\uvicorn.exe app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). FastAPI serves both the API and the frontend.

## Demo accounts

| Officer | Email | Password |
|---|---|---|
| Inspector Rajesh Sharma | `rajesh.sharma@nic.in` | `officer123` |
| Inspector Priya Verma | `priya.verma@nic.in` | `officer123` |

Use only for local demo data. Do not retain these credentials in a production deployment.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/auth/login` | Obtain an officer JWT |
| `GET` | `/auth/me` | Get current officer profile |
| `POST` | `/sessions` | Start an inspection session |
| `GET` | `/sessions` | List the officer's sessions |
| `GET` | `/sessions/{id}` | Get session metadata |
| `POST` | `/sessions/{id}/scans` | Upload and process a label image |
| `GET` | `/sessions/{id}/scans` | List scans in a session |
| `GET` | `/scans/{id}` | Retrieve a scan and its findings |
| `GET` | `/sessions/{id}/report` | Retrieve session totals and scan summary |
| `GET` | `/sessions/{id}/report/pdf` | Download the cited PDF report |

## Rule coverage

The current representative rule subset checks these mandatory declarations:

| Rule | Declaration | Workflow severity when missing/invalid |
|---|---|---|
| 6(1)(a) | Net quantity | Major |
| 6(1)(b) | Manufacturer/packer name and complete address | Critical |
| 6(1)(e) | Maximum Retail Price | Major |
| 6(1)(f) | Manufacture/packing date | Minor |
| 6(1)(g) | Consumer-care contact details | Minor |

Severity is a product triage label, not a statutory penalty classification.

## OCR notes and limitations

- Large phone photos are downscaled to a maximum 1600 px edge before OCR to keep memory use safe.
- A clear photo of the complete declaration panel is essential. Glare, blur, partial framing, curved packages, and thermal-print labels can prevent reliable extraction.
- When a value cannot be read reliably, LabelBox should return it as not detected for officer review rather than infer a declaration.
- The configured PyTorch environment must include a CUDA-enabled build before EasyOCR can use an NVIDIA GPU. The current code automatically enables GPU only when `torch.cuda.is_available()` is true.

