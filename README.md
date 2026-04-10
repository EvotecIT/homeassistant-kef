# KEF for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://hacs.xyz/)
[![Validate](https://img.shields.io/github/actions/workflow/status/EvotecIT/homeassistant-kef/validate.yml?branch=main&style=for-the-badge&label=Validate)](https://github.com/EvotecIT/homeassistant-kef/actions/workflows/validate.yml)
[![Hassfest](https://img.shields.io/github/actions/workflow/status/EvotecIT/homeassistant-kef/hassfest.yml?branch=main&style=for-the-badge&label=Hassfest)](https://github.com/EvotecIT/homeassistant-kef/actions/workflows/hassfest.yml)

Modern, local-first KEF support for Home Assistant. The integration is built to support both modern HTTP-based KEF speakers such as LSX II and older first-generation models through separate transports in one codebase.

## Highlights

- HACS-ready custom integration with config flow and zeroconf discovery
- Local control without depending on `aiokef` or `pykefcontrol`
- Modern LSX II-era backend plus an in-repo legacy transport
- Rich Home Assistant entities for playback, startup-volume behavior, standby settings, LEDs, and diagnostics
- Designed so the protocol layer can later be extracted into a reusable Python package

## Installation

### HACS

1. Open HACS.
2. Add `https://github.com/EvotecIT/homeassistant-kef` as a custom repository of type `Integration`.
3. Install `KEF`.
4. Restart Home Assistant.
5. Add the integration from `Settings -> Devices & services`.

### Manual

1. Copy [custom_components/kef](C:/Support/GitHub/homeassistant-kef/custom_components/kef) into your Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.
3. Add the integration from `Settings -> Devices & services`.

## Supported Direction

### Modern KEF family

The main focus today is the local HTTP API used by speakers such as:

- LSX II
- LSX II LT
- LS50 Wireless II
- LS60
- XIO

### Legacy KEF family

The repo also contains an in-repo legacy binary transport for older KEF speakers. That path is intentionally kept separate so we do not have to depend on external transport libraries to support first-generation hardware.

## What It Exposes

- `media_player` for playback, source selection, power, volume, mute
- configuration `switch`, `select`, and `number` entities for supported modern-speaker settings
- optional diagnostic and EQ read-only entities

## Repository Layout

### Reusable Python protocol layer

The reusable KEF client layer currently lives inside the integration and is written to be extractable later:

- [api.py](C:/Support/GitHub/homeassistant-kef/custom_components/kef/api.py)
- [models.py](C:/Support/GitHub/homeassistant-kef/custom_components/kef/models.py)
- [exceptions.py](C:/Support/GitHub/homeassistant-kef/custom_components/kef/exceptions.py)

This layer is responsible for:

- backend detection
- modern HTTP transport
- legacy binary transport
- payload parsing and capability normalization

### Home Assistant integration layer

The Home Assistant integration lives in:

- [config_flow.py](C:/Support/GitHub/homeassistant-kef/custom_components/kef/config_flow.py)
- [coordinator.py](C:/Support/GitHub/homeassistant-kef/custom_components/kef/coordinator.py)
- [media_player.py](C:/Support/GitHub/homeassistant-kef/custom_components/kef/media_player.py)
- [switch.py](C:/Support/GitHub/homeassistant-kef/custom_components/kef/switch.py)
- [select.py](C:/Support/GitHub/homeassistant-kef/custom_components/kef/select.py)
- [number.py](C:/Support/GitHub/homeassistant-kef/custom_components/kef/number.py)
- [sensor.py](C:/Support/GitHub/homeassistant-kef/custom_components/kef/sensor.py)
- [binary_sensor.py](C:/Support/GitHub/homeassistant-kef/custom_components/kef/binary_sensor.py)

## Live Investigation Notes

The modern LSX II API work and live validation notes are documented here:

- [kef-lsx2-investigation.md](C:/Support/GitHub/homeassistant-kef/docs/kef-lsx2-investigation.md)

## Current Direction

- keep the transport layer dependency-free
- add capability-based entity exposure instead of firmware-only assumptions
- improve parity for both modern and legacy families
- keep a clean future path to a standalone `python-kef-local` style library

## Development

Install test dependencies:

```bash
python -m pip install -e .[test]
```

Run checks:

```bash
ruff check .
python -m compileall custom_components tests
pytest
```

Note:

- the full Home Assistant pytest stack is expected to run in Ubuntu CI
- on Windows, `pytest-homeassistant-custom-component` imports `fcntl`, which blocks complete local HA pytest runs

## Support

- Issues: [GitHub Issues](https://github.com/EvotecIT/homeassistant-kef/issues)
- Source: [GitHub Repository](https://github.com/EvotecIT/homeassistant-kef)
