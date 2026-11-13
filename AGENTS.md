# homeassistant-kef

HACS custom integration that controls KEF wireless speakers from Home
Assistant, plus a standalone async Python client (`kef_client`) for the same
speakers. Supports the modern HTTP API and the legacy TCP protocol.

## Layout

- `custom_components/kef/`: the integration (config flow, coordinator,
  entity platforms, diagnostics, services, translations, `brand/` assets).
- `custom_components/kef/kef_client/`: the protocol client. This is the only
  implementation and owns all speaker protocol logic.
- `kef_client/`: standalone package that loads the bundled client through
  `_loader.py` without importing Home Assistant. Keep its `.pyi` stubs in step
  with the bundled client's public API.
- `tests/`: pytest. Client and transport tests at the root,
  integration tests in `tests/components/kef/`, typing contract in `tests/typing/`.
- `docs/`: configuration, automations, device support, model and API notes,
  development, and the HA quality-scale ledger (`quality-rules.md`, `quality.md`).
- `examples/python_client.py`: runnable client example.

## Build and test

```bash
python -m pip install -e .[test]
ruff check .
pytest
python -m mypy --strict custom_components/kef
```

- Python 3.13+ (CI uses 3.14). CI tests against the supported minimum Home
  Assistant (`requirements-test-minimum.txt`, also `homeassistant` in
  `hacs.json`) and the current comparison target pinned in
  `.github/workflows/validate.yml`. Both must pass.
- The HA test stack (`pytest-homeassistant-custom-component`) imports `fcntl`,
  so full integration tests only run on Linux or WSL. Client tests run anywhere.
- CI also runs hassfest and HACS validation and installs the wheel into a clean
  venv to check the standalone type contract.
- Release-only: merging a PR runs `.github/workflows/release.yml`, which bumps
  the version in `pyproject.toml` and `custom_components/kef/manifest.json`,
  tags and publishes `kef.zip`. Don't bump versions by hand.

## Conventions

- Protocol calls belong in the client. The integration adds setup, entities
  and automations; don't reimplement protocol behaviour in platform code.
- Ruff with line length 88, target `py313`. Typing is `mypy --strict`.
- The HA manifest declares no extra requirements; it uses the `aiohttp` and
  `cryptography` that Home Assistant ships. Keep it that way.
- Gate entities and controls on detected model capabilities
  (`docs/device-support.md`, `docs/model-notes.md`). Don't show controls a model
  doesn't support.
- Diagnostics must not leak credentials or speaker secrets.
- When behaviour changes, update the matching user doc and the rule state in
  `docs/quality-rules.md`.

## Gotchas

- Tests use the local HTTP fixture in `tests/http_server.py`. Don't add tests
  that need a real speaker; hardware checks are manual and recorded in `docs/`.
