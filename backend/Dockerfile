FROM python:3.11-slim

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy the requirements from backend/
COPY backend/requirements.txt /code/requirements.txt

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /code/requirements.txt

# Copy the entire 'backend' folder, preserving its structure
COPY backend /code/backend

# Make sure this points to the correct module path in your code
CMD ["uvicorn", "backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
