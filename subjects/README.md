# Participant settings and default inheritance

[English](README.md) | [Japanese](README_ja.md)

The Python equivalent of the original `Presentation/subjects/_DEFAULT_` directory is **`subjects/_DEFAULT_/`**. Configuration files use JSON instead of MATLAB.

```text
subjects/
  _DEFAULT_/
    common.json                 # Shared defaults for seed, run, and task
    retinotopy_display.json      # Display settings
    c_pol.json                  # Wedge
    c_ecc.json                  # Annulus
    c_dual.json                 # Combined wedge and annulus
    c_bar.json
    c_multifocal.json
    c_meridian.json
    c_lgnlocalizer.json
    c_hrf.json
    c_localizer.json
  HB/
    common.json                 # Optional participant-wide overrides
    retinotopy_display.json      # Optional participant display overrides
    c_pol.json                  # Optional participant wedge overrides
    ccwf.json                   # Optional overrides for this mode only
```

## Create, validate, and run

Run these commands from the project root using PsychoPy's Python:

```powershell
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy init-subject HB --mode ccwf
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy validate --subject HB --mode ccwf
& 'C:\Program Files\PsychoPy\python.exe' -m pyretinotopy run --subject HB --mode ccwf
```

`init-subject` creates an empty `HB/common.json` and an `HB/ccwf.json` containing only the run number. It does not overwrite existing configuration files. It can add settings to a participant directory that already contains results, preserving an existing `common.json`. `--subject HB` also works with defaults when the participant directory or individual files do not yet exist. The `validate` output lists loaded files in `configuration_sources`.

## Loading order

Settings are merged in this order, with **only explicitly specified values overriding earlier values**:

1. Built-in Python defaults for the stimulus family.
2. `_DEFAULT_/common.json`, `retinotopy_display.json`, the matching `c_*.json`, then `<mode>.json`, if present.
3. `HB/common.json`, `retinotopy_display.json`, the matching `c_*.json`, then `<mode>.json`, if present.

Participant values take precedence over default family values. Within a participant's settings, later files take precedence. Dictionaries merge by key; lists are replaced as a whole. Missing files and fields retain defaults, while syntax errors or unknown fields in existing files are reported as errors.

For example, `HB/retinotopy_display.json` can contain only that participant's eye-position corrections:

```json
{
  "display": {
    "eye_offsets_px": [[3, -2], [-4, 5]],
    "mirror_x": [false, false]
  }
}
```

The following `HB/c_pol.json` applies to all carriers and tasks for both `ccw` and `cw`:

```json
{
  "stimulus": {"wedge_width_deg": 60},
  "timing": {"cycle_s": 60, "repeats": 6}
}
```

`HB/ccwi.json` applies only to the object-image wedge mode. If a JSON file also specifies `mode` or `subject`, it must agree with the command-line selection.

Relative image and cache paths are resolved from **the JSON file that defines the value**. A path inherited from a default file is not reinterpreted relative to the participant directory unless the participant explicitly supplies a replacement value.

## Family files

| File | Basic modes |
|---|---|
| `c_pol.json` | ccw, cw |
| `c_ecc.json` | exp, cont |
| `c_dual.json` | ccwexp, ccwcont, cwexp, cwcont |
| `c_bar.json` | bar |
| `c_multifocal.json` | multifocal |
| `c_meridian.json` | meridian |
| `c_lgnlocalizer.json` | lgn |
| `c_hrf.json` | hrf |
| `c_localizer.json` | localizer |

The supplied `retinotopy_display.json` is not a calibrated full-screen acquisition configuration. Before scanning, set resolution, physical screen width, viewing distance, display mode, refresh rate, and start signal for the intended apparatus.

## Resolved settings, image preparation, and sessions

```powershell
python -m pyretinotopy validate --subject HB --mode ccwf --save-config resolved-HB-ccwf.json
python -m pyretinotopy prepare-objects --subject HB --mode ccwi
python -m pyretinotopy run --subject HB --mode ccwi
```

`--save-config` saves a fully resolved JSON configuration. Each acquisition also saves the resolved settings in `subjects/ID/results/YYMMDD/MODE_run-NN/config.json` and the source-file list in `summary.json`. Editing the defaults later does not alter the conditions replayed with `--config path/to/saved/config.json`.

**`--config FILE` is an explicit standalone configuration.** It does not search `_DEFAULT_` or other participant files; omitted fields use only built-in Python defaults. Use `--subject ID --mode MODE` for inheritance and `--config FILE` for replaying saved conditions. `--subject` and `--config` are mutually exclusive.

`--subjects-dir PATH` changes the configuration root. If the selected root has no `_DEFAULT_`, built-in defaults are used. Copy `_DEFAULT_` there to retain the shared file-based defaults. A custom root and its participant settings are not created automatically when loading settings.

Session runs can specify the following instead of `config`. `subjects_dir` is optional; when supplied, it is resolved relative to the session JSON file.

```json
{
  "runs": [
    {"subject": "HB", "mode": "ccwf", "run": 1},
    {"subject": "HB", "mode": "expf", "run": 1}
  ]
}
```

Participant directories are excluded from Git. Only the distributed `_DEFAULT_` directory and this guide are included. Back up laboratory settings separately.

## Results grouped by participant

The default result directory is `subjects/ID/results/YYMMDD/MODE_run-NN/`, for example `subjects/HB/results/261106/ccwf_run-01/`. The date comes from the experiment computer's local date when the acquisition is initialized. The participant directory is created automatically even if no settings have been created in advance.

Inherited configurations loaded with `--subjects-dir` save results under that root's participant directory. An explicit JSON file inside a participant-ID directory also uses that settings root. Examples such as `examples/smoke.json` save under the project's `subjects/demo/` directory.

Each mode and run has a separate subdirectory under the date directory. Repeating the same date, ID, mode, and run archives the complete previous directory as `_old-01`, `_old-02`, etc., before saving a new attempt. `run --run N` overrides the JSON run value; different run numbers use separate directories. The default is automatic backup; `--if-exists error` cancels when results already exist. Only an explicit `--output-root ROOT` uses the alternative `ROOT/sub-ID/MODE_run-NN/` layout. Existing `data` directories are not modified.
