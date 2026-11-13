# PyRetinotopy - Retinotopy for PsychoPy

[English](USAGE.md) | [Japanese](USAGE.ja.md)

PyRetinotopy is a Python/PsychoPy adaptation of the MATLAB Psychtoolbox 3 Retinotopy stimulus set ([https://github.com/hiroshiban/Retinotopy](https://github.com/hiroshiban/Retinotopy)), developed and publicly released by Hiroshi Ban. The project and directory name is **PyRetinotopy**; the distribution, Python import, and command name is **pyretinotopy**.

The current version is **v0.4.0**. Starting positions and combined-annulus positions follow the original PTB3 image coordinates and reversed image sequences. Results are grouped by participant and date. Image data use an independent NumPy format, with complete image preparation before acquisition and advance GPU transfers. All stimuli follow cumulative time from run onset. See the [feature correspondence](PTB3_FEATURES.md) for device-dependent limits.

The Python project is independent of the original MATLAB source and participant data. Legacy-source paths below are examples for optional conversion; normal presentation does not require the original directory.

## Available stimuli

| Basic mode | Stimulus |
|---|---|
| `ccw`, `cw` | Counterclockwise/clockwise rotating wedge |
| `exp`, `cont` | Expanding/contracting annulus |
| `bar` | Bar sweeps in multiple directions |
| `ccwexp`, `ccwcont`, `cwexp`, `cwcont` | Union of a wedge and annulus with independent cycles |
| `multifocal` | Region-specific m-sequences or a supplied design over polar angle and eccentricity |
| `meridian` | Opposing wedges on horizontal/vertical meridians |
| `lgn` | Left/right hemifield LGN localizer |
| `hrf` | Stimulus/rest sequence for HRF estimation |
| `localizer` | A selected eccentricity band and its complement |

Suffixes follow the original package: no suffix means a color checker with stimulus-luminance detection; `f` means checker with a fixation task; `d` means RDS with stimulus-depth detection; `df` means RDS with a fixation task; and `i` means object images with a fixation task. There are 70 mode names. Use `*windows` names with `export`.

Display settings are independent of the stimulus. Modes are `mono`, `parallel`, `cross`, `dual`, `dualparallel`, `dualcross`, `topbottom`, `bottomtop`, `redgreen`, `greenred`, `redblue`, `bluered`, `interleavedline`, `interleavedcolumn`, and `shutter`. Shutter stereo uses PsychoPy's quad-buffer stereo and requires checks with a compatible GPU, driver, and glasses. Dedicated PROPixx/Datapixx control is unsupported.

## Starting the program

The following examples use the Python bundled with a Windows PsychoPy installation. Replace the project path with your checkout location and adjust the Python path if necessary.

```powershell
Set-Location 'E:\PyRetinotopy\PyRetinotopy'
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy list
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy validate --config examples\ccwf.json
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --config examples\smoke.json
```

`smoke.json` is a short, automatically starting 640 x 480 demonstration, not an acquisition configuration. Repeating the same participant/mode/run archives the complete previous results as `_old-01`, `_old-02`, etc., and saves the latest attempt under the original name. Use another number, such as `--run 2`, for a separate acquisition.

In a Python environment with working PsychoPy, install with `python -m pip install -e .`. Core dependencies are Python 3.10 or later, NumPy, and Pillow. Presentation additionally requires PsychoPy. Install `.[legacy]` to add SciPy/h5py for legacy image conversion and MATLAB-compatible output. The tested standalone environment is **PsychoPy 2024.2.4 / Python 3.10.11 / Windows**.

The Windows acquisition examples use GLFW and full-screen presentation. To install the backend locally without changing PsychoPy itself:

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pip install --target optional-libs --no-deps psychopy-glfw==0.0.2 glfw==2.8.0
```

`examples/object-images-fullscreen.json` is a performance-check example for a 2560 x 1440 screen. Replace `width_cm` and `distance_cm` with measurements from the experiment apparatus; example dimensions are not calibration values.

In PsychoPy Coder, open `PyRetinotopy.py` and select Run to choose a JSON configuration file.

## Run numbers and repeat attempts

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --subject HB --mode ccw --run 1
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --subject HB --mode ccw --run 2
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --subject HB --mode ccw --run 1
```

`--run` overrides the JSON value and is recorded in the configuration, summary, and result path. Repeating a number archives the previous directory, for example as `ccw_run-01_old-01/`. Other run numbers and existing backups are preserved. Completed, aborted, and failed attempts are all retained. The latest attempt is not necessarily successful; inspect each `summary.json` status and its logs when selecting data.

The default policy is `--if-exists backup`. `--if-exists error` cancels if results already exist. An OS lock protects an active acquisition. Its reusable `.lock` file may remain after exit. Each acquisition has an `acquisition.json` containing a unique ID and the archive path of its preceding attempt.

By default, `timing.operator_confirm: true` confirms ID/mode/run before backup or preparation. Cancellation leaves the previous data in place. `--no-confirm` or a false setting skips this confirmation without skipping scanner-trigger waiting. Sessions use each entry's run number and can be repeated. Give duplicate acquisitions within a single session distinct run numbers.

## Participant settings and presentation

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy init-subject HB --mode ccwf
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy validate --subject HB --mode ccwf
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --subject HB --mode ccwf
```

Edit the JSON `display`, `timing`, `stimulus`, and `task` sections. Units are seconds, degrees of visual angle, arcminutes of disparity, and RGB values from 0 to 1. Inherited configurations select family defaults from `--mode`. For standalone JSON, use `init --mode` for each protocol; overriding `--mode` on an existing standalone JSON does not replace its other parameters with different family defaults.

[subjects/_DEFAULT_](../subjects/_DEFAULT_) corresponds to the original `Presentation/subjects/_DEFAULT_`. `--subject HB --mode ccwf` reads default `common.json`, `retinotopy_display.json`, `c_pol.json`, and optional `ccwf.json`, then overlays files of the same names from the participant directory in the same order. Missing files/fields retain defaults; participant files need contain only differences. Lists are replaced as a whole. The nine family filenames match the original package.

`init-subject` creates an empty override in `HB/common.json` and only a run number in `HB/ccwf.json`. Put display corrections in `HB/retinotopy_display.json` and shared wedge settings in `HB/c_pol.json`. See the [participant configuration guide](../subjects/README.md) for layout, precedence, examples, and sessions.

`init FILE --subject HB --mode ccwf` and `--config FILE` remain available for standalone JSON. These do not search other default files, preserving saved acquisition conditions. `validate --subject HB --mode ccwf --save-config resolved.json` saves the fully merged inherited configuration.

Default scanner-start keys are `t` or `5`; response keys are `r`/`g`; Escape/Q aborts. `skip_triggers` ignores a specified number of initial pulses. Start methods include scanner keys, Space/Enter, left mouse button, and automatic start. Direct parallel-port voltage input is unsupported.

For sequential acquisitions, list configurations and run numbers as in `examples/session.json` and execute `session examples/session.json`. Each acquisition waits for its own start signal; aborting stops the remaining sequence.

Pixels per degree are calculated as `display.size_px[0] / width_cm * distance_cm * tan(1 degree)`. `width_cm` is the **physical width corresponding to the complete `size_px` framebuffer**. Side-by-side presentation does not shrink the image, so settings that do not fit an eye's region are rejected. Dimensions in `stereo-rds.json` illustrate configuration and must be replaced with apparatus measurements.

`dual` opens two windows on different screen IDs. Their swap-time difference is logged, but hardware synchronization is not guaranteed. `dualparallel`/`dualcross` instead split a single wide framebuffer into left/right regions. Eye-specific offsets and horizontal/vertical reflections are configurable.

## Starting positions and PTB3 compatibility

The default `stimulus.spatial_convention` is `"ptb3"`. Configured `start_angle_deg` is clockwise in the original image coordinates. The default `cw` center starts upward at 90 degrees; `ccw` starts at 102 degrees, 12 degrees counterclockwise from upward. The original reversal of the entire ccw image sequence is retained. Combined-stimulus annuli use 16 positions, 2-second steps, and nominal width 1 degree.

Multifocal regions follow clockwise order. `multifocal_indexing: "corrected"` assigns 36 unique regions. Use `"ptb3"` to reproduce the original duplicate region IDs, supported only at phase 0 and width 360 degrees.

Use `spatial_convention: "legacy-python"` to replay v0.2.2 or earlier. If the saved `config.json` omits this field and its sibling `summary.json` records v0.2.2 or earlier, compatibility is selected automatically. Ordinary JSON settings use the current defaults. See [PTB3 spatial compatibility](PTB3_PARITY.md) for starting positions and verification limits.

## Image stimuli and migrating MATLAB settings

`examples/object-images.json` refers to `assets/object-images/manifest.json`. Prepare the accompanying NumPy image bank before use; its approximately 1.96 GB `images.npy` is excluded from Git. The bank contains 7,493 RGBA images with axes `(image, y, x, RGBA)`. Presentation reads the native bank, not the original MAT file. Ordinary image directories, such as PNG files, are also supported. See the [image-bank guide](../assets/object-images/README.md).

To convert the legacy database once, adjust the following input path. The importer reads the input without changing it and compares all color and alpha values:

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy convert-images ..\Retinotopy\object_images\object_image_database.mat --output assets\object-images
```

Before acquisition, synthesize all images into a NumPy movie. It can be reused for identical source images, seed, and conditions. Relative cache paths are resolved from the defining JSON file. The examples use `cache/object-movies` at the project root.

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy prepare-objects --config examples\object-images-fullscreen.json
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --config examples\object-images-fullscreen.json
```

`run` also prepares a missing movie before initializing the display. A standard 360-second movie with 1031 x 1031 pixels per eye needs approximately 9.2 GB of cache. During presentation, the program prefetches prepared images and updates a GPU ring; image changes select textures already transferred to the GPU.

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy migrate ..\Retinotopy\Presentation\subjects\_DEFAULT_ --mode ccwf --output subjects\demo\migrated-ccwf.json
```

`migrate` transfers constants and simple arithmetic without executing MATLAB. Unparsed expressions and review items are written to `.migration.json`. Screen IDs, key codes, and device-specific settings are not guessed. Review the generated draft before use.

## Previews, stimulus windows, and acquisition logs

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy preview --config examples\stereo-rds.json --output rds-preview.png
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy export --config examples\barf.json --output bar-windows.npz --tr 2 --resolution 128
```

Exported stimulus windows are exposure-integrated values from 0 to 1 within each TR. NPZ axes are `(time, y, x)`; the MAT variable `stim_windows` uses `(y, x, time)` to match the original. The top row represents the upper visual field. Geometric analysis apertures do not include fixation, noise, objects, or disparity itself.

After acquisition, reconstruct apertures from actual flips, for example with `export --config subjects/HB/results/261106/ccwf_run-01/config.json --frames subjects/HB/results/261106/ccwf_run-01/frames.tsv --output actual-windows.npz`. During a dropped frame, reconstruction assumes the previous image remained visible. Eye-specific implementation differences and optical display latency are not included.

Each acquisition saves `config.json`, `frames.tsv`, `events.tsv`, `block_timing.tsv`, `targets.tsv`, `responses.tsv`, and `summary.json`. The first actual flip is time zero; earlier triggers retain negative timestamps. All stimuli use cumulative elapsed time from run onset. Delays advance the state to current time; faster refreshes can hold a state.

Inspect `planned_onset_s`, `actual_onset_s`, and `error_s` in `block_timing.tsv` for increasing error toward the end of a run. `frames.tsv` also records CPU time for state updates, drawing, and prefetching. These logs do not constitute a complete BIDS dataset.

## Documentation and checks

- [Project and Experiment Guide, English PDF](PyRetinotopy_Experiment_Guide_en.pdf)
- [Project and Experiment Guide, Japanese PDF](PyRetinotopy_Experiment_Guide_ja.pdf)
- [Presentation timing and block boundaries](PRESENTATION_TIMING.md)
- [Feature correspondence and limits](PTB3_FEATURES.md)
- [Original-to-Python setting mapping](PTB3_PARAMETER_MAP.md)
- [Starting positions, scan order, and compatibility](PTB3_PARITY.md)

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m unittest discover -s tests -v
& 'C:\Program Files\PsychoPy\python.exe' tools\qa.py --live
```

`qa.py --live` opens a series of short presentation windows. Its screen captures are for verification and are not used during normal acquisition.

The original BSD license is retained. See [LICENSE.txt](../LICENSE.txt) and [NOTICE.md](../NOTICE.md) for terms and attribution.

## Result locations

Without `--output-root`, results are saved in `subjects/ID/results/YYMMDD/MODE_run-NN/`, for example `subjects/HB/results/261106/ccwf_run-01/`. The experiment computer's local date is determined during acquisition initialization. Settings and results are kept under the same participant ID.

Inherited `--subjects-dir` settings also determine the result root. An explicit JSON inside a participant-ID directory uses that settings root. Demonstrations use the project's `subjects` directory. `PyRetinotopy.py` in Coder follows the same defaults. A repeated acquisition archives its complete previous directory with a numbered suffix; `init-subject` can add settings to an ID that already has results.

Use `--output-root ROOT` only when deliberately selecting another location. This uses `ROOT/sub-ID/MODE_run-NN/`. Existing data directories and earlier acquisition logs are not moved automatically. Replace `261106` in analysis examples with the actual acquisition date.

## Controls inherited from the original

Set `task.fixation_type` to `circle`, `cross`, or `concentric` (numeric 1, 2, or 3 is also accepted). Original type 2 is a framed graduated cross; type 3 has a central disk and interrupted outer ring. Set `fixation_radius_px` and `fixation_color`; the default dimmed task level is 64/255.

`task.schedule: "ptb3"` uses `fixation_frequency` (default 4), `duration_s` (default 0.3 seconds), and regular slots that avoid consecutive targets. Tasks can appear during initial/final fixation and rests. Stimulus tasks use the original half-period position/color/disparity windows. `"interval"` selects the earlier Python `interval_s` schedule.

Peripheral fusion guides use `display.background_type: "grid"` and patch settings. Half-position markers use `marker_timing: "half"`; measured refresh uses `use_measured_refresh: true`. Supply N x 3 RGB tables in `gamma_lut` and, for the second physical display in `dual` mode, `gamma_lut_right`. See the [feature correspondence](PTB3_FEATURES.md) and [all 96 settings](PTB3_PARAMETER_MAP.md).

Use `preview --all-positions` for every aperture position and a manifest, `export --prt FILE` for PRT from planned or actual-flip timing, and `export-olts --output DIR` for the six original color tables. Presentation requires hardware OpenGL; use a GPU-enabled local desktop, as hardware OpenGL may be unavailable through Remote Desktop.

OpenAI generative AI tools, including Codex, supported this adaptation. Hiroshi Ban, the author and responsible investigator, reviews the transfer of functionality and performs operational checks throughout development. He is responsible for the software and its release.
