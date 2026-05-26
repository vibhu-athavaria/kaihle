#!/usr/bin/env bash
# =============================================================================
# db_prod_to_dev.sh
#
# Exports production DB data → imports into local dev DB → resets all passwords
# to 'test1234!' (bcrypt hash).
#
# Usage:
#   ./scripts/db_prod_to_dev.sh --prod-url "postgresql://user:pass@host:5432/db"
#
# Or set PROD_DATABASE_URL in your environment / .env file:
#   PROD_DATABASE_URL=postgresql://... ./scripts/db_prod_to_dev.sh
#
# The local dev DB is read from .env (DATABASE_URL) and defaults to:
#   postgresql://kaihle:kaihle@localhost:5433/kaihle
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Defaults ─────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DUMP_FILE="${TMPDIR:-/tmp}/kaihle_prod_dump_$(date +%Y%m%d_%H%M%S).dump"

# Dev DB defaults (overridden by .env or --dev-url)
DEV_HOST="localhost"
DEV_PORT="5433"
DEV_USER="kaihle"
DEV_PASSWORD="kaihle"
DEV_DB="kaihle"

# bcrypt hash of 'test1234!'
# Generated with: python3 -c "from passlib.hash import bcrypt; print(bcrypt.hash('test1234!'))"
# Value is stable — bcrypt is deterministic given the same salt, but verify works with any salt.
# We generate fresh at runtime so we don't embed a stale hash in the script.
TEST_PASSWORD="test1234!"

# ── Parse args ───────────────────────────────────────────────────────────────
PROD_URL="${PROD_DATABASE_URL:-}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --prod-url)  PROD_URL="$2"; shift 2 ;;
    --dev-url)   DEV_OVERRIDE_URL="$2"; shift 2 ;;
    --dump-file) DUMP_FILE="$2"; shift 2 ;;
    --help|-h)
      sed -n '/^# Usage/,/^# =/p' "$0" | head -n -1
      exit 0
      ;;
    *) log_error "Unknown argument: $1"; exit 1 ;;
  esac
done

# ── Load .env if present ─────────────────────────────────────────────────────
ENV_FILE="$PROJECT_ROOT/.env"
if [[ -f "$ENV_FILE" ]]; then
  log_info "Loading $ENV_FILE"
  # Export only DATABASE_URL and PROD_DATABASE_URL lines, safely
  set -o allexport
  # shellcheck disable=SC1090
  source <(grep -E '^(DATABASE_URL|PROD_DATABASE_URL)=' "$ENV_FILE" | sed 's/[[:space:]]*#.*//')
  set +o allexport
fi

# Re-check after .env load
PROD_URL="${PROD_URL:-${PROD_DATABASE_URL:-}}"

# ── Validate prod URL ─────────────────────────────────────────────────────────
if [[ -z "$PROD_URL" ]]; then
  log_error "Production DATABASE_URL not provided."
  log_error "Set PROD_DATABASE_URL in .env, or pass --prod-url <url>"
  exit 1
fi

# ── Parse dev DB connection ───────────────────────────────────────────────────
# Supports overriding the full URL or using docker-compose defaults.
if [[ -n "${DEV_OVERRIDE_URL:-}" ]]; then
  DEV_CONN_URL="$DEV_OVERRIDE_URL"
else
  # Strip asyncpg driver prefix if present (psql/pg_restore need plain postgresql://)
  LOCAL_URL="${DATABASE_URL:-postgresql://kaihle:kaihle@localhost:5433/kaihle}"
  DEV_CONN_URL="${LOCAL_URL/postgresql+asyncpg:\/\//postgresql://}"
fi

# ── Prerequisite checks ───────────────────────────────────────────────────────
check_command() {
  if ! command -v "$1" &>/dev/null; then
    log_error "'$1' not found. Install postgresql client tools: brew install libpq"
    exit 1
  fi
}

check_command pg_dump
check_command pg_restore
check_command psql

# Check Python + passlib for hash generation
if ! python3 -c "from passlib.hash import bcrypt" 2>/dev/null; then
  log_error "passlib not available. Run: cd backend && uv sync --all-extras"
  exit 1
fi

# ── Confirm before proceeding ─────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  PRODUCTION → DEV database sync                         ║${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Prod source : ${RED}${PROD_URL//:*@/:***@}${NC}"
echo -e "  Dev target  : ${GREEN}${DEV_CONN_URL//:*@/:***@}${NC}"
echo -e "  Dump file   : $DUMP_FILE"
echo -e "  Passwords   : all users → '${TEST_PASSWORD}'"
echo ""
echo -e "${RED}⚠  This will DROP and recreate the local dev database.${NC}"
read -rp "  Type 'yes' to continue: " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
  log_warn "Aborted."
  exit 0
fi
echo ""

# ── Step 1: Dump production ───────────────────────────────────────────────────
log_info "Step 1/4 — Dumping production database..."

# Use --no-owner --no-acl so we don't need superuser on restore
pg_dump \
  --format=custom \
  --no-owner \
  --no-acl \
  --no-privileges \
  --exclude-table-data="celery*" \
  "$PROD_URL" \
  --file="$DUMP_FILE"

DUMP_SIZE=$(du -sh "$DUMP_FILE" | cut -f1)
log_success "Dump complete: $DUMP_FILE ($DUMP_SIZE)"

# ── Step 2: Drop & recreate local dev DB ─────────────────────────────────────
log_info "Step 2/4 — Recreating local dev database..."

# Connect to 'postgres' maintenance DB to drop/create
MAINTENANCE_URL="${DEV_CONN_URL%/*}/postgres"

psql "$MAINTENANCE_URL" <<-SQL
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = '${DEV_DB}'
    AND pid <> pg_backend_pid();

  DROP DATABASE IF EXISTS "${DEV_DB}";
  CREATE DATABASE "${DEV_DB}" OWNER "${DEV_USER}";
SQL

# Re-enable pgvector extension (required by the schema)
psql "$DEV_CONN_URL" <<-SQL
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
SQL

log_success "Dev database recreated."

# ── Step 3: Restore dump ──────────────────────────────────────────────────────
log_info "Step 3/4 — Restoring dump into dev database..."

pg_restore \
  --no-owner \
  --no-acl \
  --no-privileges \
  --exit-on-error \
  --dbname="$DEV_CONN_URL" \
  "$DUMP_FILE"

log_success "Restore complete."

# ── Step 4: Reset all passwords to test1234! ──────────────────────────────────
log_info "Step 4/4 — Hashing test password and resetting all user passwords..."

# Generate fresh bcrypt hash at runtime
HASHED_PW=$(python3 -c "
from passlib.hash import bcrypt
print(bcrypt.hash('${TEST_PASSWORD}'))
")

UPDATED=$(psql "$DEV_CONN_URL" --tuples-only --no-align <<-SQL
  UPDATE users
  SET hashed_password = '${HASHED_PW}'
  WHERE hashed_password IS NOT NULL;
  SELECT COUNT(*) FROM users WHERE hashed_password IS NOT NULL;
SQL
)

log_success "Password reset for ${UPDATED// /} users → '${TEST_PASSWORD}'"

# ── Cleanup ────────────────────────────────────────────────────────────────────
rm -f "$DUMP_FILE"
log_success "Temp dump file removed."

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Done! Dev DB is ready.                                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  All users can now log in with password: ${YELLOW}${TEST_PASSWORD}${NC}"
echo -e "  Magic-link flows still work (tokens generated fresh)."
echo ""
echo -e "  If Alembic migrations are ahead of prod schema, run:"
echo -e "    ${BLUE}docker compose exec backend alembic upgrade head${NC}"
echo ""
