FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    build-essential unzip fontconfig libglib2.0-0 libfreetype6 libfontconfig1 \
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


# Download and install Bravura font (SMuFL)
RUN wget https://www.smufl.org/files/bravura-1.392.zip -O /tmp/bravura.zip && \
    unzip /tmp/bravura.zip -d /usr/share/fonts/bravura && \
    fc-cache -fv

# Download and install Leipzig font (adjust URL if needed)
RUN wget https://github.com/LeipzigMusic/XML-Fonts/archive/refs/heads/master.zip -O /tmp/leipzig.zip && \
    unzip /tmp/leipzig.zip -d /usr/share/fonts/leipzig && \
    fc-cache -fv


COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]