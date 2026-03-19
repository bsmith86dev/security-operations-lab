#!/usr/bin/env bash
# .github/scripts/check-resource-limits.sh
# Every container must define resource requests AND limits
# This prevents noisy-neighbor problems in the k3s cluster

set -euo pipefail

ERRORS=0
WARNINGS=0

echo "Checking resource limits..."

find k3s/ -name "*.yml" | grep -v "sealed\|namespace\|pv\b\|values" | while read manifest; do
  # Count containers vs resource limit definitions
  # This is a heuristic — kubeconform catches the schema issues,
  # this catches "defined but empty" patterns

  CONTAINER_COUNT=$(grep -c "image:" "$manifest" 2>/dev/null || echo 0)
  LIMITS_COUNT=$(grep -c "limits:" "$manifest" 2>/dev/null || echo 0)
  REQUESTS_COUNT=$(grep -c "requests:" "$manifest" 2>/dev/null || echo 0)

  if [ "$CONTAINER_COUNT" -gt 0 ]; then
    if [ "$LIMITS_COUNT" -eq 0 ]; then
      echo "::warning file=$manifest::No resource limits defined ($CONTAINER_COUNT container(s))"
      WARNINGS=$((WARNINGS + 1))
    fi
    if [ "$REQUESTS_COUNT" -eq 0 ]; then
      echo "::warning file=$manifest::No resource requests defined ($CONTAINER_COUNT container(s))"
      WARNINGS=$((WARNINGS + 1))
    fi
  fi
done

if [ "$ERRORS" -gt 0 ]; then
  exit 1
fi

if [ "$WARNINGS" -gt 0 ]; then
  echo "::warning::$WARNINGS resource limit warning(s) — review before merging to main"
fi

echo "✓ Resource limits check complete"
