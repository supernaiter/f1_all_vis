#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# F1 H2H Data Pipeline
# export_race_data.py → h2h_engine.py → (optional) site build
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    cat <<'USAGE'
Usage: ./pipeline.sh <YEAR> <GP_NAME> <ROUND> [OPTIONS]

Arguments:
  YEAR       Season year (e.g. 2026)
  GP_NAME    GP name as used by FastF1 (e.g. Japan, Bahrain, Saudi_Arabia, Miami)
  ROUND      Round number (e.g. 3)

Options:
  --force    Re-export even if race data already exists
  --build    Run site build after data generation
  --help     Show this help message

Examples:
  ./pipeline.sh 2026 Japan 3
  ./pipeline.sh 2026 Bahrain 4 --force
  ./pipeline.sh 2026 Saudi_Arabia 5 --build
  ./pipeline.sh 2026 Miami 6 --force --build

Pipeline steps:
  1. Export race data (FastF1 via uv run)
  2. Generate H2H analysis (top 10, /usr/bin/python3)
  3. (Optional) Build Astro site
USAGE
}

# Parse args
if [[ $# -lt 1 ]]; then
    usage
    exit 1
fi

if [[ "$1" == "--help" ]]; then
    usage
    exit 0
fi

if [[ $# -lt 3 ]]; then
    usage
    exit 1
fi

YEAR="$1"
GP_NAME="$2"
ROUND="$3"
shift 3

FORCE=false
BUILD=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force) FORCE=true ;;
        --build) BUILD=true ;;
        --help)  usage; exit 0 ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; usage; exit 1 ;;
    esac
    shift
done

ROUND_PAD=$(printf "%02d" "$ROUND")
DATA_DIR="data/${YEAR}_R${ROUND_PAD}_${GP_NAME}"
EXPORT_DIR="${DATA_DIR}/export"
H2H_DIR="${DATA_DIR}/h2h"

echo "================================================"
echo " F1 H2H Pipeline: ${YEAR} R${ROUND_PAD} ${GP_NAME}"
echo "================================================"
echo ""

# Step 1: Export race data
echo -e "${YELLOW}[1/2] Race data export${NC}"

if [[ -f "${EXPORT_DIR}/race_laps.csv" && "$FORCE" == false ]]; then
    echo -e "${GREEN}  ✓ Export data already exists, skipping (use --force to re-export)${NC}"
else
    if [[ "$FORCE" == true && -f "${EXPORT_DIR}/race_laps.csv" ]]; then
        echo "  Removing existing export data..."
        rm -f "${EXPORT_DIR}/race_laps.csv" \
              "${EXPORT_DIR}/race_laps.parquet" \
              "${EXPORT_DIR}/race_results.csv" \
              "${EXPORT_DIR}/race_control_messages.csv" \
              "${EXPORT_DIR}/race_weather.csv" \
              "${EXPORT_DIR}/manifest.json" \
              "${EXPORT_DIR}/README.md"
    fi
    echo "  Running: uv run --with fastf1 --with pyarrow python export_race_data.py ${YEAR} ${GP_NAME} ${ROUND}"
    if ! uv run --with fastf1 --with pyarrow python export_race_data.py "$YEAR" "$GP_NAME" "$ROUND"; then
        echo -e "${RED}  ✗ Export failed. Stopping pipeline.${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ Export complete${NC}"
fi

echo ""

# Step 2: H2H analysis
echo -e "${YELLOW}[2/2] H2H analysis (--top10)${NC}"

if [[ -f "${H2H_DIR}/index.json" && "$FORCE" == false ]]; then
    echo -e "${GREEN}  ✓ H2H data already exists, skipping (use --force to regenerate)${NC}"
else
    if [[ "$FORCE" == true && -d "${H2H_DIR}" ]]; then
        echo "  Removing existing H2H data..."
        rm -rf "${H2H_DIR}"
    fi
    echo "  Running: /usr/bin/python3 h2h_engine.py ${YEAR} ${GP_NAME} ${ROUND} --top10"
    if ! /usr/bin/python3 h2h_engine.py "$YEAR" "$GP_NAME" "$ROUND" --top10; then
        echo -e "${RED}  ✗ H2H generation failed. Stopping pipeline.${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ H2H analysis complete${NC}"
fi

echo ""

# Step 3: Site build (optional)
if [[ "$BUILD" == true ]]; then
    echo -e "${YELLOW}[3/3] Site build${NC}"
    if ! (cd site && npm run build); then
        echo -e "${RED}  ✗ Site build failed.${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ Site build complete${NC}"
    echo ""
fi

# Summary
echo "================================================"
echo -e "${GREEN} Pipeline complete${NC}"
echo "  Export: ${EXPORT_DIR}/"
echo "  H2H:   ${H2H_DIR}/"
if [[ "$BUILD" == true ]]; then
    echo "  Site:   site/dist/"
fi
echo "================================================"
