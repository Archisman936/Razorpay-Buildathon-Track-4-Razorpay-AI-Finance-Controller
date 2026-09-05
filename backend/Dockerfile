# ==============================================================================
# Razorpay AI Finance Controller - Backend Dockerfile
# ==============================================================================
# Python 3.11 slim runtime for FastAPI, ML inference, and RAG service
# ==============================================================================

FROM python:3.11-slim

# Prevent python from buffering stdout/stderr and writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PROJECT_ROOT=/app

# Install minimal system utilities (curl for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition and install Python packages
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy backend application code
COPY backend/ ./backend/

# Copy ML model artifacts (Reconciliation & Exception Classification)
COPY tools/ML_Models/ ./tools/ML_Models/

# Copy knowledge base documentation for RAG vector search
COPY docs/ ./docs/

# Create data directory for RAG vector database & file uploads
RUN mkdir -p /app/data/rag_vector_db /app/data/uploads

# Configure application environment defaults
ENV RECONCILIATION_MODEL_DIR="/app/tools/ML_Models/Reconciliation Model" \
    EXCEPTION_MODEL_DIR="/app/tools/ML_Models/Exception Classification" \
    RECONCILIATION_MODEL_FILENAME="best_reconciliation_model.joblib" \
    EXCEPTION_MODEL_FILENAME="best_exception_classifier.joblib" \
    RAG_DOCUMENTS_PATH="/app/docs" \
    RAG_VECTOR_DB_PATH="/app/data/rag_vector_db" \
    PORT=8000

# Expose backend API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Start FastAPI application with Uvicorn (supports dynamic $PORT on Render, Cloud Run, etc.)
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
