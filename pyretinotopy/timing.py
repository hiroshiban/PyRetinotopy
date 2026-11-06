"""All protocols use one immutable time origin, never chained block timers."""
import math


class AbsoluteTimeline:
    """Map the next physical flip's run-relative time to a nominal frame slot.

    Slots may repeat on a faster display or jump after a late flip. Forcing
    previous_slot + 1 would make timing drift on a faster-than-nominal display.
    A previous block's error never becomes the next block's time origin.
    """
    def __init__(self, nominal_hz):
        if not math.isfinite(nominal_hz) or nominal_hz <= 0:
            raise ValueError("Nominal refresh must be positive and finite.")
        self.hz = nominal_hz
        self.previous_slot = 0

    def slot_at(self, expected_flip_s):
        if not math.isfinite(expected_flip_s):
            raise ValueError("Expected flip time must be finite.")
        self.previous_slot = max(self.previous_slot, 0, round(expected_flip_s * self.hz))
        return self.previous_slot


def block_timing_rows(design, frames):
    """Map planned cycle/block boundaries to the actual flip that displayed them."""
    hz = design.config.display.refresh_hz
    rows = []
    index = 0
    for boundary in sorted(design.block_boundaries(), key=lambda b: b["planned_onset_s"]):
        scheduled = round(boundary["planned_onset_s"] * hz) / hz
        while index < len(frames) and frames[index]["planned_time"] < scheduled - 1e-9:
            index += 1
        frame = frames[index] if index < len(frames) else None
        actual = frame["flip_time"] if frame else None
        rows.append({**boundary, "scheduled_onset_s": scheduled,
                     "actual_onset_s": actual,
                     "error_s": actual - boundary["planned_onset_s"] if frame else None,
                     "frame": frame["frame"] if frame else None})
    return rows


def marker_on(config,segment,time_s):
    """PTB3 half-position photodiode pulse, or an explicitly fixed duration."""
    if not segment.components or time_s<segment.onset:return False
    duration=segment.duration/2 if config.display.marker_timing=="half" else config.display.marker_duration_s
    return time_s-segment.onset<duration
