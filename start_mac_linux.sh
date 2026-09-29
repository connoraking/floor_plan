#!/usr/bin/env sh
set -eu

url="https://github.com/connoraking/floor_plan/releases/latest"
printf '%s\n' "Opening the Floor Planner download page..."

if command -v open >/dev/null 2>&1; then
  open "$url"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$url"
else
  printf '%s\n' "$url"
fi
