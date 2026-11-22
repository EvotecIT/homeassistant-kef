# Device support

[Back to the README](../README.md) · [Configuration](configuration.md)

The integration selects a modern HTTP or legacy transport from the speaker it
finds. Newer speakers are not the only supported design target, but implemented
support and real-hardware validation are different things.

| Device family | Current evidence |
| --- | --- |
| LSX II | Real-device local refresh, event queue, and control-path validation |
| LSX II LT | Real-device refresh, event queue, and settings in daily use |
| XIO | Real-device refresh, event queue, and settings, including the XIO-only placement, virtualizer, and calibration controls, and wireless surround controls |
| LS50 Wireless II, LS60 | Modern API compatibility targets; model-specific hardware reports are welcome |
| First-generation LSX / LS50 Wireless | Legacy TCP playback and DSP controls. First-generation LS50 Wireless Rev 2 confirmed DSP reads and treble writes |

Coda W and Muo have Bluetooth connectivity but no supported network API for
this integration, so they are not supported. What each model reports and
supports is in the [model notes](model-notes.md).

Supported devices can expose volume, mute, sources, playback controls, startup
volume, standby, wake behavior, LEDs, and additional settings. Playback controls
depend on the current source. Do not assume a TV or optical input supports the
same transport actions as a streaming source.

On first-generation LSX and LS50 Wireless, playback status and play/pause/track
controls are available on Wi-Fi and Bluetooth. Optical, AUX, and USB keep power,
volume, mute, and source controls without polling playback status. A rejected
playback query during a source change leaves valid source and volume readings
available; connection failures still report an unavailable speaker.

On the legacy TCP backend, turn the speaker on to discover its DSP controls:
desk and wall modes with attenuation, phase correction, treble, bass extension, the high-pass
switch and frequency, and subwoofer crossover, gain, and polarity. The
integration reads DSP while the speaker is on. Legacy desk and wall attenuation
range from -6 to 0 dB in 0.5 dB steps. Treble ranges from -2 to +2 dB in 0.5 dB
steps. While the speaker is on, desk attenuation, wall attenuation, and
high-pass frequency keep their last known values when their modes are off and
the speaker reports an unknown reading. A fresh reading takes precedence. The
integration learns these values from speaker readings and acknowledged writes
until the integration reloads. DSP values can still show as unknown in standby
or before a reading or acknowledged write. See
[DSP scenes](automations.md#switch-dsp-settings-by-input).

The **Speaker channel order** select swaps left and right on the speaker. The
media player’s `master_channel` attribute reports the channel played by the
primary speaker (the one with the inputs). On legacy speakers, **Left / Right**
assigns it to the right channel, and **Right / Left** assigns it to the left.

The **Auto-standby time** select offers **Never**, **20 minutes**, and
**60 minutes**. Changing it keeps the current input and channel order. Turn the
speaker on before changing either setting. When Home Assistant explicitly
turns the speaker off with the 20-minute timer selected, it switches to 60
minutes to avoid a firmware issue on original speakers. The integration also
offers a [Home Assistant volume cap](configuration.md#options) for legacy
speakers.

Modern devices expose a configuration link to their HTTP interface. The legacy
binary control port is not a web page, so legacy devices do not advertise that
port as a configuration link.

Modern devices use event-assisted refresh where available, with polling as a
fallback. An offline speaker is retried at the offline retry interval and
reconnects as soon as it announces itself on the network again; see
[configuration](configuration.md#offline-speakers).

## Report another model

Include the retail model, firmware, integration version, actions you tried, and
a diagnostics capture. Review it before posting and remove passwords or other
personal information. A report that identifies one working action does not
establish every setting for the model.

Contributor references: [API notes](api-notes.md),
[model notes](model-notes.md), and [open work](feature-checklist.md).
