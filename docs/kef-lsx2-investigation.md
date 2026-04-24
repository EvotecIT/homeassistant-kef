# KEF LSX II Investigation

Last updated: 2026-04-09

## Goal

Work out whether a modern Home Assistant custom integration can support both:

- first-generation KEF speakers that Home Assistant currently drives through `aiokef`
- second-generation KEF speakers such as LSX II that appear to use a different local API

This note captures what was confirmed from:

- the current Home Assistant KEF integration
- the `aiokef` library
- community research around the second-generation KEF HTTP API
- a live KEF LSX II at `192.168.241.228`

## Short conclusion

The current Home Assistant KEF integration is effectively a legacy integration for first-generation speakers.

For LSX II, the old `aiokef` TCP transport on port `50001` is not available. The speaker instead exposes a local HTTP API used by its built-in web UI:

- `GET /api/getData`
- `POST /api/setData`
- `GET /api/getRows`
- `POST /api/event/modifyQueue`
- `GET /api/event/pollQueue`

That means a proper custom integration should use two backends:

- `aiokef` backend for first-generation LSX / LS50W
- NSDK HTTP backend for LSX II / LS50 Wireless II / LS60

## What Home Assistant currently does

The current Home Assistant core KEF integration is still a legacy-quality integration:

- domain: `kef`
- quality scale: `legacy`
- dependency: `aiokef==0.2.16`
- configuration style: YAML `media_player` platform, not a modern config-entry integration

It exposes:

- media player control
- source selection
- mute and volume
- several DSP service calls

It does not provide:

- config flow
- discovery
- modern entities for advanced settings
- a backend for second-generation KEF devices

## First-generation vs second-generation split

### First-generation KEF

`aiokef` talks to the speaker over TCP port `50001` with a compact binary protocol.

Confirmed from the current `aiokef` source:

- source
- power state
- volume
- mute
- play/pause
- track next/previous
- DSP values such as desk/wall/treble/high/low/sub

This matches the current Home Assistant core integration.

### Second-generation KEF

The live LSX II refused connections on TCP port `50001`:

- `ConnectionRefusedError` on `192.168.241.228:50001`

At the same time, it exposed a local web UI and an HTTP API under `/api/*`.

This means LSX II is not a drop-in target for the current `aiokef` backend.

## Live LSX II device findings

The built-in web UI at `http://192.168.241.228/` confirmed:

- model: `LSX II`
- release text: `LSXII_V26120`
- version: `2.6.120.0xfb95307`
- wireless IP: `192.168.241.228`
- AirPlay version: `366.0`
- MAC address: `84:17:15:04:43:8C`

Zeroconf / mDNS services on the device included:

- `_airplay._tcp.local.`
- `_raop._tcp.local.`
- `_spotify-connect._tcp.local.`
- `_http._tcp.local.`

Important detail:

- the Spotify Connect advertisement included `CPath=/api/stream/spotify:zeroconf`

## Confirmed LSX II API behavior

### Core HTTP API

These endpoints are confirmed to exist and respond on the live speaker:

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

This is a strong fit for a Home Assistant `DataUpdateCoordinator` plus event-assisted refresh approach.

## Live LSX II values observed

These values were observed from the real speaker during investigation:

- speaker name: `LSX II-04438c`
- MAC: `84:17:15:04:43:8C`
- speaker status: `powerOn`
- source: `usb`
- volume: `80`
- mute: `false`
- play mode: `normal`
- firmware version: `2.6.120.0xfb95307`
- release text: `LSXII_V26120`
- model name node: `SP4041`

Playback data from `player:player/data` was richer than the current Home Assistant integration model:

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

This is already much richer than the first-generation KEF DSP model exposed by `aiokef`.

## Community HTTP API Findings

Community HTTP API research targets the LSX II-era device family, including:

- LS50 Wireless II
- LSX II
- LS60

The useful overlap is the same local HTTP path family confirmed on the live speaker, including:

- `player:volume`
- `player:player/data`
- `player:player/data/playTime`
- `settings:/kef/play/physicalSource`
- `settings:/kef/host/speakerStatus`
- `settings:/system/primaryMacAddress`
- `settings:/deviceName`
- `settings:/releasetext`

The important implementation lesson is to treat those paths as useful signals, not as a one-to-one Home Assistant entity contract:

- the documented source list appears stale for LSX II, because the live device reported `usb`
- some helper methods assume fields like `status.duration` always exist, which is not true for every input type
- the polling queue handling is useful, but we should wrap it more defensively in a Home Assistant integration

## Suggested integration design

### One integration, two backends

Create one HACS integration, ideally still under the `kef` concept, but with an internal backend split:

- `legacy_aiokef.py`
- `modern_nsdk.py`

Use model and protocol detection during setup:

1. try LSX II-era HTTP API first
2. if that succeeds, classify as `modern`
3. otherwise try the legacy `aiokef` transport
4. if that succeeds, classify as `legacy`

### Config flow

The config flow should:

- support manual host entry
- support zeroconf discovery through AirPlay / HTTP / Spotify Connect records
- fetch a stable identifier during setup
- deduplicate by stable identifier rather than host
- update host automatically if the same device appears on a new IP

For modern devices, likely stable identifiers are:

- `settings:/system/primaryMacAddress`
- AirPlay serial data from mDNS

For legacy devices, keep using the established MAC-based identity strategy.

### Entities to expose for modern KEF

Minimum first pass:

- `media_player`
- source selection
- volume and mute
- play / pause / next / previous where supported
- firmware version in device info

Useful second pass:

- sensors for current source, play mode, service id
- optional diagnostics for raw playback metadata
- select / switch / number entities backed by `kef:eqProfile`

Possible EQ entities:

- desk mode
- wall mode
- phase correction
- bass extension
- balance
- treble amount
- high-pass mode
- high-pass frequency
- subwoofer gain
- subwoofer polarity
- low-pass frequency

### Polling model

Recommended approach:

- normal state refresh through a `DataUpdateCoordinator`
- optional event queue listener to shorten latency
- periodic full refresh to recover from missed events

This is safer than relying only on long-poll events.

## What to build next

1. Create a reusable modern KEF client for the NSDK HTTP API.
2. Model the confirmed nodes with typed parsers and tolerant handling for missing fields.
3. Add a second backend adapter for legacy `aiokef`.
4. Build a Home Assistant custom integration on top with config flow, discovery, and tests.
5. Add fixture-driven tests from both:
   - first-generation responses
   - live LSX II response samples

## Practical recommendation

Do not try to extend the current Home Assistant core KEF integration in place first.

The cleaner path is:

- build a modern HACS integration with dual backend support
- validate it on the real LSX II
- add legacy support cleanly
- only then decide whether any part of it is suitable to upstream to Home Assistant core

The core integration can still be a useful reference for legacy speaker behavior, but it is not the right architecture for LSX II-class devices.
