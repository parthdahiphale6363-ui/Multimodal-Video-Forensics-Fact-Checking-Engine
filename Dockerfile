FROM python:3.12-slim

# Install system dependencies (including ffmpeg for media processing and curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source files
COPY . .

# Set Python Path & unbuffered output for real-time cloud logging
ENV PYTHONPATH=/app/backend:/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Run uvicorn server binding to Railway dynamic PORT environment variable
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
