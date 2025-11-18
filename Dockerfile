FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# System dependencies
RUN apt-get update && apt-get install -y build-essential gcc && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /code/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application code
COPY . /code

# Make all run scripts executable
RUN chmod +x /code/run_web.sh /code/run_worker.sh /code/run_web_with_worker.sh

# Create upload directory (not used on Render, but kept for local dev)
RUN mkdir -p /data/uploads

EXPOSE 8000

# Use the combined script for Render (web + worker in same container)
# For local development with docker-compose, this will be overridden
CMD ["./run_web_with_worker.sh"]
