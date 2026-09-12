#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# Install uv if not present
if ! command -v uv &>/dev/null; then
    echo "==> uv not found — installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # uv installer puts the binary in ~/.local/bin by default
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "==> uv $(uv --version)"

# Sync the project with all groups needed to run, test, and develop:
#   (default)  — core runtime dependencies from [project.dependencies]
#   --group dev  — pytest, ruff, prek, pytest-cov, pytest-xdist, vcrpy
#   --group test — pillow, pytest-ftpserver, plus all optional plugin deps
#                  (boto3, deluge, ftp, matrix, plexapi, qbittorrent, rarfile,
#                   sftp, subliminal, telegram, transmission)
echo "==> Syncing dependencies (dev + test groups)..."
uv sync --group dev --group test

echo ""
echo "Done. Virtual environment created at .venv/"
echo ""
echo "  Activate:    source .venv/bin/activate"
echo "  Run tests:   uv run pytest"
echo "  Start app:   uv run flexget"
