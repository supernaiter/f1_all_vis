#!/bin/bash
# PostToolUse hook: auto-lint after file edits
# Triggered on: Write, Edit tool uses

# Read the edited file path from stdin JSON
FILE_PATH=$(cat | jq -r '.tool_input.file_path // .tool_input.path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Determine file type and run appropriate linter
case "$FILE_PATH" in
  *.ts|*.tsx|*.js|*.jsx)
    npx eslint --fix "$FILE_PATH" 2>/dev/null
    ;;
  *.py)
    python -m ruff check --fix "$FILE_PATH" 2>/dev/null
    ;;
  *.css|*.scss)
    npx stylelint --fix "$FILE_PATH" 2>/dev/null
    ;;
esac

exit 0
