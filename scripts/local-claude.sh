#!/usr/bin/env bash
# Start Claude Code against a LOCAL Ollama model (the "executor"). The planner session is a normal `claude` in another terminal.
#
#   scripts/local-claude.sh [model] [-- extra claude args]
#   scripts/local-claude.sh qwen3-coder -- -p "$(cat docs/briefs/001-example.md)"
#
# Needs: Ollama running with a big enough context (the server's default is only 4k below 24 GiB of memory):
#   OLLAMA_CONTEXT_LENGTH=64000 ollama serve
# The variables below are set only for this one process; never put them in your shell profile (they would also redirect your
# planner session to the local model).
set -eu
cd "$(dirname "$0")/.."
MODEL="${1:-${LOCAL_MODEL:-qwen3-coder}}"
[ "$#" -gt 0 ] && shift
[ "${1:-}" = "--" ] && shift

if ! curl -s -m 2 http://localhost:11434/api/version >/dev/null; then
  echo "Ollama is not answering on localhost:11434. Start it first:  OLLAMA_CONTEXT_LENGTH=64000 ollama serve" >&2
  exit 2
fi
if ! ollama list 2>/dev/null | awk 'NR>1{print $1}' | grep -qx "$MODEL\(:latest\)\?\|$MODEL"; then
  echo "Model '$MODEL' is not pulled. Try:  ollama pull $MODEL   (or pass another model name from 'ollama list')" >&2
  exit 2
fi
echo "Executor: $MODEL  (context: check 'ollama ps', it should show 64000 and 100% GPU)"
ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_API_KEY="" ANTHROPIC_BASE_URL=http://localhost:11434 \
  exec claude --model "$MODEL" "$@"
