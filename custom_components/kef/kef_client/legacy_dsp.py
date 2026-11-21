"""DSP values carried by the first-generation KEF TCP protocol."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .exceptions import KefConnectionError, KefResponseError
from .models import KefEqProfile

_MODE = 0x27
_VALUE_BASE = 0x80
_UNKNOWN = 0xFF
_MODE_BITS = {"desk_mode": 0x01, "wall_mode": 0x02, "high_pass_mode": 0x08}
_SUB_POLARITY = 0x40
_BASS_MASK = 0x30
_BASS_VALUES = {"less": 0x20, "standard": 0, "extra": 0x10}
_BASS_BY_BITS = {bits: value for value, bits in _BASS_VALUES.items()}


@dataclass(frozen=True, slots=True)
class LegacyDspNumber:
    """One DSP register and its ordered set of valid values."""

    register: int
    field: str
    values: tuple[int | float, ...]

    @property
    def step(self) -> float:
        """Return the increment exposed by the speaker."""
        return self.values[1] - self.values[0]

    def decode(self, response: int) -> int | float | None:
        """Decode a register value, including unknown and invalid replies."""
        index = response - _VALUE_BASE
        return self.values[index] if 0 <= index < len(self.values) else None

    def encode(self, value: float) -> int:
        """Validate and encode the exact value before opening the socket."""
        try:
            return _VALUE_BASE + self.values.index(value)
        except ValueError as err:
            raise KefResponseError(
                f"Unsupported legacy DSP value {value} for {self.field}"
            ) from err


LEGACY_DSP_NUMBERS = {
    "desk_mode_db": LegacyDspNumber(
        0x28, "desk_mode_setting", tuple(i / 2 for i in range(-12, 1))
    ),
    "wall_mode_db": LegacyDspNumber(
        0x29, "wall_mode_setting", tuple(i / 2 for i in range(-12, 1))
    ),
    "treble_amount": LegacyDspNumber(
        0x2A, "treble_amount", tuple(i / 2 for i in range(-4, 5))
    ),
    "high_pass_frequency": LegacyDspNumber(
        0x2B, "high_pass_frequency", tuple(range(50, 121, 5))
    ),
    "sub_out_low_pass_frequency": LegacyDspNumber(
        0x2C, "sub_out_low_pass_frequency", tuple(range(40, 251, 5))
    ),
    "subwoofer_gain": LegacyDspNumber(0x2D, "subwoofer_gain", tuple(range(-10, 11))),
}


class LegacyDsp:
    """Read and change DSP through the existing serialized TCP exchange."""

    def __init__(
        self,
        read: Callable[[int], Awaitable[int]],
        write: Callable[[int, int], Awaitable[None]],
    ) -> None:
        self._read = read
        self._write = write
        self._mode_lock = asyncio.Lock()

    async def async_read_profile(self) -> KefEqProfile | None:
        """Read available DSP values without depending on them for basic playback."""
        try:
            mode = await self._read(_MODE)
        except (KefConnectionError, KefResponseError):
            return None
        if not _VALUE_BASE <= mode < _UNKNOWN:
            return None

        values: dict[str, int | float | None] = {}
        for setting in LEGACY_DSP_NUMBERS.values():
            try:
                values[setting.field] = setting.decode(
                    await self._read(setting.register)
                )
            except KefConnectionError:
                # A source or power transition can interrupt the optional reads.
                # Do not wait out the remaining registers on a lost connection.
                break
            except KefResponseError:
                continue
        gain = values.get("subwoofer_gain")
        return KefEqProfile(
            api_version="legacy",
            desk_mode=bool(mode & _MODE_BITS["desk_mode"]),
            wall_mode=bool(mode & _MODE_BITS["wall_mode"]),
            high_pass_mode=bool(mode & _MODE_BITS["high_pass_mode"]),
            bass_extension=_BASS_BY_BITS.get(mode & _BASS_MASK),
            subwoofer_polarity="inverted" if mode & _SUB_POLARITY else "normal",
            desk_mode_setting=values.get("desk_mode_setting"),
            wall_mode_setting=values.get("wall_mode_setting"),
            treble_amount=values.get("treble_amount"),
            high_pass_frequency=values.get("high_pass_frequency"),
            sub_out_low_pass_frequency=values.get("sub_out_low_pass_frequency"),
            subwoofer_gain=int(gain) if gain is not None else None,
        )

    async def async_set_switch(self, field: str, enabled: bool) -> None:
        """Set one switch in the packed mode register."""
        bit = _MODE_BITS[field]
        await self._async_update_mode(bit, bit if enabled else 0)

    async def async_set_bass_extension(self, value: str) -> None:
        """Set bass extension while preserving other mode fields."""
        if value not in _BASS_VALUES:
            raise KefResponseError(f"Unsupported legacy bass extension: {value}")
        await self._async_update_mode(_BASS_MASK, _BASS_VALUES[value])

    async def async_set_subwoofer_polarity(self, value: str) -> None:
        """Set subwoofer polarity while preserving other mode fields."""
        if value not in {"normal", "inverted"}:
            raise KefResponseError(f"Unsupported legacy subwoofer polarity: {value}")
        await self._async_update_mode(
            _SUB_POLARITY, _SUB_POLARITY if value == "inverted" else 0
        )

    async def async_set_number(self, field: str, value: float) -> None:
        """Write a value to an individual DSP register."""
        setting = LEGACY_DSP_NUMBERS[field]
        await self._write(setting.register, setting.encode(value))

    async def _async_update_mode(self, mask: int, value: int) -> None:
        # Scene actions on separate HA platforms can run at the same time.
        async with self._mode_lock:
            current = await self._read(_MODE)
            if not _VALUE_BASE <= current < _UNKNOWN:
                raise KefResponseError("Legacy KEF DSP mode is unavailable")
            updated = (current & ~mask) | value
            if current != updated:
                await self._write(_MODE, updated)
