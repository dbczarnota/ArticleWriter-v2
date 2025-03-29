

powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

uv self update

playwright install


uv run fastapi dev  app/server.py