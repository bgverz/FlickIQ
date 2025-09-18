FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Just run the main.py directly since it has uvicorn.run() in it
CMD ["python", "main.py"]
