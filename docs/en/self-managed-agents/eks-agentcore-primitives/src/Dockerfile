# AgentCore requires linux/arm64
FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

# System certs for TLS to AWS endpoints
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright driver for the AgentCore Browser tool. The browser itself runs
# remotely on AgentCore; Playwright connects to it over CDP, so we install the
# chromium driver + its system deps here.
RUN playwright install --with-deps chromium

COPY app.py .

# The AgentCore contract: serve on 8080
EXPOSE 8080

# Run the harness (serves /invocations + /ping)
CMD ["python", "app.py"]
