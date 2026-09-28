# KEF API notes

How modern KEF speakers talk to the integration, independent of the model.
Per-model behaviour is in [model notes](model-notes.md).

These notes combine live observations from an LSX II (firmware
`3.0.137.0xf884312`), an LSX II LT (`2.1.86.0xdc74e88`), and an XIO
(`1.4.135.0xd4e9dfd`) in September 2026 with the API path list of the KEF
Connect Android app 1.31.0. Earlier observations are dated where they matter.
They are not a statement about other firmware. Network addresses and device
identifiers are omitted.

The integration and reusable `kef_client` are implemented. See
[configuration](configuration.md), [device support](device-support.md), and the
[Python library](python-library.md) for current use. Remaining work is in
[open KEF development work](feature-checklist.md).

## Two protocol families

The legacy backend uses `aiokef` over TCP port `50001` for first-generation
speakers. Modern speakers refuse that transport and instead expose the HTTP API
used by their built-in web interface. Keep the two backends distinct; do not
assume settings or playback commands behave identically across them.

## Discovery

Modern speakers advertise `_airplay._tcp`, `_raop._tcp`, `_http._tcp`, and
`_spotify-connect._tcp` over mDNS. The Spotify Connect record carries
`CPath=/api/stream/spotify:zeroconf`. The integration discovers speakers through
`_airplay._tcp` and matches them by its `deviceid` property. The AirPlay record
does not reliably carry a per-speaker name, so the name is read from
`settings:/deviceName` instead.

## HTTP API

| Endpoint | Use |
| --- | --- |
| `GET /api/getData?path=<path>&roles=value` | Read one value |
| `GET /api/getRows?path=<path>` | Read a list: `network:scan_results`, `playlists:pq/getitems`, `notifications:/display/queue` |
| `POST /api/setData` | Write a value, or activate an action path |
| `POST /api/event/modifyQueue` | Create an event subscription |
| `GET /api/event/pollQueue` | Wait for subscribed changes |

`setData` takes a JSON body with `path`, `role` (`value` or `activate`), and
`value`. Current firmware on every tested model expects `POST`; older firmware
accepted `GET` for writes.

Values are typed objects such as `{"type": "bool_", "bool_": true}`. Plain types
are `bool_`, `i16_`, `i32_`, `i64_`, `double_`, and `string_`; enumerations use
named types, for example `kefStandbyMode` or `kefPhysicalSource`. Some responses
carry an extra `stability` field (always `0` so far, meaning unknown).

