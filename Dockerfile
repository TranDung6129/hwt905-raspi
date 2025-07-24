# Stage 1: Build on ARM
FROM arm32v7/python:3.11-slim-bullseye as builder

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    gfortran \
    libatlas-base-dev \
    liblapack-dev \
    libblas-dev \
    libopenblas-dev \
    cmake \
    pkg-config \
    git \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel \
    && pip install --prefix=/install -r requirements.txt

# Stage 2: Final image
FROM arm32v7/python:3.11-slim-bullseye

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . .

CMD ["python", "main.py"]
