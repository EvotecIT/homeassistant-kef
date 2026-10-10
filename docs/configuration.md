# Configuration and troubleshooting

[Back to the README](../README.md) · [Device support](device-support.md)

## Connect a speaker

Accept Home Assistant's discovered KEF device, or add **KEF** from **Settings →
Devices & services** and enter the host/IP address. Keep the speaker reachable
on your local network. Modern speakers use their local HTTP API on TCP port 80;
first-generation speakers use the IPv4 binary API on TCP port 50001. Discovery
uses the speaker's AirPlay/Bonjour announcement. Across network segments, allow
the required local traffic and make sure Home Assistant can resolve any `.local`
hostname you enter.

| Setup field | Required | Purpose |
| --- | --- | --- |
| Host | Yes for manual setup; supplied by discovery otherwise | Speaker IP address or resolvable hostname |
| Speaker password | Only when the local API requires it | Password for the speaker's web interface; blank by default |

First-generation LSX and LS50 Wireless speakers use the passwordless legacy
protocol. Leave the password blank when adding one manually. When discovery
identifies a legacy speaker, its confirmation form has no password field.

If the speaker's web UI is password-protected, enter that password during setup.
This is the speaker web-interface password, not a request to put your credentials
into YAML. Firmware updates that enable authentication can trigger a Home
Assistant reauthentication prompt.

Modern speakers found through Bonjour use their `.local` hostname so Home
Assistant can try IPv4 or IPv6 and follow address changes. If an older entry
still points to an unreachable IP address, use **Reconfigure** and enter the
speaker's advertised `.local` hostname. The speaker must be reachable during
reconfiguration. Modern speakers must match the existing entry. First-generation
speakers continue to use IPv4 for their binary control protocol. Their existing entries
learn a stable AirPlay identifier when rediscovered at the saved address, then
can follow later IPv4 changes. If the address changed before that rediscovery,
use **Reconfigure** with the current IPv4 address and confirm it belongs to
the same speaker; the legacy binary API does not provide a stable device ID.

## Options

Open the integration's **Configure** dialog. Saving options reloads the entry;
its entities retain their identities. Use **Reconfigure** to change the host.

| Option | Default and purpose |
| --- | --- |
| Speaker password | Used when the local web/API interface requires authentication |
| Polling interval | 10 seconds; accepts 5–120 seconds |
| Offline retry interval | 60 seconds; accepts 30–600 seconds. How often an offline speaker is retried |
| Diagnostics | Off by default; enables optional diagnostic entities |

## Data updates

The integration reads a speaker snapshot every 10 seconds by default. The
polling option accepts whole seconds from 5 to 120. A snapshot can require
several local API requests; the interval is not a per-request rate limit.

Modern speakers also have an event-queue listener. An event requests a fresh
snapshot between scheduled polls, so a change can appear before the next poll.
Polling continues alongside the listener and remains available if the event
queue fails. Legacy speakers use polling without this event listener.

Shorter intervals increase requests to the speaker. Leave the default unless
you need a different update cadence; no measured per-model request budget is
currently published. Network latency, retries, and speaker response time affect
when Home Assistant receives a fresh state.

### Offline speakers

A speaker on a switched-off power strip or desk socket goes offline without
warning. One or two missed polls keep the last known state, so a brief network
hiccup does not flip every entity to unavailable. After three missed polls in a
row the entities become unavailable and the integration retries at the offline
retry interval instead of the polling interval. The live event queue pauses
while the speaker is offline. Home Assistant logs one error when the speaker
goes offline and one message when it comes back.

When a discovery announcement matches an existing offline entry, the integration
requests a refresh without waiting for the offline retry interval. If the
announcement is missed or cannot be matched, recovery uses the next scheduled
retry. During initial setup there is no previous state to retain: Home Assistant
retries setup if the first connection fails.

## Daily controls and settings

The media player provides the supported power, volume, mute, source, and playback
actions. Select the speaker from your device page when adding a dashboard or
automation; do not copy an example entity ID unchanged.

Additional entities expose supported startup-volume, standby, wake-source, LED,
hardware, privacy, streaming-quality, and regional settings. Not every family or
firmware provides every setting. Use the controls visible on your own device.

On the XIO, **Wall mounted** can only be changed while **Auto-detect placement**
is off; with auto-detect on, the soundbar sets it itself. The KEF Connect app
has no manual wall-mounted setting, so this switch is the only way to override
the detected placement. Turning auto-detect off here keeps the existing room
calibration; run **Start calibration** if the soundbar is physically moved.

## Firmware updates

The update entity exposes supported firmware updates. Use a maintenance window
and follow the speaker's update requirements.

Update availability and versions always come from the speaker itself. When the
update dialog is opened, KEF's published release notes for the reported version
are fetched from kef.com; if that page is unreachable, the dialog simply shows
no notes. **Read release announcements** opens KEF's release notes page at the
section for the speaker's model.

Once a night, and whenever **Check for updates** is used in Settings > Updates
(or the `homeassistant.update_entity` action), the integration asks the speaker
to run its own firmware check. Nothing is installed by a check. The nightly
check falls between 02:30 and 04:00 Home Assistant time, when the speakers run
their own overnight update cycle, and each speaker has its own fixed time in
that window. A speaker that is offline, or is already checking, downloading, or
installing, is not asked. The XIO's wireless
subwoofer module has its own separate update check, which this integration does
not use; check it in the KEF Connect app.

Advanced users can upload a local `.swu` using `kef.install_firmware_file`.
The action requires the KEF **update entity** in `entity_id` and a `file_path`
accessible to Home Assistant. Use a file intended for the exact speaker model;
do not run firmware installation as a routine unattended automation.

## Troubleshooting

- **Speaker not found:** check its current IP and local connectivity. Manual
  setup does not depend on discovery succeeding.
- **Read works but control fails:** check whether firmware enabled a web UI
  password, then reauthenticate or reconfigure.
- **Playback action unavailable:** check the selected source and whether that
  source exposes the action.
- **Speaker unavailable:** check whether its saved address still responds. If
  its IPv4 address times out but its `.local` hostname works, reconfigure a
  modern speaker with that hostname. The integration retries without requiring
  the speaker to be removed.

For an issue, reproduce once and download integration diagnostics. Include the
model, firmware, integration version, and the failed action. Review the file and
any logs before sharing them; never post the speaker password.

## Remove the integration

1. Disable or update automations and dashboard cards that reference the speaker.
2. Open **Settings → Devices & services → KEF**, open the menu for the speaker's
   integration entry, and choose **Delete**. Repeat for any other speakers you
   want to remove.
3. To uninstall the custom integration, delete all KEF entries first, then
   remove **KEF** in HACS. For a manual installation, remove
   `config/custom_components/kef`. Restart Home Assistant.

Entry deletion removes the HA connection configuration. KEF does not keep a
separate on-disk speaker cache. Recorder history, exported diagnostics, and
backups follow Home Assistant's retention or your own file-management settings;
they are not erased by this integration. Deletion does not factory-reset the
speaker, change its saved settings, or turn it off. It remains usable through
the vendor app and its other inputs.
