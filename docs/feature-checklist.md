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
  - [x] USB charging
  - [x] startup volume and per-input startup volumes
  - [x] maximum volume / volume step / volume limiter
  - [x] subwoofer wake and KW1 wake
- [x] Reusable `kef_client` Python package
- [x] HACS-ready packaging and first GitHub release

## High-Priority Next

- [ ] Writable EQ / DSP entities for modern KEF
  - [ ] balance
  - [ ] bass extension
  - [ ] treble amount
  - [ ] subwoofer gain
  - [ ] desk mode
  - [ ] wall mode
  - [ ] phase correction
  - [ ] high-pass mode
  - [ ] high-pass frequency
- [ ] Writable fixed-volume control
- [ ] Writable cable mode
- [ ] Writable master-channel control

## Runtime / Architecture Improvements

- [ ] Use the KEF event queue API to reduce pure polling
  - [ ] `event/modifyQueue`
  - [ ] `event/pollQueue`
  - [ ] coordinator refresh integration
- [ ] Make playback command support more source-aware in the UI
- [ ] Improve capability detection per device family instead of relying only on model assumptions

## Compatibility Work

- [ ] Validate first-generation KEF behavior on real older hardware
- [ ] Confirm parity with the older Home Assistant KEF feature set where it makes sense
- [ ] Add fixtures from real first-generation devices
- [ ] Investigate firmware 4.x authentication/password behavior for newer KEF firmware

## Home Assistant Polish

- [ ] Better presentation for advanced DSP controls once writable
- [ ] Continue reducing noisy optional entities by default
- [ ] Add clearer diagnostics for backend choice, model family, and capability detection
- [ ] Consider repair guidance for auth-required or partially supported devices

## Nice-to-Have Later

- [ ] Event-driven metadata refresh instead of regular polling where supported
- [ ] More polished transport mapping by source family
- [ ] Additional examples for standalone `kef_client` use outside Home Assistant
