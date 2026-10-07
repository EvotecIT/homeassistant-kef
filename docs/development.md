# Development

[Back to the README](../README.md) · [Python library](python-library.md) ·
[Open work](feature-checklist.md) · [Quality qualification](quality.md)

```bash
python -m pip install -e .[test]
ruff check .
python -m compileall kef_client custom_components tests examples
pytest
```

Note:

- the full Home Assistant pytest stack runs best in Linux CI
- on Windows, `pytest-homeassistant-custom-component` imports `fcntl`, so complete local HA pytest runs are limited

Keep Home Assistant setup and daily-use instructions in the README and user
guides. Protocol investigations and model-validation evidence belong in the
existing investigation notes.

The reusable client is the protocol owner; the Home Assistant integration
provides setup, entities, and automations. See the
[Python library guide](python-library.md) and
[runnable client example](../examples/python_client.py) instead of copying
protocol calls into Home Assistant configuration.

## Runtime dependencies

The protocol implementation is bundled at
`custom_components/kef/kef_client`; the top-level `kef_client` package exposes
that same implementation for standalone Python callers. HACS installations
include the bundled client and do not install a separate KEF client package.

Modern speakers use `aiohttp` with Home Assistant's shared HTTP session.
`cryptography` supplies AES encryption for the speaker authentication protocol.
Legacy speakers use Python's asynchronous IPv4 TCP transport. The standalone
package declares `aiohttp` and `cryptography` in `pyproject.toml`; the HA manifest
has no additional package requirements and uses the libraries supplied by HA.

The dependency provenance check on 2026-10-07 covers the versions resolved in
both qualification environments. These are evidence snapshots, not additional
installation pins.

| Dependency | Minimum/current environment | Public source and publication |
| --- | --- | --- |
| aiohttp | 3.11.11 / 3.14.3 | Apache 2.0; public PyPI releases correspond to upstream `v3.11.11` and `v3.14.3` tags. The tagged [CI workflow](https://github.com/aio-libs/aiohttp/blob/v3.14.3/.github/workflows/ci-cd.yml) builds source distributions and wheels and publishes to PyPI. |
| cryptography | 44.0.0 / 48.0.1 | Apache-2.0 OR BSD-3-Clause; public PyPI releases correspond to upstream `44.0.0` and `48.0.1` tags. The tagged [wheel builder](https://github.com/pyca/cryptography/blob/48.0.1/.github/workflows/wheel-builder.yml) supplies the [publishing workflow](https://github.com/pyca/cryptography/blob/48.0.1/.github/workflows/pypi-publish.yml). |

PyPI source-archive provenance identifies these upstream GitHub publishers for
all four versions. This verifies public dependency ownership and publication
paths; it does not certify a particular installed Home Assistant artifact.
Recheck this evidence when the supported environments change.
