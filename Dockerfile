# ── Stage 1: Base image ────────────────────────────────────────────────
# Start from an official Python image. "slim" means minimal OS packages
# (no GUI, no dev tools we don't need), keeping the image small (~150MB
# base vs ~900MB for the full image).
FROM python:3.12-slim

# ── Stage 2: System-level setup ───────────────────────────────────────
# Set the working directory inside the container. All subsequent commands
# (COPY, RUN, CMD) operate relative to this path.
WORKDIR /app

# Don't write .pyc files (unnecessary in a container) and don't buffer
# Python's stdout/stderr (so logs appear immediately in `docker logs`).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ── Stage 3: Install Python dependencies ──────────────────────────────
# Copy ONLY requirements.txt first. Docker caches each step ("layer"),
# so if requirements.txt hasn't changed, Docker skips this step on
# rebuild — even if your code changed. This makes rebuilds fast.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 4: Copy application code ───────────────────────────────────
# Now copy the rest of the project. This layer is rebuilt whenever any
# code file changes, but the dependency layer above is cached.
COPY . .

# ── Stage 5: Expose the port ─────────────────────────────────────────
# Streamlit runs on port 8501 by default. EXPOSE documents this but
# doesn't actually open the port — that happens at `docker run` time.
EXPOSE 8501

# ── Stage 6: Health check ────────────────────────────────────────────
# Docker can periodically check if the app is responsive. If this fails
# repeatedly, orchestrators (like Docker Compose or Kubernetes) can
# restart the container automatically.
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# ── Stage 7: Run the app ─────────────────────────────────────────────
# CMD is the default command when someone runs `docker run`.
# Streamlit flags:
#   --server.port=8501        explicit port
#   --server.address=0.0.0.0  listen on all interfaces (required in Docker)
#   --server.headless=true    don't try to open a browser
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
