FROM python:3.11-slim

WORKDIR /workspace

RUN apt-get update && apt-get install -y gcc build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /workspace/backend/
COPY frontend/ /workspace/frontend/

EXPOSE 8000
EXPOSE 9999

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
