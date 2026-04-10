# KEF for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://hacs.xyz/)
[![Validate](https://img.shields.io/github/actions/workflow/status/EvotecIT/homeassistant-kef/validate.yml?branch=main&style=for-the-badge&label=Validate)](https://github.com/EvotecIT/homeassistant-kef/actions/workflows/validate.yml)
[![Hassfest](https://img.shields.io/github/actions/workflow/status/EvotecIT/homeassistant-kef/hassfest.yml?branch=main&style=for-the-badge&label=Hassfest)](https://github.com/EvotecIT/homeassistant-kef/actions/workflows/hassfest.yml)

Local-first KEF support for Home Assistant, built to support both newer KEF speakers and older generations in one integration.

![KEF integration overview](assets/kef-overview.png)

## 🎯 What This Is

This project is a custom KEF integration for Home Assistant with a strong bias toward:

- local control
- clean Home Assistant setup
- no dependency on external KEF transport libraries
- one codebase for modern and legacy KEF families

## 🔊 Device Support Direction

### Modern KEF family

The most mature support today is for speakers using KEF's newer local HTTP API, including:

- LSX II
- LSX II LT
- LS50 Wireless II
- LS60
- XIO

### Older KEF family

Older first-generation KEF speakers matter too. This repo already includes a separate legacy transport path so the integration can support earlier LSX / LS50 Wireless-style devices without forcing them through the newer API model.

Current live validation is strongest on LSX II, but broad KEF coverage is the goal, not just the newest models.

## ✨ What You Get

- zeroconf discovery and UI setup
- media player controls
- source selection
- volume and mute
- startup-volume controls
- standby and wake-source settings
- LED and hardware behavior controls where supported
- event-assisted refresh on modern KEF speakers
- optional diagnostics

## 🏠 Installation

### HACS

1. Open HACS.
2. Add `https://github.com/EvotecIT/homeassistant-kef` as a custom repository of type `Integration`.
3. Install `KEF`.
4. Restart Home Assistant.
5. Go to `Settings -> Devices & services` and add `KEF`.

### Manual

1. Copy the `custom_components/kef` folder into your Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.
3. Add the integration from `Settings -> Devices & services`.

## ✅ Current Status

- strongest real-device validation today: LSX II
- modern KEF support is already practical and expanding, including event-assisted refresh on LSX II-era devices
- legacy KEF support is part of the design, not an afterthought
- compatibility is handled by transport and capability detection, not just hardcoded firmware guesses

The current LSX II investigation notes are in `docs/kef-lsx2-investigation.md`.

Feature tracking checklist: `docs/feature-checklist.md`

## 🧱 Reusable Python Package

This repository now ships two usable layers:

- `kef_client` for direct Python access to KEF local APIs
- the Home Assistant integration in `custom_components/kef`

Library docs: `docs/python-library.md`

Runnable example: `examples/python_client.py`

Example:

```python
from aiohttp import ClientSession
from kef_client import ModernKefClient

async with ClientSession() as session:
    client = ModernKefClient("192.168.1.20", session)
    snapshot = await client.async_refresh()
    print(snapshot.device.device_name, snapshot.source)
```

That keeps the protocol layer reusable for scripts and apps while the integration stays focused on Home Assistant setup and entities.

## 🛣️ Roadmap

- next tracked work lives in `docs/feature-checklist.md`
- top priorities are writable cable mode, older-device validation, and continued capability polishing
- the long-term direction remains one integration with strong modern and legacy support

## 🛠️ Development

```bash
python -m pip install -e .[test]
ruff check .
python -m compileall kef_client custom_components tests examples
pytest
```

Note:

- the full Home Assistant pytest stack runs best in Linux CI
- on Windows, `pytest-homeassistant-custom-component` imports `fcntl`, so complete local HA pytest runs are limited

## ❤️ Support

- Issues: [GitHub Issues](https://github.com/EvotecIT/homeassistant-kef/issues)
- Source: [GitHub Repository](https://github.com/EvotecIT/homeassistant-kef)
