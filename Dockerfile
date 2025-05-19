FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for Playwright)
RUN wget -qO- https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps

# Copy the rest of the application
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV BATCH_INDEX=0
ENV BATCH_SIZE=10000
ENV SEQUENTIAL=false
ENV OLLAMA_HOST=http://159.203.3.54

# Run the script
CMD ["python", "scraper_groq.py"] 