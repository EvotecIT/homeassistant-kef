# KEF Feature Checklist

This checklist tracks what the repository already covers and what still needs work to reach fuller modern-and-legacy KEF support.

## Current Working Core

- [x] Zeroconf discovery and config flow
- [x] Modern KEF HTTP backend
- [x] Legacy backend path in the same integration
- [x] Single `media_player` with source selection, power, volume, mute, and playback commands
- [x] Modern configuration entities for:
  - [x] standby mode
  - [x] wake source
  - [x] startup tone
  - [x] HDMI auto-switch
  - [x] front LED / standby LED / top panel
  - [x] top-panel active and standby LED controls
  - [x] USB charging
  - [x] startup volume and per-input startup volumes
  - [x] maximum volume / volume step / volume limiter
  - [x] subwoofer wake and KW1 wake
- [x] Reusable `kef_client` Python package
- [x] HACS-ready packaging and first GitHub release

## High-Priority Next

- [x] Writable EQ / DSP entities for modern KEF
  - [x] `kef:eqProfile` and `kef:eqProfile/v2` parsing/writes
  - [x] balance
  - [x] bass extension
  - [x] treble amount
  - [x] subwoofer gain
  - [x] desk mode
  - [x] wall mode
  - [x] phase correction
  - [x] high-pass mode
  - [x] high-pass frequency
- [x] Writable fixed-volume control
- [x] Writable cable mode
- [x] Writable master-channel control
- [x] Firmware update entity for check/download/install
- [x] Local `.swu` firmware upload service for Home Assistant

## Runtime / Architecture Improvements

- [x] Use the KEF event queue API to reduce pure polling
  - [x] `event/modifyQueue`
  - [x] `event/pollQueue`
  - [x] coordinator refresh integration
  - [ ] broaden event subscriptions and error recovery for more KEF families
- [x] Make playback command support more source-aware in the UI for modern KEF sources
- [ ] Extend source-aware transport behavior further if legacy devices need different handling
- [ ] Improve capability detection per device family instead of relying only on model assumptions

## Compatibility Work

- [ ] Validate first-generation KEF behavior on real older hardware
- [ ] Confirm parity with the older Home Assistant KEF feature set where it makes sense
- [ ] Add fixtures from real first-generation devices
- [x] Investigate firmware 3.x authenticated local API behavior on LSX II
- [ ] Validate firmware 4.x authentication/password behavior on LS50W II hardware

## Advanced Capability Coverage

- [x] Add richer device identifiers where available:
  - [x] serial number
  - [x] KEF ID
  - [x] hardware version
- [x] Add remote-control configuration where supported:
  - [x] remote IR enable
  - [x] remote IR code set
  - [x] favorite button action
  - [x] EQ button actions
- [x] Add optional network diagnostic surfaces:
  - [x] internet ping
  - [x] network stability
  - [x] speed-test status/results
- [x] Add privacy and regional settings:
  - [x] KEF analytics
  - [x] app analytics
  - [x] streaming quality
  - [x] UI language
  - [x] speaker location
- [x] Add read-only alert/timer diagnostics
- [ ] Investigate alert/timer/alarm write controls before exposing actions
- [ ] Investigate grouping/multiroom and notification queue usefulness
- [ ] Investigate model-specific calibration, BLE subwoofer firmware, XIO dialogue mode, and sound profile controls

## Home Assistant Polish

- [ ] Better presentation for advanced DSP controls once writable
- [ ] Continue reducing noisy optional entities by default
- [ ] Add clearer diagnostics for backend choice, model family, and capability detection
- [ ] Consider repair guidance for auth-required or partially supported devices

## Nice-to-Have Later

- [ ] Event-driven metadata refresh instead of regular polling where supported
- [ ] More polished transport mapping by source family
- [ ] Additional examples for standalone `kef_client` use outside Home Assistant