A path that does not exist on a model or firmware returns HTTP 500. The app knows
paths for every model, so a 500 usually means "not on this speaker", not a
malformed request. A path that answers is not proof the model uses it; see
[model notes](model-notes.md#shared-firmware-and-schema).

## Authentication

`settings:/webserver/authMode` reports `none`, `setData`, or `all`:

- `none`: reads and writes are open.
- `setData`: reads are open; writes must be signed. All three tested speakers
  report this mode, and an unsigned write returns 401.
- `all`: reads must be signed as well.

Signed requests use an `Authorization: HMAC_SHA256_AES256 ...` header with a
per-request salt; the key is SHA-256 of the salt and the web interface
password, and written values are AES-256 encrypted. A speaker without a web
interface password accepts an empty password. The client reads the mode first
and only signs what the mode requires.

The KEF Connect app also uses a separate encrypted connection on port 4430 for
some settings, including selecting the XIO's KW2 wireless subwoofer. Writing
the matching fields over the HTTP API returns 403, so those settings are not
available to the integration.

## Event queue

`modifyQueue` takes a list of paths to subscribe to and returns a queue id.
`pollQueue?queueId=<id>&timeout=<seconds>` returns pending events, or holds the
request open for up to `timeout` seconds until one arrives. The client read
timeout must allow for that hold time. With a shorter timeout, every poll on an
idle speaker is cut off and the queue never delivers anything.

A playing speaker sends a `player:player/data/playTime` update about every
second, so its polls return quickly. An idle speaker holds each poll for the
full timeout. After an error, create a new queue before polling again.

## Offline speakers and name lookups

Speakers are usually configured by their `.local` host name. Once a speaker is
switched off, looking that name up takes several seconds to fail (the mDNS
lookup and a DNS fallback). If the request timeout also covers the lookup, the
request is cancelled first and the lookup's own failure is reported later,
outside the request. Limit connecting and reading instead, and let the lookup
fail on its own.

A speaker announces itself over zeroconf (`_airplay._tcp`) when it powers up,
so a discovery announcement is a reliable signal to retry an offline speaker.

## EQ profiles

`kef:eqProfile` returns a structured object:

- `isExpertMode`, `profileName`, `profileId`
- `dspInfo.trebleAmount`, `dspInfo.bassExtension`, `dspInfo.balance`,
  `dspInfo.phaseCorrection`, `dspInfo.audioPolarity`
- `dspInfo.deskMode`, `dspInfo.deskModeSetting`, `dspInfo.wallMode`,
  `dspInfo.wallModeSetting`
- `dspInfo.highPassMode`, `dspInfo.highPassModeFreq`
- `dspInfo.subwooferCount`, `dspInfo.subwooferGain`, `dspInfo.subwooferPreset`,
  `dspInfo.subwooferPolarity`, `dspInfo.subOutLPFreq`,
  `dspInfo.subEnableStereo`, `dspInfo.isKW1`

`kef:eqProfile/v2` returns a flat `kefEqProfileV2` object with the same fields
plus `subwooferOut`, `soundProfile`, `dialogueMode`, `wallMounted`,
`wirelessSub`, and `isEqMode`. The LSX II, LSX II LT, and XIO return the same
27 fields. Older firmware lacked some of them: in late 2025 an LSX II on
`2.5.110` did not report `soundProfile`, `wallMounted`, or `stability`.

The two versions encode values differently. v2 carries physical units; v1
carries step indices that the client converts:

| Field | v2 | v1 on the wire |
| --- | --- | --- |
| `balance` | -30 to 30 | 0 to 60, offset by 30 |
| `trebleAmount` | -3 to 3 dB, 0.25 dB steps | 0 to 16, 0.375 dB steps |
| `subwooferGain` | -10 to 10 dB | 0 to 20, offset by 10 |
| `highPassModeFreq` | 50 to 120 Hz, 5 Hz steps | 0 to 10, as 50 + 5 Hz per step (up to 100 Hz) |
| `deskModeSetting`, `wallModeSetting` | -10 to 0 dB, 0.5 dB steps | 0 to 20, 0.5 dB per step from -10 dB |
| `subOutLPFreq` | 40 to 250 Hz, 5 Hz steps | Hz divided by 10 |

The speaker holds only the active profile, not a library of saved profiles. The
KEF Connect app stores its profiles on the phone. Renaming the active profile
keeps its `profileId`.
`settings:/kef/eqProfile/profileName`, `settings:/kef/eqProfile/isExpertMode`,
and `kef:dspInfo` returned 500 on all three speakers in September 2026, although
`kef:dspInfo` answered on late-2025 firmware.

## Volume settings

`settings:/kef/host/defaultVolumeGlobal` and the per-input
`defaultVolumeWifi`, `defaultVolumeBluetooth`, `defaultVolumeOptical`,
`defaultVolumeCoaxial`, `defaultVolumeUSB`, `defaultVolumeAnalogue`, and
`defaultVolumeTV` hold the startup volumes. `standbyDefaultVol` turns the
startup volume on; when off, the speaker resumes at its last volume.
`advancedStandbyDefaultVol` chooses between one volume for all inputs (`false`)
and a volume per input (`true`). The firmware accepts every input name on every
model, so only the inputs a model has are meaningful.

`maximumVolume`, `volumeStep`, and `volumeLimit` set the volume ceiling, the
step per button press, and whether the ceiling is enforced;
`remote/userFixedVolume` holds the fixed volume level.

## Playback data

`player:player/data` describes the current session:

- `state`, for example `playing` or `stopped`
- `trackRoles.title`, and `trackRoles.icon` for artwork
- `trackRoles.mediaData.metaData`: `artist`, `album`, `albumArtist`, `serviceID`
- `trackRoles.mediaData.activeResource`: `codec`, `sampleFrequency`,
  `streamSampleRate`, `streamChannels`, `nrAudioChannels`
- `controls`: `pause`, `next_`, `previous`, which say what the current source
  allows
- `playId.systemMemberId`

Physical inputs report the input name as the title and no duration, artist, or
seek position. Artwork is an `http` URL for streaming sources (for AirPlay, a
file served by the speaker itself); the XIO's TV input reports a firmware skin
reference instead, see [model notes](model-notes.md#xio). A
`player:player/data/playTime` of `-1` means no position. The older paths
`player:playStatus`, `player:nowPlaying`, and `player:queue` returned 500 in
late 2025 and are no longer in the app.

## Path catalogue

The paths the integration reads and writes are listed in
`custom_components/kef/const.py` (`PROBE_PATHS`). The KEF Connect app 1.31.0
names 189 paths. These are the ones not used by the integration, with
what the three tested speakers returned for a plain read.

| Area | Paths | Observed |
| --- | --- | --- |
| Power | `powermanager:target` | `powerTarget` with `target` (`online` or `networkStandby`) and `reason` |
| Power | `powermanager:targetRequest`, `powermanager:goReboot` | Action paths, not probed |
| Scheduled reboot | `settings:/kef/scheduledReboot/enabled`, `/dayOfWeek`, `/time` | Present on all three; off, day `1`, `03:00` by default |
| Bluetooth | `bluetooth:state` | `bluetoothState` with `connected`, `discoverable`, `pairable`, and the speaker's name |
| Bluetooth | `bluetooth:disconnect`, `bluetooth:externalDiscoverable`, `bluetooth:clearAllDevices` | Action paths, not probed |
| Grouping | `grouping:members`, `grouping:savePersistentGroup` | `null` on the LSX II models when ungrouped; 500 on the XIO |
| Notifications | `notifications:/display/cancel` | Action path; `notifications:/display/queue` is empty in normal use |
| Alarms and timers | `alerts:/timer/add`, `/timer/remove`, `/alarm/add`, `/alarm/remove`, `/alarm/enable`, `/alarm/disable`, `/alarm/remove/all`, `/alarm/snooze`, `alerts:/stop`, `alerts:/defaultSound/play`, `/defaultSound/stop` | Action paths, not probed; `alerts:/list` is read by the integration |
| Volume | `settings:/kef/host/volumeDisplay` | `kefVolumeDisplay`, `linear` on all three |
| Volume | `hostlink:defaultVolume/set` | Action path, not probed |
| DSP | `settings:/kef/dsp/<field>` for each EQ field, e.g. `trebleAmount`, `deskMode`, `subwooferGain` | 500 on the LSX II LT and XIO. The LSX II answers only `trebleAmount`, `deskMode`, `deskModeSetting`, and `subwooferGain`, as v1 step indices. Use the EQ profile instead |
| DSP | `settings:/kef/dsp/v2/dialogueMode`, `settings:/kef/dsp/v2/subwooferOut` | Readable booleans on all three, matching the EQ profile |
| DSP | `kef:dsp/editValue` | Action path, not probed |
| Playback | `imx8af:decoderInfoCodecString` | XIO only; the same string as `activeResource.codec` |
| Google Cast | `settings:/googleCastLite/tosAccepted`, `settings:/googleCastLite/usageReport` | Readable booleans |
| Google Cast | `settings:/googlecast/tosAccepted`, `googlecast:usageReport`, `googlecast:setUsageReport` | The settings path returns 500 |
| Remote | `settings:/kef/host/remote/speakerIRCode` | `ir_code_set_a`, like `remoteIRCode` |
| Remote | `settings:/kef/host/remote/remoteDiagnosisStatus`, `/changeSpeakerIRCodeStatus` | Status values, `idle` |
| Other settings | `settings:/kef/host/iptSwitch` | `true` on the XIO, `false` on the LSX II models; purpose unknown |
| Other settings | `settings:/imx8AudioFramework/afInStandby` | `false` on all three |
| Other settings | `settings:/kef/dsp/bleLatencyCompensation` | `presentationDelay20` on all three |
| Other settings | `settings:/kef/host/appLocation` | The app's region code, separate from `speakerLocation` |
| Other settings | `settings:/airable/language`, `settings:/airplay/addedToHome`, `settings:/huaweiHiMusic/enabled` | Readable |
| Identity | `settings:/system/memberId` | Model prefix (`lsxii-`, `lsxlite-`, `xio-`) plus a UUID |
| Identity | `settings:/kef/host/firmwareVersion` | Undecodable string; use `settings:/version` |
| EQ profile | `settings:/kef/eqProfile/profileId` | 500 on all three, like `profileName` and `isExpertMode` |
| Network | `kef:network/pingInternetActivate`, `kef:speedTest/start`, `kef:speedTest/stop` | Action paths that start or stop the ping and speed test, not probed |
| Other | `ui:` | `null` on all three |
| XIO wireless subwoofer | `kefdsp:channelIdSignal` | Action path, not probed |
| Firmware | `kef:fwupgrade/info` | Per-component progress, for example `systemMCU`, `usb`, `topPanel`, `bTLE` |
| Network | `networkwizard:wireless/scan_activate`, `networkwizard:wireless/scan_results`, `network:scan`, `network:setNetworkProfile` | Setup paths, not probed |
| Wireless rear speakers | `settings:/kef/dsp/wirelessRearMode`, `settings:/kef/dsp/wirelessRearGain` | Readable defaults (`surround`, `0`) on all three |
| Wireless rear speakers | `settings:/kef/host/surroundMode`, `settings:/kef/dsp/surroundMode/deviceList`, `hostlink:/surroundMode/*`, `kefdsp:/surroundMode/*` | The settings paths return 500; for hardware KEF has not released yet |
| XIO wireless subwoofer | `kef:ble/*`, `kefdsp:bleTx01ChannelAssignment`, `kefdsp:bleTx02ChannelAssignment`, `kefdsp:txStatus`, `settings:/kef/ble/txFwVersion` | See [model notes](model-notes.md#wireless-subwoofer); do not activate update checks |

Some paths change or erase speaker state and should never be called casually:
`kef:speakerFactoryReset`, `kef:restoreDspSettings` and
`kef:restoreDspSettings/v2`, `powermanager:goReboot`,
`systemmanager:/createLogFile`, and `kefdsp:/calibration/start` or `/stop`.
`networkwizard:wireless/key` returns Wi-Fi credentials. In late 2025,
`kef:restoreDspSettings/v2` reset the EQ and placement settings but not the
network settings or streaming accounts.

`settings:/kef/host/displayBrightness`, `ledBrightness`, and `doNotDisturb`
returned 500 on every model in late 2025 and are no longer in the app.

The integration reads the speaker location from
`settings:/kef/host/speakerLocation`; the app uses `kef:speakerLocation`. Both
return the same value.

## Complete path list

Every path the KEF Connect Android app 1.31.0 names, grouped by prefix. A path
being listed says nothing about which models implement it; what the unused ones
returned on real speakers is in the [path catalogue](#path-catalogue).

The Integration column shows how the integration covers each path:

- ✓: the integration reads or writes this path directly (75 paths).
- ✓ via EQ profile: the setting is available as an entity, but the integration
  reads and writes it as a field of `kef:eqProfile/v2`, not through this path
  (19 paths). The individual DSP paths mostly return 500.
- Empty: not used by the integration (95 paths).

### `settings:/kef/host/`

| Path | Integration |
| --- | --- |
| `settings:/kef/host/advancedStandbyDefaultVol` | ✓ |
| `settings:/kef/host/appLocation` |  |
| `settings:/kef/host/autoDetectPlacement` | ✓ |
| `settings:/kef/host/autoSwitchToHDMI` | ✓ |
| `settings:/kef/host/cableMode` | ✓ |
| `settings:/kef/host/defaultVolumeAnalogue` | ✓ |
| `settings:/kef/host/defaultVolumeBluetooth` | ✓ |
| `settings:/kef/host/defaultVolumeCoaxial` | ✓ |
| `settings:/kef/host/defaultVolumeGlobal` | ✓ |
| `settings:/kef/host/defaultVolumeOptical` | ✓ |
| `settings:/kef/host/defaultVolumeTV` | ✓ |
| `settings:/kef/host/defaultVolumeUSB` | ✓ |
| `settings:/kef/host/defaultVolumeWifi` | ✓ |
| `settings:/kef/host/disableAnalytics` | ✓ |
| `settings:/kef/host/disableAppAnalytics` | ✓ |
| `settings:/kef/host/disableFrontLED` | ✓ |
| `settings:/kef/host/disableFrontStandbyLED` | ✓ |
| `settings:/kef/host/disableTopPanel` | ✓ |
| `settings:/kef/host/firmwareVersion` |  |
| `settings:/kef/host/hardwareVersion` | ✓ |
| `settings:/kef/host/iptSwitch` |  |
| `settings:/kef/host/kefId` | ✓ |
| `settings:/kef/host/masterChannelMode` | ✓ |
| `settings:/kef/host/maximumVolume` | ✓ |
| `settings:/kef/host/modelName` | ✓ |
| `settings:/kef/host/remote/changeSpeakerIRCodeStatus` |  |
| `settings:/kef/host/remote/eqButton1` | ✓ |
| `settings:/kef/host/remote/eqButton2` | ✓ |
| `settings:/kef/host/remote/favouriteButton` | ✓ |
| `settings:/kef/host/remote/remoteDiagnosisStatus` |  |
| `settings:/kef/host/remote/remoteIR` | ✓ |
| `settings:/kef/host/remote/remoteIRCode` | ✓ |
| `settings:/kef/host/remote/speakerIRCode` |  |
| `settings:/kef/host/remote/userFixedVolume` | ✓ |
| `settings:/kef/host/serialNumber` | ✓ |
| `settings:/kef/host/speakerStatus` | ✓ |
| `settings:/kef/host/standbyDefaultVol` | ✓ |
| `settings:/kef/host/standbyMode` | ✓ |
| `settings:/kef/host/startupTone` | ✓ |
| `settings:/kef/host/subwooferForceOn` | ✓ |
| `settings:/kef/host/subwooferForceOnKW1` | ✓ |
| `settings:/kef/host/surroundMode` |  |
| `settings:/kef/host/topPanelLED` | ✓ |
| `settings:/kef/host/topPanelStandbyLED` | ✓ |
| `settings:/kef/host/usbCharging` | ✓ |
| `settings:/kef/host/volumeDisplay` |  |
| `settings:/kef/host/volumeLimit` | ✓ |
| `settings:/kef/host/volumeStep` | ✓ |
| `settings:/kef/host/wakeUpSource` | ✓ |

### `settings:/kef/dsp/`

| Path | Integration |
| --- | --- |
| `settings:/kef/dsp/balance` | ✓ via EQ profile |
| `settings:/kef/dsp/bassExtension` | ✓ via EQ profile |
| `settings:/kef/dsp/bleLatencyCompensation` |  |
| `settings:/kef/dsp/calibrationResult` | ✓ |
| `settings:/kef/dsp/calibrationStatus` | ✓ |
| `settings:/kef/dsp/calibrationStep` |  |
| `settings:/kef/dsp/deskMode` | ✓ via EQ profile |
| `settings:/kef/dsp/deskModeSetting` | ✓ via EQ profile |
| `settings:/kef/dsp/highPassMode` | ✓ via EQ profile |
| `settings:/kef/dsp/highPassModeFreq` | ✓ via EQ profile |
| `settings:/kef/dsp/isKW1` | ✓ via EQ profile |
| `settings:/kef/dsp/phaseCorrection` | ✓ via EQ profile |
| `settings:/kef/dsp/preferVirtualX` | ✓ |
| `settings:/kef/dsp/subEnableStereo` | ✓ via EQ profile |
| `settings:/kef/dsp/subOutLPFreq` | ✓ via EQ profile |
| `settings:/kef/dsp/subwooferCount` | ✓ via EQ profile |
| `settings:/kef/dsp/subwooferGain` | ✓ via EQ profile |
| `settings:/kef/dsp/subwooferPolarity` | ✓ via EQ profile |
| `settings:/kef/dsp/subwooferPreset` | ✓ via EQ profile |
| `settings:/kef/dsp/surroundMode/deviceList` |  |
| `settings:/kef/dsp/trebleAmount` | ✓ via EQ profile |
| `settings:/kef/dsp/v2/dialogueMode` |  |
| `settings:/kef/dsp/v2/soundProfile` | ✓ via EQ profile |
| `settings:/kef/dsp/v2/subwooferOut` | ✓ via EQ profile |
| `settings:/kef/dsp/wallMode` | ✓ via EQ profile |
| `settings:/kef/dsp/wallModeSetting` | ✓ via EQ profile |
| `settings:/kef/dsp/wirelessRearGain` |  |
| `settings:/kef/dsp/wirelessRearMode` |  |

### Other `settings:/`

| Path | Integration |
| --- | --- |
| `settings:/airable/bitrate` | ✓ |
| `settings:/airable/language` |  |
| `settings:/airplay/addedToHome` |  |
| `settings:/alerts/snoozeTime` | ✓ |
| `settings:/deviceName` | ✓ |
| `settings:/googleCastLite/tosAccepted` |  |
| `settings:/googleCastLite/usageReport` |  |
| `settings:/googlecast/tosAccepted` |  |
| `settings:/huaweiHiMusic/enabled` |  |
| `settings:/imx8AudioFramework/afInStandby` |  |
| `settings:/kef/ble/txFwVersion` |  |
| `settings:/kef/eqProfile/isExpertMode` |  |
| `settings:/kef/eqProfile/profileId` |  |
| `settings:/kef/eqProfile/profileName` |  |
| `settings:/kef/play/physicalSource` | ✓ |
| `settings:/kef/scheduledReboot/dayOfWeek` |  |
| `settings:/kef/scheduledReboot/enabled` |  |
| `settings:/kef/scheduledReboot/time` |  |
| `settings:/mediaPlayer/mute` | ✓ |
| `settings:/mediaPlayer/playMode` | ✓ |
| `settings:/releasetext` | ✓ |
| `settings:/system/memberId` |  |
| `settings:/system/primaryMacAddress` | ✓ |
| `settings:/ui/language` | ✓ |
| `settings:/version` | ✓ |

### `kef:`

| Path | Integration |
| --- | --- |
| `kef:ble/checkForUpdates` |  |
| `kef:ble/checkForUpdatesRx` |  |
| `kef:ble/checkForUpdatesTx` |  |
| `kef:ble/getReport` |  |
| `kef:ble/ui` |  |
| `kef:ble/updateLater` |  |
| `kef:ble/updateNow` |  |
| `kef:ble/updateServer/txVersion` |  |
| `kef:ble/updateStatus` |  |
| `kef:dsp/editValue` |  |
| `kef:dspInfo` |  |
| `kef:eqProfile` | ✓ |
| `kef:eqProfile/v2` | ✓ |
| `kef:fwupgrade/info` |  |
| `kef:network/pingInternet` | ✓ |
| `kef:network/pingInternetActivate` |  |
| `kef:network/pingInternetStability` | ✓ |
| `kef:restoreDspSettings` |  |
| `kef:restoreDspSettings/v2` |  |
| `kef:speakerFactoryReset` |  |
| `kef:speakerLocation` |  |
| `kef:speedTest/averageDownloadSpeed` | ✓ |
| `kef:speedTest/currentDownloadSpeed` | ✓ |
| `kef:speedTest/packetLoss` | ✓ |
| `kef:speedTest/start` |  |
| `kef:speedTest/status` | ✓ |
| `kef:speedTest/stop` |  |

### `kefdsp:` and `hostlink:`

| Path | Integration |
| --- | --- |
| `hostlink:/surroundMode/recentlyAddedDevice` |  |
| `hostlink:/surroundMode/rxChannelModeChangeRequest` |  |
| `hostlink:/surroundMode/rxChannelModeForceChange` |  |
| `hostlink:/surroundMode/rxCheckStatus` |  |
| `hostlink:/surroundMode/txPowerToggle` |  |
| `hostlink:/surroundMode/txStartBroadcast` |  |
| `hostlink:defaultVolume/set` |  |
| `kefdsp:/calibration/start` | ✓ |
| `kefdsp:/calibration/stop` |  |
| `kefdsp:/surroundMode/addDevice` |  |
| `kefdsp:/surroundMode/removeDevice` |  |
| `kefdsp:/surroundMode/updateDeviceInfo` |  |
| `kefdsp:bleTx01ChannelAssignment` |  |
| `kefdsp:bleTx02ChannelAssignment` |  |
| `kefdsp:channelIdSignal` |  |
| `kefdsp:txStatus` |  |

### `player:` and `powermanager:`

| Path | Integration |
| --- | --- |
| `player:player/control` | ✓ |
| `player:player/data` | ✓ |
| `player:player/data/playTime` | ✓ |
| `player:volume` | ✓ |
| `powermanager:goReboot` |  |
| `powermanager:target` |  |
| `powermanager:targetRequest` |  |

### `alerts:/` and `notifications:/`

| Path | Integration |
| --- | --- |
| `alerts:/alarm/add` |  |
| `alerts:/alarm/disable` |  |
| `alerts:/alarm/enable` |  |
| `alerts:/alarm/remove` |  |
| `alerts:/alarm/remove/all` |  |
| `alerts:/alarm/snooze` |  |
| `alerts:/defaultSound/play` |  |
| `alerts:/defaultSound/stop` |  |
| `alerts:/list` | ✓ |
| `alerts:/stop` |  |
| `alerts:/timer/add` |  |
| `alerts:/timer/remove` |  |
| `notifications:/display/cancel` |  |
| `notifications:/display/queue` | ✓ |
| `notifications:/player/playing` | ✓ |

### `bluetooth:`, `grouping:`, and `googlecast:`

| Path | Integration |
| --- | --- |
| `bluetooth:clearAllDevices` |  |
| `bluetooth:disconnect` |  |
| `bluetooth:externalDiscoverable` |  |
| `bluetooth:state` |  |
| `googlecast:setUsageReport` |  |
| `googlecast:usageReport` |  |
| `grouping:members` |  |
| `grouping:savePersistentGroup` |  |

### `firmwareupdate:`, `network:`, and `networkwizard:`

| Path | Integration |
| --- | --- |
| `firmwareupdate:checkForUpdate` | ✓ |
| `firmwareupdate:downloadNewUpdate` | ✓ |
| `firmwareupdate:updateStatus` | ✓ |
| `network:info` | ✓ |
| `network:scan` |  |
| `network:scan_results` |  |
| `network:setNetworkProfile` |  |
| `networkwizard:wireless/key` |  |
| `networkwizard:wireless/scan_activate` |  |
| `networkwizard:wireless/scan_results` |  |

### Other

| Path | Integration |
| --- | --- |
| `imx8af:decoderInfoCodecString` |  |
| `imx8af:decoderInfoVirtualXActive` | ✓ |
| `systemmanager:/createLogFile` |  |
| `ui:` |  |

The integration also uses three paths the app does not name: `firmwareupdate:installUpdate`, `settings:/kef/host/speakerLocation`, and `settings:/webserver/authMode`.

## Fixture guidance

Capture partially populated playback responses as well as streaming metadata.
An external input may have no track title, duration, seek position, or artwork.
Treat device-advertised controls and available settings as the capability
contract, and retain polling recovery when the event queue disconnects.
