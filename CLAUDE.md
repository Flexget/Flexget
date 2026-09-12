# CLAUDE.md

## Architecture

- REST API: Flask + flask-restx, version tracked in `flexget/api/app.py` (`__version__`)
- All route handlers extend `APIResource` (auto-injects SQLAlchemy session, adds API-Version header)
- Core namespaces in `flexget/api/core/`; component namespaces each in `flexget/components/*/api.py`
- Task execution phases (in order): prepare → start → input → metainfo → filter → download → modify → output → learn → exit

## Known bugs (unresolved as of this session)

- `flexget/components/pending_approval/api.py`: pagination total count ignores filters (line 105); `per_page` clamped twice (lines 85/90); `PUT /` uses wrong parser (line 137)
- `pending_approval` plugin is deprecated — prefer `pending_list`

## Package manager

- Project uses `uv` exclusively — no pip/poetry/hatch invocations needed for day-to-day work
- `setup.sh` at repo root is the fast-path for environment setup: installs uv if absent, creates `.venv`, installs `dev` + `test` dependency groups
- `.env` file at repo root is auto-loaded by `uv run`; copy from `.env.example` to configure local env vars

## bundle_webui.py behaviour

- `BUNDLE_WEBUI` env var only guards the hatchling build hook (used during `uv build` / PyPI release)
- When invoked directly via `uv run scripts/bundle_webui.py` (as the Dockerfile does), the WebUI is ALWAYS bundled — `BUNDLE_WEBUI` is not checked
- `V2_WEBUI_LOCATION` env var overrides the v2 dist.zip source; accepts HTTP/HTTPS URL or local file path; exposed as a Docker `ARG` for build-time override

## run_server.sh behaviour

- Takes an optional parameter: no args = start if not running; `restart` = stop then start; `stop` = stop only (no restart)
- If `FLEXGET_CONFIG` is unset, falls back to `.venv/config.yml`, auto-creating it with a minimal example task if the file does not exist
- Loads `.env` from repo root before starting (non-overwriting, same pattern as `manual_release.sh`)

## Known pre-existing test failures

- `tests/test_npo_watchlist.py` — 3 tests fail due to `chardet` 7.x emitting a `DeprecationWarning` via `html5lib`, which FlexGet promotes to a plugin abort; unrelated to application logic
