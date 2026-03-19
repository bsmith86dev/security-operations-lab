#!/usr/bin/env bash
# .github/scripts/check-namespaces.sh
# Verifies every k3s manifest that references a namespace
# also has that namespace defined in k3s/namespaces/namespaces.yml

set -euo pipefail

NAMESPACE_FILE="k3s/namespaces/namespaces.yml"
ERRORS=0

echo "Checking namespace declarations..."

# Extract all defined namespaces
DEFINED_NS=$(grep -A2 "kind: Namespace" "$NAMESPACE_FILE" | \
  grep "name:" | awk '{print $2}' | sort -u)

# Extract all referenced namespaces from manifests
find k3s/ -name "*.yml" | grep -v "namespaces.yml\|sealed" | while read manifest; do
  # Get namespaces referenced in metadata.namespace fields
  REF_NS=$(grep -E "^\s+namespace:" "$manifest" 2>/dev/null | \
    awk '{print $2}' | sort -u)

  for ns in $REF_NS; do
    # Skip system namespaces
    if [[ "$ns" =~ ^(kube-system|kube-public|kube-node-lease|default|metallb-system|longhorn-system|cert-manager|traefik)$ ]]; then
      continue
    fi
    if ! echo "$DEFINED_NS" | grep -q "^${ns}$"; then
      echo "::error file=$manifest::Namespace '$ns' referenced but not defined in $NAMESPACE_FILE"
      ERRORS=$((ERRORS + 1))
    fi
  done
done

if [ "$ERRORS" -gt 0 ]; then
  echo "::error::$ERRORS namespace reference(s) without definitions"
  exit 1
fi

echo "✓ All namespace references valid"
