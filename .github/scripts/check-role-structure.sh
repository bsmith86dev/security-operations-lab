#!/usr/bin/env bash
# .github/scripts/check-role-structure.sh
# Validates each Ansible role has required files

set -euo pipefail

ERRORS=0

echo "Validating Ansible role structure..."

for role_dir in ansible/roles/*/; do
  role_name=$(basename "$role_dir")

  # Every role must have tasks/main.yml
  if [ ! -f "${role_dir}tasks/main.yml" ]; then
    echo "::error::Role '$role_name' missing tasks/main.yml"
    ERRORS=$((ERRORS + 1))
  fi

  # Warn if no README
  if [ ! -f "${role_dir}README.md" ]; then
    echo "::warning::Role '$role_name' has no README.md — add documentation"
  fi

  # If templates/ exists, every .j2 file must be referenced somewhere
  if [ -d "${role_dir}templates" ]; then
    for template in "${role_dir}templates/"*.j2; do
      [ -f "$template" ] || continue
      template_name=$(basename "$template")
      if ! grep -r "$template_name" "${role_dir}tasks/" > /dev/null 2>&1; then
        echo "::warning file=$template::Template '$template_name' not referenced in any task"
      fi
    done
  fi

  echo "  ✓ $role_name"
done

if [ "$ERRORS" -gt 0 ]; then
  echo "::error::$ERRORS role structure error(s)"
  exit 1
fi

echo "✓ All roles valid"
