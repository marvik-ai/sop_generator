#!/usr/bin/env bash
set -euo pipefail

# Run from the sop_pipeline directory regardless of caller cwd.
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."

# Mocked first (fast, no key needed), then the live-API pass.
uv run pytest tests/test_extract.py
uv run pytest integration_tests/test_extract.py
