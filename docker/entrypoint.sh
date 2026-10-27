#!/usr/bin/env bash
# ==============================================================================
# CCTV Analytics AI Engine - Container Entrypoint Script
# Handles runtime pre-flight verification, folder setup, and engine execution
# ==============================================================================
set -e

echo "================================================================================"
echo "         CCTV ANALYTICS AI ENGINE - DOCKER CONTAINER RUNTIME                    "
echo "================================================================================"
echo " App Version    : ${AIENGINE_VERSION:-2.2.1}"
echo " Environment    : ${TARGET_ENVIRONMENT:-WIN_X64}"
echo " Python Version : $(python3 --version 2>&1)"
echo " Working Dir    : $(pwd)"
echo "================================================================================"

# 1. Ensure required runtime volume directories exist and are writable
for wdir in logs cache runtime output recordings exports configs; do
    if [ ! -d "$wdir" ]; then
        echo "[+] Creating volume directory: $wdir"
        mkdir -p "$wdir"
    fi
done

# 2. Execute Pre-Flight Distribution Audit & Verification
if [ "$1" == "--verify" ] || [ "$HEALTHCHECK_MODE" == "1" ]; then
    echo "[+] Running Pre-Flight Verification Audit..."
    python3 -m camera_analytics.main --verify
    exit $?
fi

# 3. Check for Self-Test Mode
if [ "$1" == "--self-test" ]; then
    echo "[+] Executing System Self-Test Diagnostic Suite..."
    python3 -m camera_analytics.main --self-test
    exit $?
fi

# 4. Check for Benchmark Mode
if [ "$1" == "--benchmark" ]; then
    echo "[+] Executing Automated Runtime Benchmark..."
    python3 -m camera_analytics.main --benchmark
    exit $?
fi

# 5. Default: Launch Standalone/Enterprise AI Engine in Headless Mode
echo "[+] Launching AI Engine Daemon in Headless Mode..."
exec python3 -m camera_analytics.main --standalone --config-file configs/standalone.json --headless "$@"
