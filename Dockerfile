FROM python:3.11-slim

WORKDIR /app

# System deps (no fonts copying here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    libfreetype6-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    zlib1g-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]