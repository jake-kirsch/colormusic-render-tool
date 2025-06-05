FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libxml2 libzip4 \
    build-essential unzip fontconfig fontconfig-config libglib2.0-0 libfreetype6 libfontconfig1 \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libgtk-3-0 \
    libasound2 libxshmfence1 libxss1 fonts-liberation \
    libappindicator3-1 xdg-utils wget ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium
RUN playwright install chromium

# Download and install Verovio CLI
RUN wget https://github.com/rism-ch/verovio/releases/download/5.2.0/verovio-app-x86_64-linux.zip \
    && unzip verovio-app-x86_64-linux.zip -d /opt/verovio \
    && chmod +x /opt/verovio/verovio

# Add verovio to PATH
ENV PATH="/opt/verovio:${PATH}"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]