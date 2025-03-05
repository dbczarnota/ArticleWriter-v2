# FROM unclecode/crawl4ai:all-amd64
FROM mcr.microsoft.com/playwright:v1.50.1-noble


# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.
COPY . /app

# Install the application dependencies.
WORKDIR /app
RUN uv venv
RUN uv sync --frozen --no-cache

# RUN playwright install

# Run the application.
CMD ["/app/.venv/bin/fastapi", "run", "app/server.py", "--port", "80", "--host", "0.0.0.0"]