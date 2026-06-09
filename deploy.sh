#!/usr/bin/env bash

# ==============================================================================
# D&D DISCORD BOT INFRASTRUCTURE LAUNCH ENGINE
# ==============================================================================
# -e: Exit immediately if any command returns a non-zero exit status.
# -u: Treat unset variables as an error and exit immediately.
# -o pipefail: Fail a pipeline if any single command within it fails.
set -euo pipefail

# Define visual text logging anchors
INFO="[\033[0;34m INFO \033[0m]"
SUCCESS="[\033[0;32m SUCCESS \033[0m]"
ERROR="[\033[0;31m ERROR \033[0m]"

echo -e "${INFO} Commencing production deployment pipeline initialization..."

# 1. Operational Sanity Check: Ensure required local hidden file configurations exist
if [ ! -f ".env" ]; then
    echo -e "${ERROR} Critical Configuration Missing: '.env' file not found in root directory!" >&2
    echo -e "         Please create a '.env' file populated with your target token keys." >&2
    exit 1
fi

# 2. Network Bridge Provisioning
# Check if the external shared docker bridge network already exists before trying to forge it
SHARED_NET="dnd_shared_network"
if ! docker network inspect "$SHARED_NET" >/dev/null 2>&1; then
    echo -e "${INFO} Internal network bridge '${SHARED_NET}' not detected. Creating node..."
    docker network create "$SHARED_NET"
    echo -e "${SUCCESS} Virtual private bridge network node secured."
else
    echo -e "${INFO} Verified: Shared internal network node '${SHARED_NET}' is online and available."
fi

# 3. Cache Purging & Container Tear-Down (Ensures a hot deployment handles code changes cleanly)
echo -e "${INFO} Sweeping out obsolete system runtime footprint images..."
# Shuts down current running bot container layers if they exist, leaving data volumes unbothered
docker compose down --remove-orphans || true

# 4. Atomic Code Build and Detached Launch Phase
echo -e "${INFO} Executing Python Docker image compilation layers..."
# --build: Forces Docker to re-evaluate requirements.txt and bake your new src cogs
# -d: Detaches the container process so it runs silently as a background system daemon
docker compose up -d --build

echo -e "========================================================================="
echo -e "${SUCCESS} DEPLOYMENT COMPLETED! D&D bot ecosystem is active in detached daemon space."
echo -e "========================================================================="

# 5. Live Runtime Log Streaming Verification
echo -e "${INFO} Attaching to system stdout log arrays. Press [Ctrl + C] safely to disconnect."
echo -e "-------------------------------------------------------------------------"
sleep 2 # Brief pause to allow the container initialization threads to warm up
docker compose logs -f discord_bot
