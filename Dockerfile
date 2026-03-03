# Novel Audiobook Generator

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt requirements-dev.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY generate_audiobook.py webui.py ./
COPY config.example.yaml ./

# Create output directory
RUN mkdir -p output samples

# Install the package
RUN pip install -e .

# Expose port for web UI
EXPOSE 7860

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV GRADIO_SERVER_NAME=0.0.0.0

# Default command (can be overridden)
CMD ["python", "webui.py"]
