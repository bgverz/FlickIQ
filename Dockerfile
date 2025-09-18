FROM python:3.11-slim

WORKDIR /app

# Copy only backend code into /app
COPY backend/ .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the FastAPI app
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
