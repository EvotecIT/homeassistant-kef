# Configuration and troubleshooting

[Back to the README](../README.md) · [Device support](device-support.md)

## Connect a speaker

Accept Home Assistant's discovered KEF device, or add **KEF** from **Settings →
Devices & services** and enter the host/IP address. Keep the speaker reachable
on your local network.

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

Open the integration's **Configure** dialog.

| Option | Default and purpose |
| --- | --- |
| Speaker password | Used when the local web/API interface requires authentication |
| Polling interval | 10 seconds; accepts 5–120 seconds |
| Diagnostics | Off by default; enables optional diagnostic entities |

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
no notes.

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
