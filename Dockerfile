FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir fastapi uvicorn pydantic pyyaml openai httpx python-dotenv

COPY . .

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "7860"]