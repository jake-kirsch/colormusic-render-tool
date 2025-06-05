FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libxml2 libzip4 \
    build-essential unzip fontconfig fontconfig-config libglib2.0-0 libfreetype6 libfontconfig1 \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libgtk-3-0 \
    libasound2 libxshmfence1 libxss1 fonts-liberation \
    libappindicator3-1 xdg-utils wget ca-certificates \
    git \
    cmake \
    g++ \
    make \
    libglib2.0-dev \
    libxml2-dev \
    libzip-dev \
    curl \
    unzip \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium
RUN playwright install chromium

# Clone the repo with all submodules and checkout version 5.2.0
WORKDIR /opt
RUN git clone --recursive https://github.com/rism-digital/verovio.git \
    && cd verovio \
    && git checkout version-5.2.0 \
    && git submodule update --init --recursive

# Build Verovio
WORKDIR /opt/verovio
RUN mkdir build
WORKDIR /opt/verovio/build
RUN cmake .. && make -j"$(nproc)"

# Move CLI to system path
RUN cp /opt/verovio/build/tools/verovio /usr/local/bin/verovio
ENV PATH="/usr/local/bin:$PATH"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]