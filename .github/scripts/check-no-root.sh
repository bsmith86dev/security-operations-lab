#!/usr/bin/env bash
# .github/scripts/check-no-root.sh
# Blocks any container spec that runs as root (UID 0)
# Exceptions: explicitly documented with a lab.blerdmh.com/root-required annotation

set -euo pipefail

ERRORS=0

echo "Checking for root containers..."

find k3s/ -name "*.yml" | grep -v "sealed\|namespace\|pv\b" | while read manifest; do
  # Check for runAsUser: 0 (explicit root)
  if grep -n "runAsUser: 0" "$manifest" 2>/dev/null; then
    # Check if there's an exception annotation
    if ! grep -q "lab.blerdmh.com/root-required" "$manifest"; then
      echo "::error file=$manifest::Container running as root (runAsUser: 0) without exception annotation"
      ERRORS=$((ERRORS + 1))
    else
      echo "::warning file=$manifest::Root container allowed via annotation — verify this is intentional"
    fi
  fi

  # Check for privileged: true without annotation
  if grep -n "privileged: true" "$manifest" 2>/dev/null; then
    if ! grep -q "lab.blerdmh.com/privileged-required" "$manifest"; then
      echo "::error file=$manifest::Privileged container without exception annotation"
      ERRORS=$((ERRORS + 1))
    fi
  fi
done

if [ "$ERRORS" -gt 0 ]; then
  echo "::error::$ERRORS security policy violation(s) found"
  exit 1
fi

echo "✓ No unauthorized root/privileged containers"
