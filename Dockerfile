FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for FPDF2 and networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install dependencies using pip (from pyproject.toml)
RUN pip install .

# Create data directory for volume mounting
RUN mkdir /data

ENV CONFIG_PATH=/data/config.yaml
ENV PYTHONPATH=/app

# Expose port (overridden by env vars in app)
EXPOSE 8000

CMD ["python", "-m", "home_financial_tools.server.main"]
