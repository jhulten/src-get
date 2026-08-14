# src-get shell integration for bash and zsh
#
# Wraps the src-get binary so that on success the shell automatically
# changes into the cloned/updated repository directory.
#
# The binary writes git output to stderr and prints only the repo path
# to stdout, so we can capture them independently.
#
# Usage: source this file in your ~/.bashrc or ~/.zshrc
#
#   source /path/to/src-get/shell/src-get.sh
#
# Or, if installed via pip/uv into your PATH, just add the function below
# directly to your shell rc file.

src-get() {
  local repo_path exit_code

  # Capture stdout (repo path) only; stderr (git output) flows to the terminal.
  repo_path=$(command src-get "$@")
  exit_code=$?

  if [ "$exit_code" -eq 0 ] && [ -n "$repo_path" ]; then
    cd "$repo_path" || return 1
  fi

  return "$exit_code"
}
