# PTB3 starting positions and scan order - v0.3.0

[English](PTB3_PARITY.md) | [Japanese](PTB3_PARITY.ja.md)

The original MATLAB files are unchanged. Formulas from `Presentation` and `Generation` were compared with all 70 Python modes using independent reference formulas. This is not a pixel comparison with images rendered by MATLAB.

## Default starting positions

| Stimulus | Behavior matching the original |
|---|---|
| `cw` | Starts centered at 90 degrees (upward) and rotates clockwise; configured start angle -114 degrees and width 48 degrees |
| `ccw` | Starts centered at 102 degrees and rotates counterclockwise; presenting the 30-image sequence in N..1 order places the first image 12 degrees counterclockwise from upward |
| `exp` | Expands from the center through 25 positions, in 2-second steps; 50 seconds active and 10 seconds rest |
| `cont` | After 10 seconds rest, contracts from an 8-degree radius toward the center through 25 positions |
| Four combined modes | Polar-angle starts as above; annulus has 16 positions, 2-second steps, and nominal width 1 degree; expansion has 32 seconds active then 8 seconds rest, contraction has rest before activity |
| `bar` | The first normal angle is 0 degrees: move from the right edge (center x = 8 degrees) to the left; all 9 sweeps and 16 positions per sweep are compared |
| `multifocal` | Region 0 starts at the right horizontal meridian and follows image-clockwise order; default IDs are unique across 12 sectors x 3 eccentricity bands |
| `meridian` | Starts with opposing wedges on the horizontal meridian, alternating with the vertical meridian |
| `lgn` | Starts with a 140-degree-wide left field, alternating with its horizontal reflection; custom start angles do not turn this into a 180-degree rotation |
| `hrf` | Starts with a full-field stimulus, followed by rest |
| `localizer` | Starts with a 2.7-3.8-degree eccentricity band, followed by rest and its complement |

The original rules for placing rest before clockwise/contracting scans are retained. Default polar rest is zero for `ccw` and `cw`. Each stimulus has 4 seconds of initial and final fixation by default.

## Coordinates

`stimulus.spatial_convention: "ptb3"` is the default. Configured `start_angle_deg` and `dual_ring_start_angle_deg` use PTB3 image coordinates: zero points right and positive angles point toward the lower half of the image. `checker_phase_deg` and related parameters also apply to the original angular phase. Internal components and output windows use visual-field coordinates: zero points right and positive angles point upward. The top image row represents the upper visual field.

For zero-based PTB3 wedge image index `j`, the leading edge in visual-field coordinates is `-start_angle_deg - j*step_angle_deg - wedge_width_deg`. `cw` starts at `j=0`; `ccw` starts at `j=N-1`. Simply reversing the sign would leave a one-step difference for `ccw`.

The combined-annulus position count is `(360 / step_angle_deg) * (eccentricity_cycle_s - eccentricity_rest_s) / (polar_cycle_s - polar_rest_s)`. This corrects the earlier Python formula, which used the annulus's independent cycle and produced 24 positions. Choose conditions giving an integer position count, as in the original; non-integer counts are rejected. Where wedge and annulus overlap, the wedge checker takes precedence.

## Explicit multifocal indexing difference

At zero phase, the original `mf_GenerateCheckerBoard1D.m` sets `true_nwedges=ndivsE`. With 12 sectors and 3 eccentricity bands, different regions therefore share IDs. The default `multifocal_indexing: "corrected"` uses `sector + ring*sectors`, assigning 36 unique regions. This retains the corrected indexing used by the Python package.

To reproduce the historical duplicate IDs, select `multifocal_indexing: "ptb3"`. This is supported only at phase 0 and width 360 degrees and uses `sector + ring*rings`. The choice is saved with each acquisition. Do not treat the default corrected apertures as identical to historical MATLAB apertures.

## Replaying earlier Python acquisitions

Select `spatial_convention: "legacy-python"` to reproduce starting positions from v0.2.2 or earlier. If a saved acquisition's `config.json` omits the field and its sibling `summary.json` records v0.2.2 or earlier, it is recognized automatically. An explicit setting takes precedence. Ordinary JSON and participant configurations use the current defaults. Set `legacy-python` explicitly when an older file lacks version metadata.

Starting phase affects analysis. Distinguish earlier and current acquisitions and regenerate analysis apertures from the `config.json` saved with each acquisition. Existing acquisition results are not rewritten.

## Verification and limits

Run `python -m unittest discover -s tests -v` for automated comparisons of continuous-coordinate apertures against the original reference formulas in `tests/reference_ptb3.py`. Tests also cover changed starting angles, widths and steps, transitions around rest, asymmetric LGN angles, and original multifocal ID compatibility.

These checks concern continuous-coordinate apertures. The original uses integer pixels-per-degree rounding, a 1.01 raster margin, and ceiling-based boundaries, so pixel edges and central fixation can differ. Identical checker sequences, task sequences, stochastic-carrier framebuffers, and optical output are not claimed. Run duration, cycle/block cumulative targets, and absolute-time control are unchanged.
