FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for Playwright)
RUN wget -qO- https://deb.nodesource.com/setup_16.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SUPABASE_URL=""
ENV SUPABASE_KEY=""
ENV BROWSER_WS=""
ENV BATCH_INDEX=0
ENV BATCH_SIZE=25

# Verify environment variables are set
RUN echo "Checking environment variables:" && \
    echo "SUPABASE_URL is set: $([ ! -z "$SUPABASE_URL" ] && echo 'yes' || echo 'no')" && \
    echo "SUPABASE_KEY is set: $([ ! -z "$SUPABASE_KEY" ] && echo 'yes' || echo 'no')" && \
    echo "BROWSER_WS is set: $([ ! -z "$BROWSER_WS" ] && echo 'yes' || echo 'no')"

# Command to run the scraper
CMD ["python", "scraper_groq.py"] 