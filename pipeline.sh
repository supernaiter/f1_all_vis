#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# F1 H2H Data Pipeline
# export_race_data.py → h2h_engine.py → (optional) site build
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

START_TIME=$(date +%s)

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
  ROUND      Round number 1-24 (e.g. 3)

Options:
  --force    Re-export even if race data already exists
  --build    Run site build after data generation
  --dry-run  Preview what steps would execute without running them
  --help     Show this help message

Examples:
  ./pipeline.sh 2026 Japan 3
  ./pipeline.sh 2026 Bahrain 4 --force
  ./pipeline.sh 2026 Saudi_Arabia 5 --build
  ./pipeline.sh 2026 Miami 6 --force --build
  ./pipeline.sh 2026 Japan 3 --dry-run --build

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

# --- Input validation ---
if ! [[ "$YEAR" =~ ^[0-9]{4}$ ]]; then
    echo -e "${RED}Error: YEAR must be a 4-digit number (got: '$YEAR')${NC}"
    exit 1
fi

if ! [[ "$ROUND" =~ ^[0-9]+$ ]] || [ "$ROUND" -lt 1 ] || [ "$ROUND" -gt 24 ]; then
    echo -e "${RED}Error: ROUND must be 1-24 (got: '$ROUND')${NC}"
    exit 1
fi

FORCE=false
BUILD=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)   FORCE=true ;;
        --build)   BUILD=true ;;
        --dry-run) DRY_RUN=true ;;
        --help)    usage; exit 0 ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; usage; exit 1 ;;
    esac
    shift
done

ROUND_PAD=$(printf "%02d" "$ROUND") || { echo -e "${RED}Error: Cannot zero-pad ROUND '$ROUND'${NC}"; exit 1; }
DATA_DIR="data/${YEAR}_R${ROUND_PAD}_${GP_NAME}"
EXPORT_DIR="${DATA_DIR}/export"
H2H_DIR="${DATA_DIR}/h2h"

# Dynamic step counter
TOTAL_STEPS=2
if [[ "$BUILD" == true ]]; then
    TOTAL_STEPS=3
fi
STEP=0

echo "================================================"
echo " F1 H2H Pipeline: ${YEAR} R${ROUND_PAD} ${GP_NAME}"
if [[ "$DRY_RUN" == true ]]; then
    echo " [DRY RUN MODE]"
fi
echo "================================================"
echo ""

# Step 1: Export race data
STEP=$((STEP + 1))
echo -e "${YELLOW}[${STEP}/${TOTAL_STEPS}] Race data export${NC}"

if [[ -f "${EXPORT_DIR}/race_laps.csv" && "$FORCE" == false ]]; then
    echo -e "${GREEN}  ✓ Export data already exists, skipping (use --force to re-export)${NC}"
else
    if [[ "$DRY_RUN" == true ]]; then
        echo "  [DRY RUN] Would run: uv run --with fastf1 --with pyarrow python export_race_data.py ${YEAR} ${GP_NAME} ${ROUND}"
        if [[ "$FORCE" == true && -f "${EXPORT_DIR}/race_laps.csv" ]]; then
            echo "  [DRY RUN] Would remove existing export data first"
        fi
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
fi

echo ""

# Step 2: H2H analysis
STEP=$((STEP + 1))
echo -e "${YELLOW}[${STEP}/${TOTAL_STEPS}] H2H analysis (--top10)${NC}"

if [[ -f "${H2H_DIR}/index.json" && "$FORCE" == false ]]; then
    echo -e "${GREEN}  ✓ H2H data already exists, skipping (use --force to regenerate)${NC}"
else
    if [[ "$DRY_RUN" == true ]]; then
        echo "  [DRY RUN] Would run: /usr/bin/python3 h2h_engine.py ${YEAR} ${GP_NAME} ${ROUND} --top10"
        if [[ "$FORCE" == true && -d "${H2H_DIR}" ]]; then
            echo "  [DRY RUN] Would use atomic swap (temp dir → rename on success)"
        fi
    else
        if [[ "$FORCE" == true && -d "${H2H_DIR}" ]]; then
            # Atomic swap: backup existing, regenerate, swap on success
            H2H_BACKUP="${H2H_DIR}.backup.$$"
            echo "  Backing up existing H2H data to ${H2H_BACKUP}..."
            mv "${H2H_DIR}" "${H2H_BACKUP}"
        fi
        echo "  Running: /usr/bin/python3 h2h_engine.py ${YEAR} ${GP_NAME} ${ROUND} --top10"
        if ! /usr/bin/python3 h2h_engine.py "$YEAR" "$GP_NAME" "$ROUND" --top10; then
            echo -e "${RED}  ✗ H2H generation failed.${NC}"
            if [[ -n "${H2H_BACKUP:-}" && -d "${H2H_BACKUP}" ]]; then
                echo "  Restoring previous H2H data from backup..."
                mv "${H2H_BACKUP}" "${H2H_DIR}"
                echo -e "${YELLOW}  ⚠ Previous data restored. No data lost.${NC}"
            fi
            exit 1
        fi
        # Clean up backup on success
        if [[ -n "${H2H_BACKUP:-}" && -d "${H2H_BACKUP}" ]]; then
            rm -rf "${H2H_BACKUP}"
        fi
        echo -e "${GREEN}  ✓ H2H analysis complete${NC}"
    fi
fi

echo ""

# Step 3: Site build (optional)
if [[ "$BUILD" == true ]]; then
    STEP=$((STEP + 1))
    echo -e "${YELLOW}[${STEP}/${TOTAL_STEPS}] Site build${NC}"
    if [[ "$DRY_RUN" == true ]]; then
        echo "  [DRY RUN] Would run: cd site && npm run build"
    else
        if ! (cd site && npm run build); then
            echo -e "${RED}  ✗ Site build failed.${NC}"
            exit 1
        fi
        echo -e "${GREEN}  ✓ Site build complete${NC}"
    fi
    echo ""
fi

# Summary
END_TIME=$(date +%s)
ELAPSED=$(( END_TIME - START_TIME ))
ELAPSED_MIN=$(( ELAPSED / 60 ))
ELAPSED_SEC=$(( ELAPSED % 60 ))

echo "================================================"
echo -e "${GREEN} Pipeline complete${NC} (${ELAPSED_MIN}m${ELAPSED_SEC}s)"
echo "  Export: ${EXPORT_DIR}/"
echo "  H2H:   ${H2H_DIR}/"
if [[ "$BUILD" == true ]]; then
    echo "  Site:   site/dist/"
fi
# Show H2H pair count if available
if [[ -f "${H2H_DIR}/index.json" ]]; then
    PAIR_COUNT=$(python3 -c "import json; print(len(json.load(open('${H2H_DIR}/index.json'))['pairs']))" 2>/dev/null || echo "?")
    echo "  Pairs:  ${PAIR_COUNT}"
fi
echo "================================================"
