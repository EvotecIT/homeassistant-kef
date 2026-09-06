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

## Fixture guidance

Capture partially populated playback responses as well as streaming metadata.
An external input may have no track title, duration, or seek position. Treat
device-advertised controls and available settings as the capability contract,
and retain polling recovery when the event queue disconnects.
