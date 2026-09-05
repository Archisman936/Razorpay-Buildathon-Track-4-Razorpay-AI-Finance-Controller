# Razorpay AI Finance Controller

> **Track 4 — AI Finance Controller | Razorpay Buildathon**

An end-to-end, AI-augmented financial reconciliation system built on top of a Razorpay-style payment-gateway data model. It automates the complete reconciliation pipeline — from raw file ingestion through deterministic rule matching, ML-assisted ambiguity resolution, automated exception classification, RAG-powered evidence retrieval, and Gemini LLM explanations — served through a FastAPI backend and a React dashboard.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Running Locally](#2-running-locally)
3. [Running with Docker & Docker Hub](#3-running-with-docker--docker-hub)
4. [High-Level Architecture](#4-high-level-architecture)
5. [Data Generation](#5-data-generation)
6. [Data Sources & Schema](#6-data-sources--schema)
7. [Parsing](#7-parsing)
8. [Validation](#8-validation)
9. [Normalization](#9-normalization)
10. [PostgreSQL — Financial Source of Truth](#10-postgresql--financial-source-of-truth)
11. [Deterministic Reconciliation](#11-deterministic-reconciliation)
12. [ML Development](#12-ml-development)
13. [ML Model Artifacts](#13-ml-model-artifacts)
14. [Backend Structure](#14-backend-structure)
15. [Reconciliation Pipeline](#15-reconciliation-pipeline)
16. [RAG — Retrieval-Augmented Generation](#16-rag--retrieval-augmented-generation)
17. [LLM — Gemini Integration](#17-llm--gemini-integration)
18. [Frontend Overview](#18-frontend-overview)
19. [Dashboard](#19-dashboard)
20. [File Upload Pipeline](#20-file-upload-pipeline)
21. [AI Chatbot](#21-ai-chatbot)
22. [API Endpoints](#22-api-endpoints)
23. [Project Structure](#23-project-structure)
24. [Environment Variables](#24-environment-variables)
25. [Installation](#25-installation)
26. [PostgreSQL Setup](#26-postgresql-setup)
27. [Data Generation & Loading](#27-data-generation--loading)
28. [ML Training](#28-ml-training)
29. [RAG Ingestion](#29-rag-ingestion)
30. [Complete First-Time Setup Sequence](#30-complete-first-time-setup-sequence)
31. [Testing](#31-testing)
32. [System Health](#32-system-health)
33. [Security](#33-security)
34. [Limitations](#34-limitations)
35. [Demo Workflow](#35-demo-workflow)
36. [Design Principles](#36-design-principles)

---

## 1. Project Overview

### What it does

The **Razorpay AI Finance Controller** automates the process of financial reconciliation across a payment-gateway ecosystem. It ingests raw financial files (CSV, XLSX, PDF, JSON), normalises them into a canonical form, stores them in PostgreSQL, and then runs a multi-tier reconciliation pipeline to determine which records match, which are ambiguous, and which represent genuine exceptions.

### The business problem

In a payment-gateway environment, money flows through many systems simultaneously:

- Merchants generate orders and invoices
- Razorpay collects payments and deducts fees
- Razorpay batches payments into settlement events
- Banks process those settlements and produce bank statements
- GST records must match invoice tax amounts
- Book entries must balance double-entry

At scale, even small discrepancies — a ±1-day date shift, a narration format variation, an ID prefix mismatch — create thousands of unmatched records per cycle. Manual reconciliation at this volume is expensive, slow, and error-prone.

### Why reconciliation is difficult

- **Format heterogeneity**: every source uses different field names, date formats, and amount representations
- **Identifier noise**: the same payment might appear as `PAY_000123`, `PAY000123`, or `pay-000123` across systems
- **Timing differences**: banks process settlements 1–3 days after the event
- **Partial amounts**: fees, taxes, and refunds mean the "expected" and "received" amounts are rarely identical
- **Missing records**: not every event produces a matching record in every system
- **Duplicates**: bank feeds occasionally duplicate entries

### How the system automates reconciliation

| Stage | Mechanism |
|---|---|
| Ingestion | FastAPI file upload → parser → validator |
| Normalisation | Rule-based field mapping, ID canonicalisation, currency/date normalisation |
| Storage | PostgreSQL (financial source of truth) |
| Deterministic reconciliation | Exact ID / UTR / amount / date rules |
| ML matching | Logistic Regression classifier on 35 engineered features |
| Exception classification | Logistic Regression 7-class classifier on discrepancy features |
| Evidence retrieval | RAG: ChromaDB + `all-MiniLM-L6-v2` embeddings over documentation |
| AI explanation | Google Gemini LLM synthesises structured evidence into natural language |
| Presentation | React dashboard with live metrics, transaction lookup, and AI chat |

### Layer separation

| Layer | Role |
|---|---|
| **Deterministic** | Authoritative, auditable rule-based matching |
| **ML** | Resolves ambiguous candidates that survive deterministic rules |
| **RAG** | Retrieves domain knowledge and supporting evidence |
| **LLM** | Synthesises, explains, and answers natural-language questions |

The LLM **never determines financial truth**. Financial decisions are made by deterministic rules and ML; the LLM explains those decisions.

---

## 2. Running Locally

### Backend (FastAPI + Uvicorn)

```bash
# 1. Activate your Python virtual environment
.venv\Scripts\activate                    # Windows PowerShell
# source .venv/bin/activate               # Linux/macOS

# 2. Run backend server
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# With auto-reload for development
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Backend API**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **System Health Endpoint**: `http://127.0.0.1:8000/api/v1/health`

### Frontend (Vite + React)

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start Vite development server
npm run dev
```

- **Frontend Application**: `http://localhost:5173`
- The Vite development server automatically proxies `/api` and `/health` requests to `http://localhost:8000`.

---

## 3. Running with Docker & Docker Hub

Pre-built, production-ready container images are published on Docker Hub under `archisman2006`:
- **Backend Image**: `archisman2006/razorpay-backend:latest`
- **Frontend Image**: `archisman2006/razorpay-frontend:latest`

### Option A: One-Click Full Stack via Docker Compose (Recommended)

Run the entire system (PostgreSQL 15 + FastAPI Backend + Nginx React Frontend) in one command:

```bash
# 1. Start all containers in the background
docker compose up -d

# 2. Verify running services
docker compose ps

# 3. View live container logs
docker compose logs -f
```

- **Frontend Web Dashboard**: `http://localhost` (Port 80)
- **Backend API & Swagger Docs**: `http://localhost:8000/docs`
- **PostgreSQL Database**: `localhost:5432`

To shut down the stack:
```bash
docker compose down
```

### Option B: Pull & Run Pre-Built Images from Docker Hub

Pull the official images directly:

```bash
docker pull archisman2006/razorpay-frontend:latest
docker pull archisman2006/razorpay-backend:latest
```

**Run Backend container**:
```bash
docker run -d \
  --name razorpay_backend \
  -p 8000:8000 \
  -e DB_HOST=host.docker.internal \
  -e DB_PORT=5432 \
  -e DB_NAME=razorpay_recon \
  -e DB_USER=postgres \
  -e DB_PASSWORD=your_postgres_password \
  -e GEMINI_API_KEY=your_gemini_api_key \
  archisman2006/razorpay-backend:latest
```

**Run Frontend container**:
```bash
docker run -d \
  --name razorpay_frontend \
  -p 80:80 \
  -e BACKEND_URL=http://host.docker.internal:8000 \
  archisman2006/razorpay-frontend:latest
```

### Option C: Build and Push Docker Images Locally

If you modify code and wish to build fresh images:

```bash
# Build Backend image
docker build -t archisman2006/razorpay-backend:latest -f backend/Dockerfile .

# Build Frontend image
docker build -t archisman2006/razorpay-frontend:latest -f frontend/Dockerfile ./frontend
```

Automated build and push scripts:
```powershell
# Windows PowerShell
.\scripts\docker_build_and_push.ps1 -Username archisman2006 -Tag latest
```
```bash
# Linux / macOS Bash
./scripts/docker_build_and_push.sh archisman2006 latest
```

---

## 4. High-Level Architecture

```
╔══════════════════════════════════════════════════════════╗
║                  RAW INPUT FILES                         ║
║          CSV / XLSX / JSON / JSONL / PDF                 ║
╚══════════════════════════════════════════════════════════╝
                           │
                    PARSING LAYER
          backend/app/services/normalization/parsers/
                           │
                   VALIDATION LAYER
        backend/app/services/normalization/validation/
                           │
                  NORMALISATION LAYER
       backend/app/services/normalization/transforms/
       backend/app/services/normalization/mappings/
                           │
                        PIPELINE
       backend/app/services/normalization/pipeline.py
                           │
                ┌──────────▼──────────┐
                │     POSTGRESQL      │
                │  razorpay_recon DB  │ ◄── Financial Source of Truth
                └──────────┬──────────┘
                           │
              DETERMINISTIC RECONCILIATION
         backend/app/services/reconciliation/
              rules.py / matcher.py / resolver.py
                           │
             UNMATCHED / AMBIGUOUS RECORDS
                           │
                  ML RECONCILIATION
           backend/app/services/reconciliation/
                  ml_ranking.py
           tools/ML_Models/Reconciliation Model/
                   (Logistic Regression)
                           │
                EXCEPTION CLASSIFICATION
       backend/app/services/reconciliation/
                exception_features.py
       tools/ML_Models/Exception Classification/
                   (Logistic Regression)
                           │
               RAG — EVIDENCE RETRIEVAL
              backend/app/rag/
              ChromaDB + all-MiniLM-L6-v2
                           │
                GEMINI LLM — EXPLANATION
              backend/app/llm/
              google-genai SDK
                           │
                FASTAPI BACKEND RESPONSE
              backend/app/api/routes/
                           │
                  REACT FRONTEND
              frontend/src/
```

---

## 5. Data Generation

### Overview

All data in this project is **synthetic**, generated deterministically from a clean financial simulation of Indian e-commerce merchants using a Razorpay-style payment gateway.

### Generation philosophy

```
Clean Financial World
        │
        ▼
   Ground Truth
   (event_links, reconciliation_truth, exception_truth)
        │
        ▼
  Corruption Engine
  (noise, missing records, ID variants, date drift)
        │
        ▼
   Noisy Source Data
   (data/raw/noisy/)
```

Every entity is derived from its parent — no records are created independently. Relationships are enforced at generation time.

### Generation dependency order

```
Merchant (root)
   │
   ├── Customer
   │
   └── Order
        │
        ├── Invoice ── GST Record
        │
        └── Payment
               ├── Fee
               ├── Refund
               └── Settlement ── Bank Record
                          └── Adjustment

Order / Payment / Settlement / Invoice ── Book Entries (double-entry)
```

### Dataset scale

| Entity | Target | Generated |
|---|---|---|
| Merchants | 5 | 5 |
| Customers | 500 | 500 |
| Orders | 2,000 | 2,000 |
| Invoices | ~1,800 | 1,726 |
| GST Records | ~1,800 | 1,726 |
| Payments | 2,000 | 2,000 |
| Fees | 2,000 | 2,000 |
| Refunds | ~150 | 155 |
| Settlements | ~200 | 173 |
| Bank Records | ~2,200 | 547 |
| Book Entries | 4,000+ | 12,276 |
| Adjustments | ~50 | 50 |

### Corruption types applied to raw data

| Type | Rate | Description |
|---|---|---|
| ID Noise | 15% | Format variants: dashes, slashes, lowercase, no separator |
| Description Noise | 30% | Bank narration format variations |
| Date Noise | 20% | ±1–3 day shifts |
| Amount Noise | 8% | Small discrepancies with tracked cause codes |
| Missing Records | 2–5% | Records removed per entity type |
| Duplicates | 3% | Near-duplicate records with slight variations |
| Wrong References | 5% | Cross-references swapped between entities |

Corruption is **reproducible** (global seed: 42) and logged to `data/raw/noisy/corruption_log.jsonl`.

### Relevant scripts

```bash
python tools/data_generation/generate_all.py      # Generate all synthetic data
python scripts/normalize_all.py                   # Normalise raw → canonical
python scripts/load_canonical.py                  # Load normalised data into PostgreSQL
```

### Data directories

| Directory | Contents |
|---|---|
| `data/raw/synthetic/` | Clean synthetic source records |
| `data/raw/noisy/` | Corrupted versions (used for loading) |
| `data/ground_truth/` | Reconciliation truth, exception truth, event links |
| `tools/ML_Models/ML_data/` | Train/validation/test splits for ML training |

---

## 6. Data Sources & Schema

The database `razorpay_recon` contains 14 tables representing a complete payment-gateway ecosystem.

### Entity relationships

```
merchants ─── customers ─── orders ─── invoices ─── gst_records
                                │
                            payments ─── fees
                                │
                                ├── refunds
                                │
                                └── settlement_payments
                                           │
                                       settlements ─── adjustments
                                           │
                                       bank_records

All events ── books (double-entry ledger)
```

### Key tables

| Table | Primary Key | Description |
|---|---|---|
| `merchants` | `merchant_id` | Merchant business profile |
| `customers` | `customer_id` | Customer records linked to merchant |
| `orders` | `order_id` | Customer orders with GST breakdown |
| `invoices` | `invoice_id` | Tax invoices generated from completed orders |
| `payments` | `payment_id` | Payment captures by gateway (UPI/CARD/NETBANKING/WALLET) |
| `fees` | `fee_id` | Gateway fee deducted per payment |
| `refunds` | `refund_id` | Full/partial/reversal refunds |
| `settlements` | `settlement_id` | Batched settlements sent to merchant bank |
| `settlement_payments` | `(settlement_id, payment_id)` | Settlement ↔ Payment linkage |
| `bank_records` | `bank_record_id` | Bank statement entries (CREDIT/DEBIT) |
| `books` | `entry_id` | Double-entry ledger (debit + credit per event) |
| `gst_records` | `gst_record_id` | GST filings linked to invoices |
| `adjustments` | `adjustment_id` | Settlement adjustments (reversals, corrections) |

### ID format convention

All entities use the pattern `{PREFIX}_{NNNNNN}`:

| Entity | Prefix | Example |
|---|---|---|
| Merchant | MER | `MER_000001` |
| Customer | CUS | `CUS_000001` |
| Order | ORD | `ORD_000001` |
| Invoice | INV | `INV_000001` |
| Payment | PAY | `PAY_000001` |
| Fee | FEE | `FEE_000001` |
| Refund | REF | `REF_000001` |
| Settlement | STL | `STL_000001` |
| Bank Record | BNK | `BNK_000001` |
| Book Entry | LED | `LED_000001` |
| GST Record | GST | `GST_000001` |
| Adjustment | ADJ | `ADJ_000001` |

### Schema

The complete SQL schema is in `database/schema/schema.sql`. Every table includes lineage columns:

```sql
lineage_source              VARCHAR(50)     -- source system name
lineage_source_record_id    VARCHAR(100)    -- original record ID
lineage_source_file_id      VARCHAR(200)    -- source file path
lineage_source_row          INTEGER         -- row number in source file
lineage_ingested_at         TIMESTAMPTZ     -- ingestion timestamp
lineage_normalizer_ver      VARCHAR(20)     -- normalizer version
```

---

## 7. Parsing

The normalisation pipeline accepts the following raw file formats:

| Format | Extensions | Parser module |
|---|---|---|
| JSON Lines | `.jsonl` | `parsers/jsonl_parser.py` |
| JSON | `.json` | `parsers/json_parser.py` |
| CSV | `.csv` | `parsers/csv_parser.py` |
| Excel | `.xlsx`, `.xls` | `parsers/excel_parser.py` |
| PDF | `.pdf` | `parsers/pdf_parser.py` |

All parsers output a standardised list of dictionaries. The PDF parser uses `pdfplumber` for text-based PDFs and falls back to `pypdf` for scanned documents.

```
raw file → parser → [{ field: value, ... }, ...]
```

Parsers are located at `backend/app/services/normalization/parsers/`.

---

## 8. Validation

After parsing, each record passes through the validation layer (`backend/app/services/normalization/validation/`):

| Check | Behaviour on failure |
|---|---|
| Required field presence | Record quarantined with `MISSING_REQUIRED_FIELD` error |
| Schema type validation | Record quarantined with `TYPE_MISMATCH` error |
| Duplicate detection | Duplicate flagged, original retained |
| Financial consistency | Amount/tax cross-checks; failures quarantined |
| Malformed identifiers | Normalised if recoverable; quarantined if not |

**Quarantine behaviour**: Invalid records are not silently dropped — they are separated with a reason code and lineage trace, preserving auditability. Valid records continue to the normalisation step.

---

## 9. Normalisation

The normalisation layer (`backend/app/services/normalization/`) maps heterogeneous source records into canonical PostgreSQL-ready structures.

### Normalisation operations

| Operation | Description |
|---|---|
| **Field mapping** | Source field names → canonical PostgreSQL column names |
| **ID canonicalisation** | `PAY000123` / `pay-000123` → `PAY_000123` |
| **Amount normalisation** | String amounts → `NUMERIC(15,2)` |
| **Currency normalisation** | All amounts in INR; currency code standardised |
| **Date normalisation** | Mixed timezone strings → `TIMESTAMPTZ` UTC-normalised |
| **Status normalisation** | `"captured"` / `"CAPTURED"` → `"CAPTURED"` |
| **Text normalisation** | Whitespace trimming, unicode normalisation |
| **Lineage injection** | Source file, row, and ingestion timestamp attached |

### Package structure

```
backend/app/services/normalization/
├── pipeline.py          # Orchestrates parse → validate → transform → load
├── parsers/             # Format-specific parsers (CSV, JSON, XLSX, PDF)
├── transforms/          # Entity-specific field mapping and type coercion
├── mappings/            # Field alias dictionaries per source entity
└── validation/          # Schema and financial consistency checks
```

---

## 10. PostgreSQL — Financial Source of Truth

> **PostgreSQL is the single source of financial truth in this system.**
> ML, RAG, and LLM all read from or refer to the database but never replace it.

### Connection

Configured via environment variables (see [Section 22](#22-environment-variables)):

```
Host:     POSTGRES_HOST   (default: localhost)
Port:     POSTGRES_PORT   (default: 5432)
Database: POSTGRES_DB     (default: razorpay_recon)
User:     POSTGRES_USER   (default: postgres)
Password: POSTGRES_PASSWORD
```

Alternatively, set `DATABASE_URL` as a full DSN string.

### Initialising the database

```bash
# Create the database (as postgres superuser)
psql -U postgres -c "CREATE DATABASE razorpay_recon;"

# Apply schema (all tables, indexes, constraints)
psql -U postgres -d razorpay_recon -f database/schema/schema.sql
```

### Key indexes

Every major foreign key relationship is indexed. Key indexes include:

- `idx_customers_merchant` — on `customers(merchant_id)`
- `idx_payments_merchant`, `idx_payments_order` — on `payments`
- `idx_bank_records_settlement`, `idx_bank_records_date` — on `bank_records`
- `idx_books_reference`, `idx_books_entity` — on `books`
- `idx_settlement_payments_both` — composite on `settlement_payments`

### Database access in the backend

The backend uses `psycopg2` with a connection pool pattern. The database layer is at `backend/app/database/`:

```
backend/app/database/
├── connection.py        # fetch_one(), fetch_all(), execute()
└── repositories/
    ├── bank_repository.py
    ├── payment_repository.py
    └── settlement_repository.py
```

---

## 11. Deterministic Reconciliation

Deterministic reconciliation runs **first**, before any ML. It is transparent, auditable, and produces no false positives.

### Reconciliation pairs

| Pair | Source | Target | Primary match signal |
|---|---|---|---|
| `ORDER_PAYMENT` | Order | Payment | `order_id` exact match + amount |
| `ORDER_INVOICE` | Order | Invoice | `order_id` exact match + amount |
| `PAYMENT_FEE` | Payment | Fee | `payment_id` exact match |
| `PAYMENT_REFUND` | Payment | Refund | `payment_id` exact match |
| `PAYMENT_SETTLEMENT` | Payment | Settlement | via `settlement_payments` linkage |
| `SETTLEMENT_BANK` | Settlement | Bank Record | UTR match + amount + fuzzy description |
| `INVOICE_GST` | Invoice | GST Record | `invoice_id` exact match + tax amounts |
| `EVENT_BOOKS` | Any event | Book Entry | `reference_id` match + debit=credit balance |
| `SETTLEMENT_ADJUSTMENT` | Settlement | Adjustment | `settlement_id` exact match |

### Matching tiers

**Tier 1 — Exact (deterministic)**: Applied first. If matched here, ML is not invoked.

| Rule | Fields checked | Tolerance |
|---|---|---|
| Exact ID match | `order_id`, `payment_id`, `settlement_id`, `invoice_id` | None |
| Exact UTR match | `utr` | None |
| Exact gateway reference | `gateway_reference` | None |
| Exact amount + same date | `amount`, `date` | Amount exact, same calendar day |

**Tier 2 — Fuzzy (feature-based)**: Applied to records that survive Tier 1 unmatched. Features are computed and passed to ML.

| Feature | Method | Threshold |
|---|---|---|
| ID similarity | Levenshtein / normalised edit distance | > 0.8 |
| Description similarity | TF-IDF cosine / RapidFuzz | > 0.7 |
| Amount difference | `abs(a−b) / max(a,b)` | < 5% |
| Date difference | `abs(date_a − date_b)` in days | ≤ 3 days |
| Reference similarity | Fuzzy string match on UTR/ref fields | > 0.75 |

**Tier 3 — ML**: Applied to ambiguous candidates that survive Tier 2.

### Why deterministic first?

Deterministic rules have zero false-positive risk for exact matches. Running them first means ML only handles genuinely ambiguous cases, reducing inference load and preserving explainability.

### Reconciliation service modules

```
backend/app/services/reconciliation/
├── reconciliation_service.py    # Main service, RecordNotFoundError
├── candidates.py                # Candidate generation window
├── deterministic.py             # Tier 1 and Tier 2 exact rules
├── feature_builder.py           # Feature engineering for ML input
├── ml_ranking.py                # ML inference call, threshold apply
├── exception_features.py        # Exception classification feature builder
└── structured_result.py         # Canonical result schema builder
```

---

## 12. ML Development

> The ML development notebooks are in `tools/ML_Models/ML_Models_Code/`.
> These are **the authoritative record** of all ML experimentation and model selection.

### A. ML Reconciliation (Binary Classifier)

**Notebook**: `tools/ML_Models/ML_Models_Code/Reconciliation_ML_Model.ipynb`

#### Problem definition

Binary classification: given a (bank_record, settlement_candidate) feature vector, predict whether this pair is a genuine match (`label=1`) or not (`label=0`).

This addresses the **residual ambiguity** that deterministic rules leave behind — cases where multiple candidates pass fuzzy thresholds and a ranking decision is needed.

#### Dataset

- **Source**: `tools/ML_Models/ML_data/matching/`
- **Split**: 70% train / 15% validation / 15% test, grouped by `source_id` to prevent leakage
- **Train**: 1,351 pairs | **Validation**: 289 pairs | **Test**: 291 pairs
- **Class imbalance**: heavily skewed toward non-match (label=0), addressed with `class_weight="balanced"`

#### Feature engineering (35 features)

Features are computed per candidate pair:

| Feature group | Examples |
|---|---|
| Amount signals | `absolute_amount_difference`, `amount_ratio`, `exact_amount_match`, `relative_amount_difference` |
| Date signals | `date_difference_days`, `same_day`, `within_1_day`, `within_3_days`, `within_7_days`, `value_date_difference_days` |
| Reference signals | `reference_exact_match`, `utr_similarity`, `description_token_overlap` |
| Settlement context | `settlement_gross_amount`, `settlement_net_amount`, `settlement_fee_amount`, `settlement_refund_amount` |
| Candidate ranking | `candidate_rank_by_amount`, `candidate_rank_by_date`, `candidate_rank_by_reference`, `candidate_count` |
| Competitive gap | `best_vs_second_best_amount_gap`, `best_vs_second_best_date_gap`, `best_vs_second_best_reference_gap` |
| Entity signals | `merchant_match`, `bank_category`, `transaction_type_is_credit`, `payment_count` |

#### Models evaluated

| Model | Validation F1 | Validation ROC-AUC | Validation PR-AUC |
|---|---|---|---|
| Logistic Regression | 1.000 | 1.000 | 1.000 |
| Random Forest | 1.000 | 1.000 | 0.9999 |
| XGBoost | 1.000 | 1.000 | 1.000 |
| LightGBM | 1.000 | 1.000 | 1.000 |

All four models achieved perfect validation metrics on the synthetic benchmark. **Logistic Regression was selected** as the final model based on interpretability, simplicity, and production suitability (fastest inference, no tree-based hyperparameters to tune, low serialisation cost).

#### Test set metrics (Logistic Regression)

| Metric | Value |
|---|---|
| Accuracy | 0.997 |
| Precision | 0.947 |
| Recall | 1.000 |
| F1 | 0.973 |
| Macro F1 | 0.986 |
| PR-AUC | 0.939 |
| ROC-AUC | 0.997 |

**Decision threshold**: 0.275 (tuned on validation set to maximise recall while controlling precision).

#### Leakage prevention

- Train/validation/test splits are grouped by `source_id` (bank record ID), so no bank record contributes pairs to more than one split.
- Reference features (`reference_exact_match`, `utr_similarity`) were audited: their presence in the feature set is legitimate because UTR matching is the business rule being learned, not a data leak.

#### Final artifact

```
tools/ML_Models/Reconciliation Model/
├── best_reconciliation_model.joblib   # Trained sklearn Pipeline
├── feature_schema.json               # Feature list, target, threshold
├── final_metrics.json                # Validation and test metrics
├── model_comparison.csv              # All model comparison results
├── ablation_results.csv              # Feature ablation study
├── classification_report.csv         # Full sklearn classification report
├── confusion_matrix.csv              # Test confusion matrix
├── training_summary.json             # Summary including integration role
└── test_predictions.csv             # Per-sample test predictions
```

---

### B. Exception Classification (7-Class Classifier)

**Notebook**: `tools/ML_Models/ML_Models_Code/Exception_Classification.ipynb`

#### Problem definition

Multi-class classification: given a record that **failed reconciliation**, predict which of 7 exception categories caused the failure.

#### Exception classes

| Class | Description |
|---|---|
| `AMOUNT_DISCREPANCY` | Numeric amount does not match expected value |
| `DESCRIPTION_MISMATCH` | Bank narration/description does not match reference |
| `DUPLICATE` | Record appears more than once |
| `FORMAT_MISMATCH` | Field format incompatibility (date, ID, currency) |
| `MISSING_RECORD` | Expected counterpart record is absent |
| `TIMING_DIFFERENCE` | Valid match but outside acceptable date window |
| `WRONG_REFERENCE` | Reference ID points to the wrong counterpart |

#### Dataset

- **Source**: `tools/ML_Models/ML_data/classification/`
- **Split**: 70% train / 15% validation / 15% test, stratified by class
- **Train**: 3,965 samples | **Validation**: 851 samples | **Test**: 851 samples

#### Feature engineering (19 features)

| Feature | Description |
|---|---|
| `entity_type` | Type of entity producing the exception (categorical) |
| `affected_field` | Which field triggered the exception (categorical) |
| `value_pair_present` | Whether both expected and actual values are present |
| `value_exact_match` | Exact string equality |
| `value_normalized_id_match` | Match after ID canonicalisation |
| `value_str_similarity` | String similarity score |
| `value_token_overlap` | Token overlap ratio |
| `value_numeric_diff`, `value_numeric_abs_diff`, `value_numeric_rel_diff` | Numeric difference signals |
| `value_is_numeric_pair` | Whether both values are numeric |
| `value_date_diff_days` | Date difference in days |
| `value_is_date_pair` | Whether both values are dates |
| `entity_amount` | Financial amount of the entity |
| `fee_amount_context`, `tax_amount_context`, `refund_amount_context`, `adjustment_amount_context` | Amount context from related entities |
| `diff_to_adjustment_ratio` | Ratio of discrepancy to any known adjustment |

#### Models evaluated

| Model | Validation Accuracy | Macro F1 | Weighted F1 | ROC-AUC (OvR) |
|---|---|---|---|---|
| Logistic Regression | 1.000 | 1.000 | 1.000 | 1.000 |
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 |
| XGBoost | 1.000 | 1.000 | 1.000 | 1.000 |
| LightGBM | 1.000 | 1.000 | 1.000 | 1.000 |

Again, all four models achieved perfect validation metrics on the synthetic benchmark. **Logistic Regression was selected** for the same reasons: interpretability, simplicity, and production suitability.

#### Test set metrics (Logistic Regression)

| Metric | Value |
|---|---|
| Accuracy | 1.000 |
| Balanced Accuracy | 1.000 |
| Macro Precision | 1.000 |
| Macro Recall | 1.000 |
| Macro F1 | 1.000 |
| Weighted F1 | 1.000 |
| ROC-AUC (OvR, macro) | 1.000 |

#### Final artifact

```
tools/ML_Models/Exception Classification/
├── best_exception_classifier.joblib    # Trained sklearn Pipeline
├── feature_schema.json               # Feature list, class mapping, target
├── final_metrics.json                # Validation and test metrics
├── model_comparison.csv              # All model results
├── class_mapping.json                # Class index ↔ label mapping
├── model_info.json                   # Model metadata
├── classification_report.csv         # Full per-class report
├── confusion_matrix.csv              # 7×7 confusion matrix
├── class_error_analysis.csv          # Per-class error breakdown
└── test_prediction_confidence.csv    # Per-sample confidence scores
```

---

## 13. ML Model Artifacts

```
tools/ML_Models/
├── Reconciliation Model/             # Binary match classifier
│   ├── best_reconciliation_model.joblib
│   ├── feature_schema.json
│   └── ...evaluation artifacts...
│
├── Exception Classification/         # 7-class exception classifier
│   ├── best_exception_classifier.joblib
│   ├── feature_schema.json
│   └── ...evaluation artifacts...
│
├── ML_Models_Code/                   # Training notebooks (DO NOT DELETE)
│   ├── Reconciliation_ML_Model.ipynb
│   └── Exception_Classification.ipynb
│
└── ML_data/                          # ML training datasets
    ├── matching/                     # Binary classification splits
    │   ├── train.csv
    │   ├── validation.csv
    │   └── test.csv
    └── classification/               # Multi-class classification splits
        ├── train.csv
        ├── validation.csv
        └── test.csv
```

### Model loading

The backend loads models at startup via `backend/app/ml/model_loader.py`:

```python
# ModelLoader reads from Settings:
# - settings.reconciliation_model_path   → best_reconciliation_model.joblib
# - settings.reconciliation_schema_path  → Reconciliation Model/feature_schema.json
# - settings.exception_model_path        → best_exception_classifier.joblib
# - settings.exception_schema_path       → Exception Classification/feature_schema.json
```

The backend **never retrains models**. It loads the serialised artifacts once at startup and uses them for inference throughout the application lifecycle.

---

## 14. Backend Structure

```
backend/
├── __init__.py
└── app/
    ├── main.py                          # FastAPI application entry point
    ├── api/
    │   ├── dependencies.py              # Dependency injection (settings, loader, pipeline)
    │   └── routes/
    │       ├── __init__.py              # Router registration
    │       ├── health.py                # GET /health, GET /api/v1/health
    │       ├── dashboard.py             # GET /api/v1/dashboard/summary
    │       ├── reconciliation.py        # POST /api/v1/reconciliation/run
    │       ├── transactions.py          # GET /api/v1/transactions/{type}/{id}
    │       ├── upload.py                # POST /api/v1/upload/file
    │       └── chat.py                  # POST /api/v1/chat/message
    ├── core/
    │   ├── config.py                    # Settings class (env-driven)
    │   └── logging.py                   # Structured logger
    ├── database/
    │   ├── connection.py                # psycopg2 connection pool, fetch_one/fetch_all
    │   └── repositories/
    │       ├── bank_repository.py
    │       ├── payment_repository.py
    │       └── settlement_repository.py
    ├── ml/
    │   └── model_loader.py              # Loads joblib artifacts, artifact_status()
    ├── rag/
    │   ├── config.py                    # RAGConfig dataclass
    │   ├── embeddings.py                # sentence-transformers wrapper
    │   ├── chunker.py                   # Document chunking
    │   ├── loaders.py                   # Markdown/text document loader
    │   ├── retriever.py                 # Top-k retrieval
    │   ├── vector_store.py              # ChromaDB wrapper
    │   └── service.py                   # Public RAGService interface
    ├── llm/
    │   ├── __init__.py                  # ReconciliationAgent, get_agent()
    │   ├── agent.py                     # LLM agent with tool use
    │   ├── gemini_service.py            # google-genai SDK wrapper
    │   ├── prompts.py                   # System prompts and templates
    │   └── response.py                  # ChatResponse dataclass
    ├── schemas/
    │   ├── common.py                    # HealthResponse, base schemas
    │   └── reconciliation.py            # ReconciliationResult, RunRequest
    └── services/
        ├── normalization/               # Parse → Validate → Transform → Load
        ├── reconciliation/              # Deterministic + ML + Exception
        └── orchestration/
            └── pipeline.py             # ReconciliationPipeline.run_case()
```

---

## 15. Reconciliation Pipeline

The complete execution path for a single reconciliation case:

```
POST /api/v1/reconciliation/run
  { "source_type": "bank_record", "source_id": "BNK_000123" }
                    │
         ReconciliationPipeline.run_case()
         backend/app/services/orchestration/pipeline.py
                    │
         1. Fetch source record from PostgreSQL
            BankRepository.get_by_id("BNK_000123")
                    │
         2. Deterministic reconciliation
            reconciliation_service.py
            → Build candidate window (±25 days)
            → Apply Tier 1 exact rules (UTR, amount+date)
            → If matched: DETERMINISTIC_MATCH → DONE
            → If unmatched: build Tier 2 fuzzy features
                    │
         3. ML reconciliation (if include_ml=True and ambiguous candidates)
            feature_builder.py → 35 feature vector
            ml_ranking.py → ModelLoader.predict_reconciliation()
            → Logistic Regression inference
            → Apply threshold=0.275
            → If score > threshold: ML_MATCH
            → If score < threshold: UNMATCHED
                    │
         4. Exception classification (if include_exception=True and unmatched)
            exception_features.py → 19 feature vector
            ModelLoader.predict_exception()
            → Logistic Regression inference
            → Returns one of 7 exception classes
                    │
         5. Build structured result
            structured_result.py
            → ReconciliationResult schema
            → Includes match_method, confidence, exception_class, evidence
                    │
         6. Return JSON response to frontend
```

---

## 16. RAG — Retrieval-Augmented Generation

RAG provides domain knowledge and reconciliation context to the LLM.

> **RAG does NOT determine financial truth.**
> It retrieves supporting documentation that the LLM uses to explain reconciliation decisions.

### Document sources

By default, RAG indexes all Markdown files in the `docs/` directory, including:

- `docs/FINANCIAL_RULES.md` — GST, payment method rules, settlement formulas
- `docs/RECONCILIATION_RULES.md` — matching tiers, reconciliation pairs, exception taxonomy
- `docs/SCHEMA.md` — entity schemas, field descriptions
- `docs/DATA_GENERATION_SPEC.md` — data generation methodology

### RAG pipeline

```
docs/ Markdown files
        │
   DocumentLoader      (backend/app/rag/loaders.py)
        │
   DocumentChunker     (backend/app/rag/chunker.py)
   chunk_size=500, overlap=50
        │
   EmbeddingService    (backend/app/rag/embeddings.py)
   all-MiniLM-L6-v2 via sentence-transformers
        │
   VectorStore         (backend/app/rag/vector_store.py)
   ChromaDB @ data/rag_vector_db/
        │
   Retriever           (backend/app/rag/retriever.py)
   top_k=5 nearest chunks per query
        │
   RAGService          (backend/app/rag/service.py)
   Public interface used by the LLM agent
```

### Embedding model

`all-MiniLM-L6-v2` from the `sentence-transformers` library. The model is downloaded automatically from HuggingFace on first use.

### Vector database

ChromaDB persisted at `data/rag_vector_db/`. The vector store is built once during RAG ingestion and reused across backend restarts. Rebuild with the `--force` flag if documentation changes.

---

## 17. LLM — Gemini Integration

### SDK

Uses the **current Google GenAI Python SDK** (`google-genai`), not the deprecated `google-generativeai`.

```python
from google import genai
```

### Configuration

```
GEMINI_API_KEY    # Required — Google AI Studio API key
GEMINI_MODEL      # e.g. gemini-2.0-flash (configurable)
```

### Agent architecture

```
User message
     │
ReconciliationAgent.chat()       (backend/app/llm/agent.py)
     │
GeminiService                    (backend/app/llm/gemini_service.py)
     │
System prompt + conversation history + RAG context
     │
Google Gemini API (google-genai SDK)
     │
ChatResponse (answer, sources, tools_used, confidence, metadata)
```

### Domain guardrails

- The system prompt explicitly instructs Gemini to act as a financial reconciliation assistant
- The LLM is instructed not to speculate about financial amounts not present in the database
- All reconciliation decisions are made by the deterministic/ML pipeline; Gemini explains them
- Conversation history is maintained per session; reset via `POST /api/v1/chat/reset`

### Error handling

The `GeminiService` includes retry logic for transient API errors. If the Gemini API is unavailable, the `/chat/message` endpoint returns an appropriate error — the reconciliation pipeline continues to function independently.

---

## 18. Frontend Overview

The frontend is a React single-page application built with Vite.

```
frontend/src/
├── main.jsx              # React entry point
├── App.jsx               # Router (react-router-dom) + Sidebar layout
├── api.js                # Centralized API client (all backend calls)
├── index.css             # Global styles and design tokens
├── components/
│   └── Sidebar.jsx       # Navigation sidebar
└── pages/
    ├── Dashboard.jsx     # Metrics dashboard
    ├── Reconciliation.jsx # Manual reconciliation runner
    ├── Transactions.jsx  # Transaction lookup
    ├── Upload.jsx        # File upload pipeline UI
    ├── Chat.jsx          # AI chatbot
    └── Health.jsx        # System health monitor
```

### API client

All backend communication goes through `frontend/src/api.js`. The Vite dev server proxies `/api/v1` → `http://localhost:8000`.

---

## 19. Dashboard

The dashboard (`/dashboard`) displays real metrics fetched from `GET /api/v1/dashboard/summary`.

| Metric | Source |
|---|---|
| Total bank records | `SELECT COUNT(*) FROM bank_records` |
| Reconciled records | `WHERE settlement_id IS NOT NULL` |
| Unreconciled records | `WHERE settlement_id IS NULL` |
| Reconciliation rate | `reconciled / total × 100` |
| Total discrepancy (₹) | Sum of unreconciled CREDIT bank record amounts |
| Category breakdown | `GROUP BY category` on bank_records |
| Payment status breakdown | `GROUP BY status` on payments |
| Settlement totals | `SUM(gross_amount)`, `SUM(net_amount)`, `SUM(total_fees)` |

**All values come from live PostgreSQL queries.** No mocked or hardcoded data is displayed.

---

## 20. File Upload Pipeline

The Upload page (`/upload`) accepts files and triggers the complete backend pipeline.

### Supported formats

CSV, XLSX, XLS, JSON, JSONL, PDF

### Pipeline execution

```
User selects file + source type
           │
POST /api/v1/upload/file  (multipart/form-data)
           │
   backend/app/api/routes/upload.py
           │
   1. Save to temporary location
   2. Detect/confirm source_type
   3. Parse (format-specific parser)
   4. Validate (schema, financial, duplicates)
   5. Normalise (field mapping, ID canonicalisation, type coercion)
   6. Upsert into PostgreSQL
   7. Run deterministic reconciliation on new records
   8. Run ML reconciliation on ambiguous cases
   9. Run exception classification on unmatched records
  10. Return summary: records_parsed, records_valid, records_loaded, reconciliation_results
           │
  Frontend displays progress and results summary
  Dashboard metrics refresh on next poll
```

**The frontend does not perform any financial processing.** All normalisation, validation, and reconciliation logic runs in the backend.

---

## 21. AI Chatbot

The Chat page (`/chat`) connects to the LLM agent via `POST /api/v1/chat/message`.

### Data flow

```
User types message in React chat UI
          │
POST /api/v1/chat/message
  { "message": "...", "reset_conversation": false }
          │
ReconciliationAgent.chat(message)
          │
  ┌── RAG retrieval (top-5 relevant chunks from docs/)
  │
  ├── PostgreSQL query (if message references a specific transaction ID)
  │
  └── Gemini LLM call (system prompt + context + message)
          │
ChatResponse { answer, sources, tools_used, confidence, metadata }
          │
React renders response with source citations
```

### Example questions

- `"Why is BNK_000123 unreconciled?"`
- `"What is UTR and how is it used in reconciliation?"`
- `"Show me the reconciliation result for settlement STL_000045"`
- `"What exception types does the system classify?"`
- `"How are GST records matched to invoices?"`
- `"Explain the settlement-to-bank reconciliation process"`

---

## 22. API Endpoints

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | System health (DB + ML models) |
| `GET` | `/api/v1/health` | Same as above, prefixed for frontend |

**Response:**
```json
{
  "status": "ok",
  "database": { "ok": true },
  "models": {
    "reconciliation_schema": true,
    "exception_schema": true,
    "reconciliation_model": true,
    "exception_model": true
  }
}
```

### Dashboard

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/dashboard/summary` | Real reconciliation metrics from PostgreSQL |

### Reconciliation

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/reconciliation/run` | Run full reconciliation pipeline for one record |

**Request:**
```json
{
  "source_type": "bank_record",
  "source_id": "BNK_000001",
  "include_ml": true,
  "include_exception": true
}
```

**Response:** `ReconciliationResult` with `match_method`, `matched_record`, `exception_class`, `confidence`, `evidence`.

### Transactions

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/transactions/{source_type}/{source_id}` | Fetch a single record from the database |

`source_type` accepts: `bank_record`, `payment`, `order`, `settlement`

### Chat

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/chat/message` | Send message to LLM agent |
| `POST` | `/api/v1/chat/reset` | Clear conversation history |
| `GET` | `/api/v1/chat/health` | LLM agent health check |

### Upload

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/upload/file` | Upload and process a financial file |
| `GET` | `/api/v1/upload/source-types` | List accepted source type identifiers |

---

## 23. Project Structure

```
razorpay-ai-finance-controller/
│
├── backend/                          # FastAPI Python backend
│   └── app/
│       ├── api/routes/               # HTTP route handlers
│       ├── core/                     # Config, logging
│       ├── database/                 # PostgreSQL connection + repositories
│       ├── ml/                       # ML model loader (inference only)
│       ├── rag/                      # RAG pipeline components
│       ├── llm/                      # Gemini agent + service
│       ├── schemas/                  # Pydantic/plain response schemas
│       ├── services/                 # Normalisation, reconciliation, orchestration
│       └── main.py                   # FastAPI app factory
│
├── frontend/                         # React + Vite frontend
│   ├── src/
│   │   ├── api.js                    # API client
│   │   ├── App.jsx                   # Router + layout
│   │   ├── components/Sidebar.jsx    # Navigation
│   │   └── pages/                    # Dashboard, Reconciliation, Transactions,
│   │                                 # Upload, Chat, Health
│   ├── package.json
│   └── vite.config.js
│
├── data/
│   ├── raw/
│   │   ├── synthetic/                # Clean generated source records
│   │   └── noisy/                    # Corrupted source records (used for DB load)
│   ├── ground_truth/                 # Reconciliation truth, exception truth
│   ├── normalized/                   # (populated by scripts/normalize_all.py)
│   └── rag_vector_db/                # ChromaDB vector store (populated by scripts/ingest_rag.py)
│
├── database/
│   └── schema/
│       └── schema.sql                # Complete PostgreSQL DDL
│
├── docs/                             # Domain documentation (ingested by RAG)
│   ├── FINANCIAL_RULES.md
│   ├── RECONCILIATION_RULES.md
│   ├── SCHEMA.md
│   └── DATA_GENERATION_SPEC.md
│
├── tools/
│   ├── data_generation/              # Synthetic data generation package
│   │   ├── generate_all.py
│   │   ├── generators/               # Per-entity generators
│   │   ├── corruption/               # Noise injection engines
│   │   └── config/                   # Generation config YAML
│   └── ML_Models/
│       ├── ML_Models_Code/           # Training notebooks (kept as technical record)
│       │   ├── Reconciliation_ML_Model.ipynb
│       │   └── Exception_Classification.ipynb
│       ├── Reconciliation Model/      # Trained reconciliation artifacts
│       ├── Exception Classification/  # Trained exception classifier artifacts
│       └── ML_data/                   # ML train/val/test splits
│
├── scripts/
│   ├── normalize_all.py              # Batch normalise all raw data
│   ├── load_canonical.py             # Load normalised data into PostgreSQL
│   ├── ingest_rag.py                 # Build ChromaDB vector store from docs/
│   ├── verify_runtime.py             # Runtime system verification
│   ├── audit_db.py                   # Database audit and integrity checks
│   ├── build_matching_v3_*.py        # ML dataset construction scripts
│   ├── feature_audit.py              # ML feature quality audit
│   ├── common.py                     # Shared script utilities
│   └── test_chatbot_manual.py        # Manual chatbot API test script
│
├── scratch/                          # Working files, traceability records
│   ├── check_db.py
│   ├── test_pipeline_steps.py
│   └── matching_v3/
│       └── ...candidate pair diagnostics...
│
├── tests/                            # pytest test suite
│   ├── api/                          # API endpoint tests
│   ├── llm/                          # LLM agent and service tests
│   ├── ml/                           # Model loading and inference tests
│   ├── normalization/                # Pipeline import tests
│   ├── rag/                          # RAG component tests
│   ├── reconciliation/               # Deterministic and ML reconciliation tests
│   ├── conftest.py
│   └── test_imports.py, test_security.py
│
├── .env.example                      # Environment variable template
├── .gitignore
├── pytest.ini                        # pytest configuration
├── requirements.txt                  # Python dependencies (complete, validated)
├── requirements-dev.txt              # Development-only extras
└── README.md                         # This file
```

---

## 24. Environment Variables

Copy `.env.example` to `.env` and fill in your values:

**Windows:**
```powershell
Copy-Item .env.example .env
```

**Linux/macOS:**
```bash
cp .env.example .env
```

### Required variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `razorpay_recon` | Database name |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | *(empty)* | **Required** — database password |
| `GEMINI_API_KEY` | *(empty)* | **Required** — Google AI Studio API key |

### Optional variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | *(none)* | Full DSN; overrides individual host/port/db/user/password |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model name |
| `ML_MODELS_DIR` | `tools/ML_Models` | Root directory for ML artifacts |
| `RECONCILIATION_MODEL_DIR` | `tools/ML_Models/Reconciliation Model` | Reconciliation model directory |
| `EXCEPTION_MODEL_DIR` | `tools/ML_Models/Exception Classification` | Exception classifier directory |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `RAG_DOCUMENTS_PATH` | `docs` | Directory containing Markdown documents for RAG |
| `RAG_VECTOR_DB_PATH` | `data/rag_vector_db` | ChromaDB persistence path |
| `RAG_CHUNK_SIZE` | `500` | Characters per RAG chunk |
| `RAG_CHUNK_OVERLAP` | `50` | Overlap between consecutive chunks |
| `RAG_TOP_K` | `5` | Number of retrieved chunks per query |
| `RAG_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer embedding model |
| `VITE_API_BASE_URL` | `/api/v1` | Frontend API base URL (Vite env) |

> **Never commit your `.env` file.** It is listed in `.gitignore`.

---

## 25. Installation

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- PostgreSQL 14+

### Python environment

```bash
# Create virtual environment
python -m venv .venv

# Activate — Windows PowerShell
.venv\Scripts\activate

# Activate — Linux/macOS
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### Frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## 26. PostgreSQL Setup

```bash
# 1. Install PostgreSQL (if not installed)
#    Windows: https://www.postgresql.org/download/windows/
#    Linux:   sudo apt install postgresql postgresql-contrib

# 2. Create the database
psql -U postgres -c "CREATE DATABASE razorpay_recon;"

# 3. Apply schema (tables, indexes, constraints)
psql -U postgres -d razorpay_recon -f database/schema/schema.sql

# 4. Configure credentials in .env
#    POSTGRES_PASSWORD=your_password_here

# 5. Verify connection
python scripts/audit_db.py
```

---

## 27. Data Generation & Loading

Run these commands once in order to populate the database:

```bash
# Step 1: Generate all synthetic data (reproducible, seed=42)
python tools/data_generation/generate_all.py

# Step 2: Normalise raw data into canonical form
python scripts/normalize_all.py

# Step 3: Load normalised data into PostgreSQL
python scripts/load_canonical.py

# Step 4 (optional): Audit database integrity
python scripts/audit_db.py
```

After these steps, the database will contain:
- 5 merchants, 500 customers, 2,000 orders, 2,000 payments
- 173 settlements, 547 bank records, 12,276 ledger entries
- Ground truth reconciliation and exception labels in `data/ground_truth/`

---

## 28. ML Training

> **Training is not required to run the application.**
> Pre-trained artifacts are already in `tools/ML_Models/`.

The ML notebooks in `tools/ML_Models/ML_Models_Code/` document the complete training workflow:

| Notebook | Task | Input | Output |
|---|---|---|---|
| `Reconciliation_ML_Model.ipynb` | Binary match classification | `ML_data/matching/*.csv` | `Reconciliation Model/*.joblib` |
| `Exception_Classification.ipynb` | 7-class exception classification | `ML_data/classification/*.csv` | `Exception Classification/*.joblib` |

### To retrain from scratch

1. Build ML datasets (requires loaded PostgreSQL):
   ```bash
   python scripts/build_matching_v3_candidates.py
   python scripts/build_matching_v3_features.py
   python scripts/build_matching_v3_finalize.py
   ```
2. Open the notebooks in Google Colab or Jupyter
3. Mount Google Drive or adjust file paths to point to `tools/ML_Models/ML_data/`
4. Run all cells — final models are saved as `.joblib`
5. Place the output `.joblib` files in the correct `tools/ML_Models/` subdirectories

> **ML training vs. ML inference**: Training runs in notebooks (one-time, offline). Inference runs in the backend at request time using the pre-trained artifacts.

---

## 29. RAG Ingestion

Build the ChromaDB vector store from the `docs/` directory:

```bash
# Initial ingestion
python scripts/ingest_rag.py

# Force rebuild if documentation has changed
python scripts/ingest_rag.py --force
```

This reads all Markdown files from `docs/`, chunks them, embeds them with `all-MiniLM-L6-v2`, and persists the vectors to `data/rag_vector_db/`.

RAG ingestion is a one-time setup step. The vector store is reused across backend restarts.

---

## 30. Complete First-Time Setup Sequence

For a fresh clone on a new machine, execute these one-time setup steps in order:

```bash
# 1. Initialize PostgreSQL database
psql -U postgres -c "CREATE DATABASE razorpay_recon;"
psql -U postgres -d razorpay_recon -f database/schema/schema.sql

# 2. Generate and load synthetic financial records
python tools/data_generation/generate_all.py
python scripts/normalize_all.py
python scripts/load_canonical.py

# 3. Build RAG ChromaDB knowledge vector store
python scripts/ingest_rag.py

# 4. Start servers
# Terminal 1 (Backend): python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# Terminal 2 (Frontend): cd frontend && npm run dev
```

---

## 31. Testing

### Python backend tests

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=backend

# Run specific subsystems
pytest tests/ml/
pytest tests/rag/
pytest tests/reconciliation/
pytest tests/api/
```

**Test suite coverage:**

| Module | Tests |
|---|---|
| `tests/api/` | Health, reconciliation, chat endpoints |
| `tests/ml/` | Model loading, real inference |
| `tests/rag/` | Chunker, embeddings, loaders, retriever, vector store, service |
| `tests/reconciliation/` | Deterministic rules, ML ranking, exception features, feature builder |
| `tests/llm/` | Agent, Gemini service, prompts |
| `tests/normalization/` | Pipeline import |
| `tests/test_imports.py` | Package import smoke test |
| `tests/test_security.py` | Secret protection checks |

**Total: 146 tests collected** (144 pass; 2 mock-format mismatches in `test_agent.py` pre-date this session).

### Runtime verification

```bash
# Verify all system components are healthy
python scripts/verify_runtime.py
```

### Frontend build verification

```bash
cd frontend
npm run build
```

---

## 32. System Health

The Health page (`/health`) polls `GET /health` and `GET /api/v1/chat/health`.

### What is checked

| Component | Check |
|---|---|
| **Backend** | HTTP 200 from `/health` |
| **PostgreSQL** | `ping_database()` — psycopg2 connection + `SELECT 1` |
| **Reconciliation model** | `artifact_status()` — `.joblib` file exists and schema loads |
| **Exception classifier** | Same as above |
| **RAG / Chat LLM** | `GET /api/v1/chat/health` — agent initialisation + RAG readiness |

**Status values:**
- `"ok"` — all components healthy
- `"degraded"` — backend running but DB or ML not ready

---

## 33. Security

| Concern | Implementation |
|---|---|
| Secrets in `.env` | `.env` is listed in `.gitignore`; never committed |
| No API keys in frontend | `GEMINI_API_KEY` is backend-only; never sent to the browser |
| No hardcoded secrets | All sensitive values are environment-driven |
| RAG excludes secret files | The RAG loader only indexes Markdown from `docs/`; `.env` is never indexed |
| No direct browser-to-DB | All database access is through the FastAPI backend |
| No direct browser-to-Gemini | All Gemini API calls are backend-only |
| LLM domain guardrails | System prompt restricts Gemini to reconciliation domain |
| Backend is financial truth | Frontend never performs financial calculations |

---

## 34. Limitations

### Synthetic data

All data is synthetically generated. Metrics, model performance, and reconciliation rates reflect synthetic patterns — not real-world Razorpay transaction volumes or complexity.

### Model performance on synthetic benchmark

All four ML models achieved near-perfect or perfect validation metrics on the synthetic dataset. This is **expected** — the synthetic data is generated from explicit rules, making the classification tasks learnable. Real-world performance would likely be lower due to:

- Unanticipated noisy patterns
- Edge cases not represented in the synthetic distribution
- Domain shift between synthetic and production data

### Local PostgreSQL requirement

The system requires a locally running PostgreSQL instance. There is no in-memory or cloud database fallback.

### Gemini API quota

The chat feature requires a valid `GEMINI_API_KEY`. On the free tier, there are requests-per-minute and requests-per-day limits. Under high load, the chat endpoint may return rate-limit errors.

### Exception classifier is called after ML

Exception classification is only invoked when both deterministic reconciliation and ML matching fail. If the ML model is not loaded (e.g. missing joblib), exception classification is also unavailable.

### No production hardening

This is a buildathon project. It lacks:
- Authentication and authorization
- Rate limiting on API endpoints
- Production WSGI server configuration (only Uvicorn dev mode is documented)
- Database connection pooling configuration for high concurrency
- Persistent session management for the chatbot

---

## 35. Demo Workflow

A complete end-to-end demonstration scenario:

**1. Start the system** (see [Section 30](#30-running-everything)):
```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# frontend: npm run dev
```

**2. Open the dashboard** at `http://localhost:5173`
- View total bank records, reconciliation rate, discrepancy amount
- See category breakdown and payment status distribution

**3. Inspect the health page** (`/health`)
- Confirm PostgreSQL ✓, Reconciliation Model ✓, Exception Classifier ✓

**4. Run a reconciliation** on the Reconciliation page (`/reconciliation`)
- Enter `source_type = bank_record`, `source_id = BNK_000001`
- Click Reconcile — observe match method (DETERMINISTIC or ML), confidence, matched settlement

**5. Ask the AI chatbot** (`/chat`)
- Type: `"Why is BNK_000001 matched to STL_000045?"`
- Receive an explanation citing reconciliation rules and RAG-retrieved domain context

**6. Look up a transaction** (`/transactions`)
- Enter `bank_record / BNK_000100` — view the raw record from the database

**7. Upload a new file** (`/upload`)
- Upload a CSV or XLSX bank record file
- Backend runs parse → validate → normalise → PostgreSQL → reconcile → ML → exception classify
- View the processing summary

**8. Refresh the dashboard**
- Observe updated counts reflecting the newly uploaded records

**9. Ask the AI about a result**
- `"What exception was found for the bank record I just uploaded?"`
- The agent queries the database, retrieves reconciliation context, and explains the result

---

## 36. Design Principles

| Layer | Role | Is Financial Truth? |
|---|---|---|
| **PostgreSQL** | Single source of financial data | ✅ Yes |
| **Deterministic reconciliation** | Authoritative, auditable rule-based matching | ✅ Yes (for matched records) |
| **ML (Logistic Regression)** | Ambiguity resolution for unmatched candidates | ⚠️ Probabilistic advisory |
| **RAG (ChromaDB + embeddings)** | Domain knowledge retrieval for context | ❌ No |
| **LLM (Gemini)** | Explanation and natural-language synthesis | ❌ No |
| **Frontend (React)** | Presentation, interaction, visualisation | ❌ No |

### Key principle

```
PostgreSQL → Deterministic → ML → (exception class)
                                           │
              RAG retrieves evidence ──────┤
                                           │
              Gemini synthesises ──────────┤
                                           ▼
                               User-facing explanation
```

The LLM is the **presentation layer for reasoning**, not the reasoning engine itself. Every financial conclusion can be traced back to a database record, a deterministic rule, or a trained ML model output.

---

*Razorpay AI Finance Controller — Track 4 Buildathon Submission*
