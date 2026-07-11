FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY src/ src/
COPY prompts/ prompts/
COPY scripts/ scripts/
COPY knowledge/ knowledge/
RUN python scripts/build_knowledge.py

CMD ["python", "main.py"]
