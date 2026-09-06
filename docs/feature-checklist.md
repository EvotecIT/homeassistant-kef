# Open KEF development work

For implemented controls and model support, use [configuration](configuration.md)
and [device support](device-support.md). The reusable client and Home Assistant
integration already exist; this list tracks remaining work.

## Device and firmware coverage

- [ ] Capture sanitized first-generation LSX/LS50 Wireless fixtures and validate
  legacy playback, source selection, and DSP behavior on real hardware.
- [ ] Validate firmware 4.x local authentication on LS50 Wireless II hardware.
- [ ] Broaden event-queue and recovery testing across modern KEF families.
- [ ] Refine capability detection where a model advertises fewer settings than
  other speakers using the same protocol.

## Undocumented capabilities

- [ ] Investigate alert, timer, and alarm writes before exposing actions.
- [ ] Determine whether grouping, multiroom, and notification queues provide
  useful, controllable features.
- [ ] Verify model-specific calibration, BLE subwoofer firmware, XIO dialogue
  mode, and sound-profile APIs with device captures.

## Home Assistant usability

- [ ] Improve grouping and descriptions of advanced DSP controls where the
  current entities are difficult to navigate.
- [ ] Add actionable repair guidance for authenticated or partially supported
  devices when the existing setup errors do not explain recovery.

Keep new settings capability-gated. Add fixture and device proof before widening
support, and remove completed items from this list rather than retaining a
second inventory of implemented features.
