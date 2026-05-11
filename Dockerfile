FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ \
        fasttree \
        clustalw \
        mafft \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# FastTree binary: aphylogeo looks for "aphylogeo/bin/FastTree" relative to CWD.
# Since CWD at runtime is /app (the backend root), create it here.
RUN mkdir -p /app/aphylogeo/bin && \
    ln -sf "$(which fasttree)" /app/aphylogeo/bin/FastTree

# ── Application source ────────────────────────────────────────────────────────
# Copied here so the image works standalone. In development the docker-compose
# volume mount overlays this with the live source for hot-reload.
COPY . .
