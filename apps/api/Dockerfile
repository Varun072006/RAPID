FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy manifest and source files needed for package installation
COPY pyproject.toml README.md ./
COPY packages/ ./packages/
COPY apps/api/ ./apps/api/

# Install dependencies and rapid package
RUN uv pip install --system --no-cache -e .

EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
