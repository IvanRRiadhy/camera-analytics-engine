# Dockerfile for Python AI Camera Analytics Engine

FROM python:3.11-slim

# Install system dependencies (OpenCV, FFmpeg, GL dependencies)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirement list or requirements if available (or install core packages)
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    ultralytics \
    opencv-python-headless \
    paho-mqtt \
    numpy

# Copy python engine code
COPY . /app/camera_analytics/

ENV PYTHONPATH=/app

CMD ["python", "-m", "camera_analytics.demo"]
