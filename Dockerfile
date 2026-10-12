FROM python:3.12-slim

# Install system dependencies (including ffmpeg for media processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source files
COPY . .

# Set Python Path
ENV PYTHONPATH=/app/backend:/app

EXPOSE 8000

# Run the app
CMD ["python", "backend/main.py"]
