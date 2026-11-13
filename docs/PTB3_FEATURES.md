# Features carried forward from PTB3 - v0.4.0

[English](PTB3_FEATURES.md) | [Japanese](PTB3_FEATURES.ja.md)

PyRetinotopy carries forward the experimental functionality of the original Retinotopy package while replacing MATLAB Psychtoolbox 3 with Python and PsychoPy. Shared stimulus definitions, cumulative timing, advance preparation, independent random streams, and complete acquisition backups provide the corresponding behavior.

OpenAI generative AI tools, including Codex, supported source review, implementation, testing, and documentation. Hiroshi Ban, the author and responsible investigator, reviews the transfer of functionality and performs operational checks throughout development. He is responsible for the software and its release. The table below describes the feature correspondence and device-dependent limits.

The [mapping of all 96 original settings](PTB3_PARAMETER_MAP.md) explains how each setting is specified in Python.

## Feature correspondence

| Feature | Implementation | Checks and limits |
|---|---|---|
| 9 stimulus families, 14 basic modes, and 5 carrier/task variants | All 70 mode names and 10 window-export names share `Design` and `Geometry` | Continuous-coordinate aperture comparisons cover all 70 modes; exact MATLAB pixel equivalence has not been established |
| Wedge, annulus, combined, and bar starting positions and scan order | Original image coordinates, reversal of the complete ccw image sequence, 16 combined-annulus positions, and wedge precedence | Independently checked against the original formulas |
| Participant settings and default fallback | `_DEFAULT_` followed by participant overrides; partial JSON, family/mode files, and standalone saved configurations | Relative paths, precedence, and replay of older acquisitions are tested |
| Run numbers and repeated acquisitions | `--run N` is recorded in configuration, summary, acquisition metadata, and directory names | Runs 1, 2, and 3 remain separate even for the same stimulus |
| Repeating the same run | Archive the complete directory as `_old-01`, `_old-02`, etc.; save the latest attempt under the original name | Tests preserve file bytes and timestamps, other runs, and previous backups |
| Confirmation, cancellation, and abnormal termination | Confirm ID/mode/run before backup; Escape/Q aborts; failures are logged | An OS lock is held from preparation through final saving and is released on process exit |
| Fixation type 1: circle | Original circular alpha mask and foreground | Size, color, and dimmed color are configurable |
| Fixation type 2: rectangular | Frame and graduated cross from the original `CreateFixationImgMono` (`cross`) | Replaces the earlier simple-square interpretation; `square` remains an additional choice |
| Fixation type 3: concentric | Central disk, interrupted outer ring, and circular background | Replaces the earlier black concentric rings; drawing is prepared in advance |
| Fixation task | Fixation frequency, duration, regular slots, and default dimmed level of 64/255; includes initial/final fixation and rests | Choose `ptb3` or `interval`; MATLAB random sequences are not reproduced identically |
| Stimulus detection task | Half-position windows, brief localizer/HRF color or disparity windows, and luminance/depth changes in visible patches | Reaction times use actual flips; unpresented targets are not scored as misses |
| Color sequences and update rates | Start at the first active time and pause during rests; original default rates | Complete checker-pair rates: bar 4 Hz, meridian 5 Hz, LGN/HRF 3.75 Hz |
| RDS | Opposing checker planes cycle through disparity levels; negative disparity is near; configurable density, radius, color, background, and task gain | The earlier `random` assignment remains available; small-angle disparity is converted directly to degrees instead of cyclic image shifts |
| Object images | 120 selected images, scale, disparity, 250 ms updates, colored noise, native NumPy bank, and advance synthesis | RGBA values of all 7,493 source images match; random placement and interpolation differ from MATLAB |
| Peripheral binocular fusion guides | `plain`/`grid`, patch size/count/two colors, clear central aperture, and a shared layout for both eyes | Eye-region fit is checked on loading; verify guide positions and eye assignment on the intended display |
| Monocular and binocular presentation | 15 display modes, side-by-side and vertical splits, anaglyph, interleaving, dual displays, and shutter stereo | Software eye assignment is tested; physical synchronization, crosstalk, and quad-buffer stereo require apparatus checks |
| Gamma | RGB exponents, arbitrary N x 3 JSON tables, and a separate table for the second physical display in `dual` mode | Applied locally without changing system-wide settings; perform photometric calibration on the apparatus |
| Starting an acquisition | Space/Enter, left mouse button, scanner key, arbitrary named key, or immediate start | Direct parallel-port voltage input is unsupported; numeric PTB key codes are not guessed |
| Refresh and waiting | Explicit refresh selection or measured refresh, corresponding to `force_frame_rate`; state selection at every refresh | Sync checks are retained; measured and configured refresh rates are checked for consistency |
| Photodiode marker | Four corners, configurable size, half-position duration by default or an explicit duration | Measure optical onset on the apparatus |
| Timing, responses, and results | Cumulative deadlines from one `t0`; events, frames, block timing, status, and UUID | A preceding block's measured end is not used as the next origin |
| Stimulus windows, TR, and low-resolution reconstruction | Planned/actual-flip reconstruction, exposure integrated within each TR, NPZ/MAT output, and adjustable resolution | Exposure integration replaces instantaneous sampling at each TR |
| PRT and OLT | Millisecond/volume PRT from the shared timeline; six original OLT files distributed unchanged | File structure is tested; import into BrainVoyager itself requires verification |
| DEBUG and stimulus inspection | `preview --time`, `--all-positions` with a manifest, and a gallery of 14 basic stimuli | Explicit offline commands replace implicit debugging selected by a participant name |

PRT output follows the [BrainVoyager format specification](https://helpdesk.brainvoyager.com/729383-The-Format-of-PRT-Files). `Volumes` uses one-based inclusive intervals; `msec` uses milliseconds from run onset. Intervals that do not align exactly with TR boundaries are rejected for volume output rather than silently rounded.

## Device-dependent and auxiliary functionality

Dedicated PROPixx/Datapixx initialization, VESA/blue-line control, and direct parallel-port pin-voltage input are unsupported. Unsupported modes are not silently replaced. Check dual-display swaps, physical shutter synchronization, scanner and response devices, gamma, and optical timing on the apparatus used for the experiment.

The original `Common` directory also includes general-purpose EyeLink, MEG, audio, and image-processing helpers. PyRetinotopy does not provide a one-to-one Python translation of all 278 MATLAB files. MATLAB HTML generation with m2html is also outside the presentation functionality. Features used through the presentation entry points are integrated in the table above.

## Reproducing saved acquisition settings

For acquisitions from v0.3.0 and earlier, the summary version determines compatibility defaults for omitted coordinate, color-clock, RDS, fixation, task, and marker settings. Ordinary configuration files use the current defaults. New acquisitions save the complete resolved configuration.
