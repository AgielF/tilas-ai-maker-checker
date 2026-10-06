#!/usr/bin/env bash
# tools/sanitize.sh — Tilas pre-commit security & hygiene gate
# Jalankan sebelum `git commit`. Exit 0 = aman, exit 1 = ada temuan.
set -uo pipefail

RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; NC=$'\033[0m'
FAIL=0

# File yang sengaja dikecualikan dari pemindaian pola secret.
# - docs/SECURITY.md  : mendokumentasikan prefix key yang SUDAH DI-REVOKE (bukan secret aktif)
# - tools/sanitize.sh : memuat pola regex itu sendiri
SCAN_EXCLUDE=(
  ":(exclude)docs/SECURITY.md"
  ":(exclude)tools/sanitize.sh"
  ":(exclude)*.pdf"
  ":(exclude)*.lock"
  ":(exclude)*package-lock.json"
)

echo "==> Tilas sanitize.sh — pre-commit gate"
echo

# ---------- 1. File terlarang di staging ----------
echo "[1/3] Cek file terlarang di staging..."
FORBIDDEN_BASENAMES=( ".env" "mcp.json" )
FORBIDDEN_DIRS=( ".bob" ".langflow" )
FORBIDDEN_GLOBS=( "*.key" ".env.*" )

STAGED=$(git diff --cached --name-only --diff-filter=ACM)
BLOCKED=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  base="$(basename "$f")"
  # allowlist: template aman
  if [ "$base" = ".env.example" ]; then continue; fi

  for b in "${FORBIDDEN_BASENAMES[@]}"; do
    [ "$base" = "$b" ] && { echo "${RED}[BLOCK]${NC} $f"; BLOCKED=1; }
  done
  for g in "${FORBIDDEN_GLOBS[@]}"; do
    case "$base" in $g) echo "${RED}[BLOCK]${NC} $f"; BLOCKED=1;; esac
  done
  for d in "${FORBIDDEN_DIRS[@]}"; do
    case "$f" in "$d"/*|*/"$d"/*) echo "${RED}[BLOCK]${NC} $f"; BLOCKED=1;; esac
  done
done <<< "$STAGED"

if [ "$BLOCKED" -eq 0 ]; then
  echo "${GREEN}OK${NC} — tidak ada file terlarang di staging."
else
  FAIL=1
fi
echo

# ---------- 2. Pola secret pada perubahan staged ----------
echo "[2/3] Scan pola secret pada diff staged..."
# ⚠️ Setiap alternatif diawali \b (word boundary) supaya "risk-" tidak match "sk-".
PATTERNS='\bsk-[A-Za-z0-9_-]{16,}|\bAIza[0-9A-Za-z_-]{20,}|\bghp_[A-Za-z0-9]{20,}|\bgho_[A-Za-z0-9]{20,}|\bAKIA[0-9A-Z]{16}|\b9YD6Y15|-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer [A-Za-z0-9._-]{20,}'

HITS=$(git diff --cached -U0 -- . "${SCAN_EXCLUDE[@]}" 2>/dev/null \
        | grep -E '^\+' \
        | grep -nE "$PATTERNS" || true)

if [ -n "$HITS" ]; then
  echo "${RED}[BLOCK]${NC} Pola secret terdeteksi pada baris yang ditambahkan:"
  echo "$HITS"
  FAIL=1
else
  echo "${GREEN}OK${NC} — tidak ada pola secret."
fi
echo

# ---------- 3. File sensitif di working tree ----------
echo "[3/3] Cek file sensitif di working tree..."
for f in .env mcp.json; do
  if [ -f "$f" ]; then
    if git check-ignore -q "$f"; then
      echo "${GREEN}OK${NC} — $f ada tapi ter-ignore."
    else
      echo "${YELLOW}[WARN]${NC} $f ada dan TIDAK ter-ignore oleh .gitignore."
      FAIL=1
    fi
  fi
done
if [ "$FAIL" -eq 0 ]; then
  echo "${GREEN}OK${NC} — tidak ada file sensitif yang bocor."
fi
echo

# ---------- Ringkasan ----------
if [ "$FAIL" -eq 0 ]; then
  echo "${GREEN}==> LULUS — aman untuk commit.${NC}"
  exit 0
else
  echo "${RED}==> GAGAL — perbaiki temuan di atas sebelum commit.${NC}"
  exit 1
fi