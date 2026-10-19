#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./install-skills.sh /path/to/project/root

Install or update this repository's OpenCode N3TX skills into another project.
The script copies .opencode/skills from this repo into:

  /path/to/project/root/.opencode/skills

It creates the target .opencode/skills directory if needed. Existing N3TX skill
files with the same names are updated; unrelated target-project skills are left
in place.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_SKILLS_DIR="${SCRIPT_DIR}/.opencode/skills"
TARGET_ROOT="$1"

if [[ ! -d "${SOURCE_SKILLS_DIR}" ]]; then
  echo "error: source skills directory not found: ${SOURCE_SKILLS_DIR}" >&2
  exit 1
fi

if [[ ! -d "${TARGET_ROOT}" ]]; then
  echo "error: target project root is not a directory: ${TARGET_ROOT}" >&2
  exit 1
fi

TARGET_OPENCODE_DIR="${TARGET_ROOT%/}/.opencode"
TARGET_SKILLS_DIR="${TARGET_OPENCODE_DIR}/skills"

mkdir -p "${TARGET_SKILLS_DIR}"

echo "Installing N3TX OpenCode skills"
echo "  source: ${SOURCE_SKILLS_DIR}"
echo "  target: ${TARGET_SKILLS_DIR}"

if command -v rsync >/dev/null 2>&1; then
  rsync -a "${SOURCE_SKILLS_DIR}/" "${TARGET_SKILLS_DIR}/"
else
  # Fallback keeps this script portable on minimal systems. It overwrites files
  # with the same paths but preserves unrelated target-project skills.
  cp -R "${SOURCE_SKILLS_DIR}/." "${TARGET_SKILLS_DIR}/"
fi

SOURCE_COUNT="$(find "${SOURCE_SKILLS_DIR}" -name SKILL.md | wc -l | tr -d ' ')"
TARGET_COUNT="$(find "${TARGET_SKILLS_DIR}" -name SKILL.md | wc -l | tr -d ' ')"

echo "Done. Copied ${SOURCE_COUNT} N3TX skills. Target now contains ${TARGET_COUNT} total skills."
echo "Restart OpenCode in the target project to load the updated skills."
