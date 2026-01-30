FROM python:3.11-slim

WORKDIR /app

# Install system dependencies that might be needed for building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 8080
EXPOSE 8080

# Run the application
# We run main.py directly because the app creation and uvicorn run logic is in __main__
CMD ["python", "main.py"]
