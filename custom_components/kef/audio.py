"""Shared audio presentation helpers for KEF entities."""

from __future__ import annotations

from .models import KefSnapshot


def format_channels(channel_count: int | str | None) -> str | None:
    """Convert a channel count to audio format notation (for example, 5.1.2)."""
    if channel_count is None:
        return None

    if isinstance(channel_count, str):
        channel_count = channel_count.strip()
        if not channel_count:
            return None
        try:
            channel_count = int(channel_count)
        except ValueError:
            return None if channel_count == "0.0" else channel_count

    if channel_count <= 0:
        return None
    channel_map = {2: "2.0", 6: "5.1", 8: "5.1.2"}
    return channel_map.get(channel_count, str(channel_count))


def audio_codec_value(data: KefSnapshot) -> str | None:
    """Return the decoded audio codec with channel format."""
    if data.playback is None or not data.playback.codec:
        return None
    codec_name = (
        data.playback.codec.split(" - ")[0]
        if " - " in data.playback.codec
        else data.playback.codec
    )
    if codec_name == "Dolby PCM":
        codec_name = "PCM"
    channel_format = format_channels(data.playback.stream_channels)
    if channel_format:
        return f"{codec_name} {channel_format}"
    return codec_name


def audio_virtualizer_value(data: KefSnapshot) -> str | None:
    """Return the decoded audio virtualizer mode with channel format."""
    if data.playback is None or not data.playback.codec:
        return None
    virtualizer_name = (
        data.playback.codec.split(" - ")[1]
        if " - " in data.playback.codec
        else "Direct"
    )
    if virtualizer_name == "Direct":
        channel_format = format_channels(data.playback.stream_channels)
        if channel_format is None:
            channel_format = format_channels(data.playback.audio_channels)
    else:
        channel_format = format_channels(8)
    if channel_format:
        return f"{virtualizer_name} {channel_format}"
    return virtualizer_name
