# Device support

[Back to the README](../README.md) · [Configuration](configuration.md)

The integration selects a modern HTTP or legacy transport from the speaker it
finds. Newer speakers are not the only supported design target, but implemented
support and real-hardware validation are different things.

| Device family | Current evidence |
| --- | --- |
| LSX II | Real-device local refresh, event queue, and control-path validation |
| LSX II LT, LS50 Wireless II, LS60, XIO | Modern API compatibility targets; model-specific hardware reports are welcome |
| First-generation LSX / LS50 Wireless | Legacy transport implemented; further real-hardware validation is needed |

Supported devices can expose volume, mute, sources, playback controls, startup
volume, standby, wake behavior, LEDs, and additional settings. Playback controls
depend on the current source. Do not assume a TV or optical input supports the
same transport actions as a streaming source.

Modern devices use event-assisted refresh where available, with polling as a
fallback. Unavailable speakers continue polling and recover after a successful
refresh.

## Report another model

Include the retail model, firmware, integration version, actions you tried, and
a diagnostics capture. Review it before posting and remove passwords or other
personal information. A report that identifies one working action does not
establish every setting for the model.

Contributor references: [LSX II investigation](kef-lsx2-investigation.md) and
[open work](feature-checklist.md).
