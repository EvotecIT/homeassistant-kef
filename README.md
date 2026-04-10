# Home Assistant KEF

HACS-ready custom KEF integration for Home Assistant, focused on modern KEF speakers such as LSX II while keeping room for first-generation support.

Current design goals:

- modern config-entry integration
- local-only control
- no protocol-library dependency on `aiokef` or `pykefcontrol`
- one codebase with separate modern and legacy transports

The live LSX II API investigation is documented in:

- [docs/kef-lsx2-investigation.md](docs/kef-lsx2-investigation.md)
