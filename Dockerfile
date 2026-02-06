FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .
COPY templates/ ./templates/
COPY static/ ./static/

# Create plugins directory
RUN mkdir -p /app/plugins

# Expose port
EXPOSE 8000

# Run server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
