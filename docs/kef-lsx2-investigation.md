# KEF LSX II protocol notes

These are device observations from the April 2026 investigation, with a client
refresh recheck on July 27, 2026 using LSX II firmware `3.0.137.0xf884312`.
They are not a statement of the latest firmware or current Home Assistant core
support. Network addresses and device identifiers are omitted.

The integration and reusable `kef_client` are implemented. See
[configuration](configuration.md), [device support](device-support.md), and the
[Python library](python-library.md) for current use. Remaining work is in
[open KEF development work](feature-checklist.md).

## Two protocol families

The legacy backend uses `aiokef` over TCP port `50001` for first-generation
speakers. The observed LSX II refused that transport and instead exposed the
HTTP API used by its built-in web interface. Keep the two backends distinct;
do not assume settings or playback commands behave identically across them.

Modern firmware may require a web-interface password. The current setup flow
handles that separately from protocol-family detection; see
[authentication](configuration.md).

## Live LSX II device findings

The built-in web UI on the speaker's private address confirmed:

- model: `LSX II`
- release text: `LSXII_V26120`
- version: `2.6.120.0xfb95307`
- wireless IP: private address (anonymized)
- AirPlay version: `366.0`
- MAC address: anonymized

Zeroconf / mDNS services on the device included:

- `_airplay._tcp.local.`
- `_raop._tcp.local.`
- `_spotify-connect._tcp.local.`
- `_http._tcp.local.`

Important detail:

- the Spotify Connect advertisement included `CPath=/api/stream/spotify:zeroconf`

## Confirmed LSX II API behavior

### Core HTTP API

These endpoints responded during the LSX II investigation:

- `GET /api/getData`
- `GET /api/getRows`
- `POST /api/event/modifyQueue`
- `GET /api/event/pollQueue`

The web UI JavaScript also uses:

- `POST /api/setData`

### Confirmed readable paths

The following paths were successfully queried against the live LSX II:

- `settings:/deviceName`
- `settings:/airplay/deviceName`
- `settings:/airplay/addedToHome`
- `settings:/version`
- `settings:/releasetext`
- `settings:/system/primaryMacAddress`
- `network:info`
- `network:profile`
- `firmwareupdate:updateStatus`
- `settings:/kef/play/physicalSource`
- `settings:/kef/host/speakerStatus`
- `settings:/kef/host/modelName`
- `settings:/mediaPlayer/mute`
- `settings:/mediaPlayer/playMode`
- `player:volume`
- `player:player/data`
- `player:player/data/playTime`
- `kef:eqProfile`

### Confirmed `getRows` paths

The following row-based paths were successfully queried:

- `network:scan_results`
- `playlists:pq/getitems`
- `notifications:/display/queue`

### Confirmed event queue API

The event queue API works on LSX II:

- `POST /api/event/modifyQueue` returned a queue id
- `GET /api/event/pollQueue` accepted that queue id and returned an event list

The integration uses event-assisted refresh with polling as a fallback.

## Live LSX II values observed

These values were observed from the real speaker during investigation:

- speaker name: anonymized
- MAC: anonymized
- speaker status: `powerOn`
- source: `usb`
- volume: `80`
- mute: `false`
- play mode: `normal`
- firmware version: `2.6.120.0xfb95307`
- release text: `LSXII_V26120`
- model name node: `SP4041`

The observed `player:player/data` payload included:

- `state`
- `trackRoles.title`
- `trackRoles.mediaData.metaData.serviceID`
- `controls.pause`
- `controls.next_`
- `controls.previous`
- `playId.systemMemberId`

On the live speaker, that response looked like a USB input session rather than a streaming service track, so fields such as duration were absent. That means our integration must treat playback metadata as partially populated, not guaranteed.

## Confirmed EQ payload shape

The path `kef:eqProfile` returned a structured object like:

- `isExpertMode`
- `profileName`
- `profileId`
- `dspInfo.trebleAmount`
- `dspInfo.subwooferPolarity`
- `dspInfo.isKW1`
- `dspInfo.bassExtension`
- `dspInfo.wallModeSetting`
- `dspInfo.highPassModeFreq`
- `dspInfo.audioPolarity`
- `dspInfo.deskMode`
- `dspInfo.subwooferGain`
- `dspInfo.phaseCorrection`
- `dspInfo.subwooferCount`
- `dspInfo.subEnableStereo`
- `dspInfo.wallMode`
- `dspInfo.subwooferPreset`
- `dspInfo.subOutLPFreq`
- `dspInfo.deskModeSetting`
- `dspInfo.balance`
- `dspInfo.highPassMode`

## Modern EQ profile v2 findings

`kef:eqProfile/v2` returns a flat `kefEqProfileV2` object. Beyond the v1
`dspInfo` fields above it adds `subwooferOut`, `soundProfile`,
`dialogueMode`, `wallMounted`, `wirelessSub`, and `isEqMode`.

An LSX II and an XIO report the same schema: the LSX II includes
`soundProfile`, `dialogueMode`, and `wallMounted` even though the KEF Connect
app only offers those on the XIO. The same applies to the XIO settings paths
`settings:/kef/host/autoDetectPlacement` and `settings:/kef/dsp/preferVirtualX`,
which an LSX II also answers. A field or path being present does not mean the
model uses it, so these controls are gated by model rather than by value.

`dialogueMode` is accepted and persisted by both models, but a live listening
test on each produced no audible change. The KEF Connect app has no separate
dialogue setting; dialogue enhancement on the XIO is the `dialogue` value of
`soundProfile`. The integration does not expose `dialogueMode` for that reason.

## XIO virtualizer status

The playback codec string (for example `Dolby Digital Plus - Dolby Surround`)
only names the Dolby upmixer. Whether DTS Virtual:X is also processing is a
separate flag, `imx8af:decoderInfoVirtualXActive`, which turns true when
`settings:/kef/dsp/preferVirtualX` is enabled. The KEF Connect app lists both
("Dolby Surround, Virtual:X").

DTS content reports a bare `DTS` codec string with no processing part, and the
flag is true even with `preferVirtualX` off (observed with DTS 5.1: six stream
channels, `nrAudioChannels` 12). The Dolby upmixer cannot process DTS, so
Virtual:X renders it; the KEF Connect app shows just "DTS Virtual:X". The
virtualizer sensor reports this as "DTS Virtual:X 5.1.2" rather than "Direct".

## XIO wireless subwoofer paths

Reading `kef:ble/updateStatus`, `kef:ble/updateServer/txVersion`, and
per-device `kef:ble/ui/<device>/version` is safe. Activating
`kef:ble/checkForUpdates` is not: on a live XIO it woke the soundbar from
standby and disconnected the paired KW2 receiver until the subwoofer was
power-cycled. Leave firmware checks and updates for the wireless subwoofer
module to the KEF Connect app.

## Fixture guidance

Capture partially populated playback responses as well as streaming metadata.
An external input may have no track title, duration, or seek position. Treat
device-advertised controls and available settings as the capability contract,
and retain polling recovery when the event queue disconnects.
