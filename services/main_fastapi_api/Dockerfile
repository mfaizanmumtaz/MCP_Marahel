#################################### Builder Stage
FROM python:3.13-alpine AS builder
WORKDIR /app

# Install build dependencies needed for compiling psutil and other packages
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    g++ \
    libffi-dev \
    openssl-dev \
    linux-headers \
    python3-dev

# Install uv
RUN pip install --no-cache-dir uv

COPY pyproject.toml .

# Install runtime dependencies first (needed by pymupdf, etc.)
RUN apk add --no-cache libstdc++

# Install Python dependencies
RUN uv sync

# Remove build dependencies to keep image small
RUN apk del .build-deps

#################################### Runtime Stage
FROM python:3.13-alpine
WORKDIR /app/src

# Install runtime libraries
RUN apk add --no-cache libstdc++

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# Copy application code
COPY ./src /app/src

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9696"]




# #################################### Builder Stage
# FROM python:3.13-alpine AS builder
# WORKDIR /app
# # Install build dependencies and uv
# RUN apk add --no-cache --virtual .build-deps \
#     gcc \
#     musl-dev \
#     g++ \
#     libffi-dev \
#     libstdc++ \
#     openssl-dev \
#     && pip install --no-cache-dir uv \
#     && apk del .build-deps
# COPY pyproject.toml .
# # Install requirements with uv
# RUN apk add --no-cache libstdc++

# RUN uv sync

# #################################### Runtime Stage
# FROM python:3.13-alpine
# WORKDIR /app/src
# # Copy only the necessary files from builder
# COPY --from=builder /app/.venv /app/.venv
# ENV PATH="/app/.venv/bin:${PATH}"
# # Copy application code
# COPY ./src /app/src
# # Run the application
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9696"]