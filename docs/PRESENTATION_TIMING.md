# Presentation timing and block boundaries

[English](PRESENTATION_TIMING.md) | [Japanese](PRESENTATION_TIMING.ja.md)

All stimulus families use the same `AbsoluteTimeline` and presentation loop. The first actual flip defines `t0`, which remains fixed throughout the run. With 4 seconds of initial fixation and 60-second cycles, cycle targets are `t0 + 4`, `t0 + 64`, `t0 + 124`, and so on.

Before each flip, the loop subtracts `t0` from PsychoPy's predicted next-refresh time and selects the stimulus state for that cumulative elapsed time. The measured end of one block is never used to calculate the next block's target. A delay is therefore not added to later deadlines.

If the actual display is slightly faster than the nominal 60 Hz, a state can be held for another refresh. If it is slower, or a frame is delayed, the loop advances to the state appropriate to the current elapsed time. The nominal frame index is not forced to increase by one at every physical flip. This also avoids increasing timing error caused by small refresh-rate differences.

## Targets for each stimulus family

| Family | Cumulative target relative to run onset |
|---|---|
| Wedge and annulus | Initial fixation + cycle index x `cycle_s` |
| Bar | Initial fixation + sweep index x `cycle_s`; each sweep includes its rest period |
| Combined wedge and annulus | Independent polar-angle and eccentricity cycles calculated from the same `t0` |
| Multifocal | Initial fixation + trial index x `trial_s` |
| Meridian, LGN, and eccentricity localizer | Initial fixation + block index x `block_s` |
| HRF | Initial fixation + cycle index x `cycle_s` |

Aperture-position changes are selected from the complete schedule on the same cumulative clock. Physical display times are quantized to refreshes, so rounding to a display frame still introduces an error. Verify the time at which light reaches the observer separately, for example with a photodiode.

## Saved timing records

`block_timing.tsv` contains these columns:

| Column | Meaning |
|---|---|
| `series` / `block` | Boundary series and cycle, sweep, trial, or block index |
| `planned_onset_s` | Continuous target time relative to `t0` |
| `scheduled_onset_s` | Target assigned to a nominal refresh slot |
| `actual_onset_s` | Measured flip time that displayed the corresponding state |
| `error_s` | Actual minus planned onset; negative values indicate an early onset |
| `frame` | Physical flip index |

`events.tsv` also records `planned_onset` and `onset_error_s` for individual stimulus states. `summary.json` reports the largest absolute boundary error in `block_timing.max_abs_error_s`. Actual flip counts and nominal frame counts can differ when actual and nominal refresh rates differ; run duration and boundaries still follow cumulative elapsed time.

## Checking an acquisition

Plot `error_s` against the block index or `planned_onset_s`. Check that errors do not increase toward the end of the run and remain within the tolerance required by the experiment. Boundaries not reached in an aborted run are recorded as `n/a`.

The automated timing tests simulate 20-minute displays at 59, 59.94, 60.06, and 61 Hz against a nominal 60 Hz, checking that errors at 60-second boundaries do not accumulate. They also simulate a 1.4-second interruption and check that its delay is not carried into later blocks.

Measured times in these logs are PsychoPy synchronization timestamps, not optical measurements. Check timing on the intended apparatus using the normal run duration and stimulus conditions.
