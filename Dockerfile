# syntax=docker/dockerfile:1
FROM python:3.11-slim

LABEL maintainer="VeriFace Protocol Team"
LABEL description="Production container environment for Face ID + Blockchain Re-Verification Pipeline"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies required for OpenCV and native bindings
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install pinned Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project source code, models, and assets
COPY . .

# Ensure model files and sample images are present
RUN test -f models/yunet.onnx && test -f models/sface.onnx

# Default entrypoint runs the verifiable pipeline
ENTRYPOINT ["python", "pipeline.py"]
CMD ["--demo-mode", "--consent-confirmed", "--image", "sample_images/query_face.jpg"]
