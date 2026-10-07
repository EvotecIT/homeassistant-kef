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

Dependency qualification also requires evidence for licenses, public package
availability, release tags, and the upstream publication pipelines. The
[rule ledger](quality-rules.md) tracks that remaining provenance check separately
from the integration's transport and packaging tests.
