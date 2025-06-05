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

# # Download and extract the .tar.gz source
# WORKDIR /opt
# RUN curl -L -o verovio.tar.gz https://github.com/rism-digital/verovio/archive/refs/tags/version-5.2.0.tar.gz && \
#     tar -xzf verovio.tar.gz && \
#     rm verovio.tar.gz

# # Build the source
# WORKDIR /opt/verovio-version-5.2.0/build
# RUN cmake ../cmake && make -j"$(nproc)"

# # Install CLI globally
# RUN cp /opt/verovio-version-5.2.0/build/tools/verovio /usr/local/bin/verovio
# ENV PATH="/usr/local/bin:$PATH"

# # Optional: test
# RUN verovio --version

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]