"""Explicit units: seconds, visual degrees, arcminutes and RGB in [0, 1]."""
from dataclasses import asdict, dataclass, field, fields
import copy
import json
import math
from pathlib import Path
import re

from .modes import DISPLAY_MODES, parse_mode


@dataclass
class DisplayConfig:
    mode: str = "mono"
    size_px: list = field(default_factory=lambda: [1280, 1080])
    screens: list = field(default_factory=lambda: [0, 1])
    width_cm: float = 33.3  # physical width corresponding to size_px[0]
    distance_cm: float = 96.0
    ipd_cm: float = 6.4
    full_screen: bool = False
    refresh_hz: float = 60.0
    use_measured_refresh: bool = False  # PTB3 force_frame_rate=0
    backend: str = "pyglet"
    high_priority: bool = True
    realtime_priority: bool = False
    gpu_mask_limit_mb: int = 1024
    background: list = field(default_factory=lambda: [128/255]*3)
    background_type: str = "plain"  # plain or grid (PTB3 bgtype 1/2)
    background_patch_size_px: list = field(default_factory=lambda: [30,30])  # height,width
    background_patch_count: list = field(default_factory=lambda: [20,40])
    background_patch_colors: list = field(default_factory=lambda: [[1,1,1],[0,0,0]])
    eye_offsets_px: list = field(default_factory=lambda: [[0, 0], [0, 0]])
    mirror_x: list = field(default_factory=lambda: [False, False])
    mirror_y: list = field(default_factory=lambda: [False, False])
    gamma: list = field(default_factory=lambda: [1.0, 1.0, 1.0])
    gamma_lut: list = field(default_factory=list)  # optional N x RGB [0,1], overrides exponents
    gamma_lut_right: list = field(default_factory=list)  # optional second physical display (dual only)
    marker_corner: int = 0  # 0=off; 1=UL, 2=UR, 3=LL, 4=LR
    marker_size_px: int = 50
    marker_duration_s: float = 0.1
    marker_timing: str = "half"  # half of the current position, or fixed duration

    @property
    def ppd(self):
        # Same small-angle, linear degree mapping as PTB and PsychoPy 'deg'.
        return self.size_px[0] / self.width_cm * self.distance_cm * math.tan(math.pi/180)


@dataclass
class TimingConfig:
    initial_fixation_s: float = 4.0
    final_fixation_s: float = 4.0
    cycle_s: float = 60.0
    rest_s: float = 0.0
    repeats: int = 6
    polar_cycle_s: float = 60.0
    polar_rest_s: float = 0.0
    polar_repeats: int = 6
    eccentricity_cycle_s: float = 40.0
    eccentricity_rest_s: float = 8.0
    eccentricity_repeats: int = 9
    block_s: float = 16.0
    trial_s: float = 2.0
    trigger_keys: list = field(default_factory=lambda: ["t", "5"])
    response_keys: list = field(default_factory=lambda: ["r", "g"])
    abort_keys: list = field(default_factory=lambda: ["escape","q"])
    skip_triggers: int = 0
    operator_confirm: bool = True  # PTB3 force_proceed_flag=False; shown before backup/window preparation
    start: str = "trigger"  # trigger, key, mouse, immediate
    tr_s: float = 2.0


@dataclass
class StimulusConfig:
    temporal_convention: str = "ptb3"  # active presentation clock; legacy-python includes blanks
    disparity_assignment: str = "ptb3"  # opposing checker planes; random preserves old patch depths
    spatial_convention: str = "ptb3"  # or legacy-python for v0.2.x replay
    min_radius_deg: float = 0.0
    max_radius_deg: float = 8.0
    wedge_width_deg: float = 48.0
    start_angle_deg: float = -114.0  # PTB3 image angle: +x=0, clockwise
    step_angle_deg: float = 12.0
    checker_wedges: int = 4
    checker_rings: int = 8
    checker_phase_deg: float = 0.0
    dual_ring_width_deg: float = 24.0
    dual_ring_step_angle_deg: float = 12.0
    dual_ring_checker_wedges: int = 4
    dual_ring_checker_rings: int = 2
    dual_ring_phase_deg: float = 0.0
    dual_ring_start_angle_deg: float = -102.0
    bar_width_deg: float = 1.5
    bar_steps: int = 16
    bar_angles_deg: list = field(default_factory=lambda: [0,45,90,135,180,225,270,315,0])
    bar_checks_long: int = 18
    bar_checks_short: int = 2
    multifocal_indexing: str = "corrected"  # ptb3 reproduces the original zero-phase ID overlap
    multifocal_sectors: int = 12
    multifocal_rings: int = 3
    multifocal_design: list = field(default_factory=list)  # region x trial, 0/1
    target_radii_deg: list = field(default_factory=lambda: [2.7,3.8])
    colors: list = field(default_factory=lambda: [[1,0,0],[0,1,0],[1,1,0],[0,0,1],
                    [1,0,1],[0,1,1],[1,1,1],[0,0,0],[1,128/255,0],[128/255,0,1]])
    flicker_hz: float = 5.0  # complete A/B pairs per second
    disparity_arcmin: list = field(default_factory=lambda: [-12,12,5])
    dot_density_percent: float = 0.5
    dot_radius_deg: float = 0.05
    dot_colors: list = field(default_factory=lambda: [[1,1,1],[0,0,0]])
    dot_background: bool = False
    dot_correlation: float = 1.0
    dot_refresh_hz: float = 10.0
    object_source: str = ""
    object_count: int = 120
    object_scale: list = field(default_factory=lambda: [0.2,0.5])
    object_disparity_arcmin: list = field(default_factory=lambda: [-12,12])
    object_update_s: float = 0.25
    object_cache_dir: str = "cache/object-movies"
    object_texture_slots: int = 4
    noise_contrast: float = 0.2


@dataclass
class TaskConfig:
    schedule: str = "ptb3"  # PTB3 task slots or uniform interval scheduling
    fixation_frequency: int = 4  # fixtaskfreq; probability 1/(2*frequency) per duration slot
    interval_s: list = field(default_factory=lambda: [2.0,6.0])
    duration_s: float = 0.3
    response_window_s: float = 1.0
    dim_ratio: float = 0.4
    depth_multiplier: float = 2.0
    fixation_radius_px: int = 4
    fixation_type: str = "circle"  # PTB3: circle, cross, concentric; extension: square
    fixation_rendering: str = "ptb3"  # legacy-python preserves old shape/dimming
    fixation_dim_color: list = field(default_factory=lambda: [64/255]*3)
    fixation_color: list = field(default_factory=lambda: [1,1,1])
    enabled: bool = True


@dataclass
class ExperimentConfig:
    subject: str = "demo"
    run: int = 1
    mode: str = "ccwf"
    seed: int = 1
    display: DisplayConfig = field(default_factory=DisplayConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    stimulus: StimulusConfig = field(default_factory=StimulusConfig)
    task: TaskConfig = field(default_factory=TaskConfig)

    def validate(self, presentation=False):
        mode = parse_mode(self.mode)
        d,t,s,k = self.display,self.timing,self.stimulus,self.task
        if s.temporal_convention not in ("ptb3","legacy-python") or s.disparity_assignment not in ("ptb3","random"):
            raise ValueError("Use ptb3/legacy-python temporal convention and ptb3/random disparity assignment.")
        if s.spatial_convention not in ("ptb3","legacy-python"):
            raise ValueError("spatial_convention must be ptb3 or legacy-python.")
        if type(k.fixation_type) is int:
            k.fixation_type={1:"circle",2:"cross",3:"concentric"}.get(k.fixation_type,"unknown")
        if k.fixation_rendering not in ("ptb3","legacy-python") or k.schedule not in ("ptb3","interval"):
            raise ValueError("Use ptb3/legacy-python fixation rendering and ptb3/interval task schedule.")
        if type(k.fixation_frequency) is not int or k.fixation_frequency<1:
            raise ValueError("fixation_frequency must be a positive integer.")
        if d.background_type not in ("plain","grid") or d.marker_timing not in ("half","fixed"):
            raise ValueError("Use plain/grid background and half/fixed marker timing.")
        for pair in (d.background_patch_size_px,d.background_patch_count):
            if len(pair)!=2 or any(type(v)is not int or v<1 for v in pair):
                raise ValueError("Background patch sizes/counts require two positive integers.")
        if len(d.background_patch_colors)!=2 or any(len(c)!=3 or any(not 0<=v<=1 for v in c) for c in d.background_patch_colors):
            raise ValueError("Background patch colors must be two RGB [0,1] triples.")
        for table in (d.gamma_lut,d.gamma_lut_right):
            if table and (len(table)<2 or any(len(c)!=3 or any(not 0<=v<=1 for v in c) for c in table)):
                raise ValueError("Gamma tables must contain >=2 RGB [0,1] rows.")
        if d.gamma_lut_right and d.mode!="dual":
            raise ValueError("gamma_lut_right requires two physical displays (mode dual).")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", self.subject):
            raise ValueError("Subject must be a safe ID of 1-64 letters, digits, '_' or '-'.")
        # JSON permits NaN/Infinity in some readers. They must never enter timing.
        def finite(value):
            if isinstance(value, dict):
                return all(finite(v) for v in value.values())
            if isinstance(value, list):
                return all(finite(v) for v in value)
            return not isinstance(value, float) or math.isfinite(value)
        if not finite(asdict(self)):
            raise ValueError("All numeric parameters must be finite.")
        positive = [d.width_cm,d.distance_cm,d.ipd_cm,d.refresh_hz,t.cycle_s,t.polar_cycle_s,
                    t.eccentricity_cycle_s,t.block_s,t.trial_s,t.tr_s,s.max_radius_deg,
                    s.wedge_width_deg,s.step_angle_deg,s.bar_width_deg,s.flicker_hz,
                    s.dot_radius_deg,s.dot_refresh_hz,s.object_update_s,s.dual_ring_width_deg,
                    s.dual_ring_step_angle_deg,k.duration_s,
                    k.response_window_s]
        if any(x <= 0 for x in positive):
            raise ValueError("Sizes, rates and active timing parameters must be positive.")
        integer = [self.run,t.repeats,t.polar_repeats,t.eccentricity_repeats,s.checker_wedges,
                   s.checker_rings,s.bar_steps,s.bar_checks_long,s.bar_checks_short,
                   s.multifocal_sectors,s.multifocal_rings,s.object_count,k.fixation_radius_px,
                   d.marker_size_px,d.gpu_mask_limit_mb,s.dual_ring_checker_wedges,s.dual_ring_checker_rings,
                   s.object_texture_slots,*d.size_px]
        if any(type(x) is not int or x < 1 for x in integer) or s.bar_steps < 2:
            raise ValueError("Counts and pixel sizes must be positive integers; bar_steps >= 2.")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be a non-negative integer.")
        if type(t.skip_triggers) is not int or t.skip_triggers < 0:
            raise ValueError("skip_triggers must be a non-negative integer.")
        if len(d.size_px)!=2 or len(d.screens)!=2 or any(type(x)is not int or x<0 for x in d.screens):
            raise ValueError("size_px and screens must have two valid entries.")
        if d.mode not in DISPLAY_MODES:
            raise ValueError(f"Unsupported display mode {d.mode!r}; PROPixx needs a device adapter.")
        if d.backend not in ("pyglet", "glfw"):
            raise ValueError("backend must be pyglet or glfw.")
        if d.mode == "dual" and d.screens[0] == d.screens[1]:
            raise ValueError("dual needs two distinct screen IDs.")
        if not (0 <= s.min_radius_deg < s.max_radius_deg and s.wedge_width_deg <= 360):
            raise ValueError("Require 0 <= min_radius < max_radius and wedge width <= 360.")
        if not math.isclose(360/s.step_angle_deg, round(360/s.step_angle_deg)):
            raise ValueError("step_angle_deg must divide 360 exactly.")
        if not math.isclose(360/s.dual_ring_step_angle_deg,round(360/s.dual_ring_step_angle_deg)):
            raise ValueError("dual_ring_step_angle_deg must divide 360 exactly.")
        for cycle,rest in ((t.cycle_s,t.rest_s),(t.polar_cycle_s,t.polar_rest_s),
                           (t.eccentricity_cycle_s,t.eccentricity_rest_s)):
            if not 0 <= rest < cycle:
                raise ValueError("Rest must satisfy 0 <= rest < cycle.")
        if min(t.initial_fixation_s,t.final_fixation_s,d.marker_duration_s) < 0:
            raise ValueError("Fixation and marker durations cannot be negative.")
        if mode.family in ("meridian","lgn","localizer") and t.rest_s >= t.block_s:
            raise ValueError("Block rest must be shorter than block_s.")
        if mode.family == "multifocal" and t.rest_s >= t.trial_s:
            raise ValueError("Trial rest must be shorter than trial_s.")
        if mode.family == "dual" and not math.isclose(t.polar_cycle_s*t.polar_repeats,
                                                      t.eccentricity_cycle_s*t.eccentricity_repeats):
            raise ValueError("Dual polar and eccentricity total durations must match.")
        if not s.bar_angles_deg or not all(isinstance(x,(int,float)) for x in s.bar_angles_deg):
            raise ValueError("bar_angles_deg must contain numeric sweep angles.")
        if len(s.colors)<2 or len(s.colors)%2 or any(len(c)!=3 or any(not 0<=v<=1 for v in c) for c in s.colors):
            raise ValueError("colors must contain RGB [0,1] pairs.")
        for rgb in (d.background,k.fixation_color,k.fixation_dim_color):
            if len(rgb)!=3 or any(not 0<=v<=1 for v in rgb):
                raise ValueError("Colors must be RGB triples in [0,1].")
        if len(s.dot_colors)!=2 or any(len(c)!=3 or any(not 0<=v<=1 for v in c) for c in s.dot_colors):
            raise ValueError("dot_colors must contain two RGB triples in [0,1].")
        if len(d.gamma)!=3 or any(v<=0 for v in d.gamma):
            raise ValueError("gamma must have three positive values.")
        if len(d.eye_offsets_px)!=2 or any(len(p)!=2 for p in d.eye_offsets_px):
            raise ValueError("eye_offsets_px requires two [x,y] offsets.")
        if len(d.mirror_x)!=2 or len(d.mirror_y)!=2:
            raise ValueError("Each mirror setting requires a value for each eye.")
        if d.marker_corner not in range(5):
            raise ValueError("marker_corner must be 0..4.")
        if not (0 < s.dot_density_percent <= 100 and -1 <= s.dot_correlation <= 1):
            raise ValueError("Dot density is a percentage (0,100]; correlation must be [-1,1].")
        if (len(s.disparity_arcmin)!=3 or s.disparity_arcmin[0]>s.disparity_arcmin[1]
                or int(s.disparity_arcmin[2])!=s.disparity_arcmin[2] or s.disparity_arcmin[2]<1):
            raise ValueError("disparity_arcmin requires [min,max,positive integer steps].")
        for pair in (s.object_scale,s.object_disparity_arcmin,s.target_radii_deg,k.interval_s):
            if len(pair)!=2 or pair[0]>pair[1]:
                raise ValueError("Parameter ranges must be [min,max].")
        if not (0< s.object_scale[0] <= s.object_scale[1] and 0<=s.noise_contrast<=1):
            raise ValueError("Object scale must be positive; noise contrast in [0,1].")
        if not (s.min_radius_deg<=s.target_radii_deg[0]<s.target_radii_deg[1]<=s.max_radius_deg):
            raise ValueError("Target radii must lie within the stimulation field.")
        if k.interval_s[0] <= max(k.duration_s,k.response_window_s):
            raise ValueError("Task interval must exceed task duration and response window.")
        if not 0 < k.dim_ratio < 1 or k.depth_multiplier <= 1:
            raise ValueError("dim_ratio must be (0,1); depth_multiplier must exceed 1.")
        if s.object_texture_slots < 3 or not s.object_cache_dir:
            raise ValueError("object_texture_slots must be >= 3 and object_cache_dir cannot be empty.")
        if k.fixation_type not in ("circle","cross","square","concentric"):
            raise ValueError("Unknown fixation_type.")
        if t.start not in ("trigger","key","mouse","immediate"):
            raise ValueError("start must be trigger, key, mouse or immediate.")
        if not t.trigger_keys or not t.response_keys or not t.abort_keys:
            raise ValueError("Key lists cannot be empty.")
        if set(t.trigger_keys)&set(t.response_keys) or set(t.abort_keys)&set(t.response_keys+t.trigger_keys):
            raise ValueError("Trigger, response and abort keys must be disjoint.")
        if s.multifocal_indexing not in ("corrected","ptb3"):
            raise ValueError("multifocal_indexing must be corrected or ptb3.")
        if mode.family=="multifocal" and s.multifocal_indexing=="ptb3" and (s.checker_phase_deg!=0 or s.wedge_width_deg!=360):
            raise ValueError("PTB3 multifocal ID compatibility requires phase=0 and width=360.")
        if s.multifocal_design:
            n=s.multifocal_sectors*s.multifocal_rings
            if len(s.multifocal_design)!=n or not s.multifocal_design[0]:
                raise ValueError("Multifocal design must have sectors*rings rows and >=1 trial.")
            lengths={len(row) for row in s.multifocal_design}
            if len(lengths)!=1 or any(v not in (0,1) for row in s.multifocal_design for v in row):
                raise ValueError("Multifocal design must be a rectangular binary matrix.")
        if presentation and mode.carrier=="disparity" and d.mode=="mono":
            raise ValueError("Disparity stimuli require a binocular display mode.")
        if presentation and mode.windows:
            raise ValueError("Use the export command for *windows mode aliases.")
        if presentation and mode.carrier=="objects" and not s.object_source:
            raise ValueError("objects modes require object_source (native .npy bank/manifest or image directory).")
        return self

    def to_dict(self):
        return asdict(self)

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_dict(),indent=2,ensure_ascii=False)+"\n",encoding="utf-8")


def defaults(mode="ccwf"):
    c=ExperimentConfig(mode=mode)
    family=parse_mode(mode).family
    s,t=c.stimulus,c.timing
    if family=="eccentricity":
        s.checker_rings=2
        t.rest_s=10
    elif family=="bar":
        t.cycle_s,t.rest_s,t.repeats=40,8,1
        s.flicker_hz=4
        s.dot_refresh_hz=8
    elif family=="dual":
        s.max_radius_deg=7.5
    elif family=="multifocal":
        s.max_radius_deg,s.checker_wedges,s.checker_rings=7.5,36,9
        s.wedge_width_deg,s.start_angle_deg=360,0
    elif family in ("meridian","lgn","hrf","localizer"):
        s.checker_wedges=30
        s.wedge_width_deg=360
        s.start_angle_deg=0
        s.flicker_hz=3.75
        s.dot_refresh_hz=7.5
        if family=="meridian":
            s.wedge_width_deg,s.checker_wedges,s.max_radius_deg=24,4,7.5
            s.flicker_hz=5
            s.dot_refresh_hz=10
        elif family=="lgn":
            s.wedge_width_deg,s.start_angle_deg,s.checker_wedges=140,110,15
            s.max_radius_deg=7.5
        elif family=="hrf":
            t.cycle_s,t.rest_s=32,16
        else:
            s.max_radius_deg=7.5
            s.flicker_hz=5
            s.dot_refresh_hz=10
            t.block_s,t.rest_s=32,16
    return c


def _overlay(c,raw,path):
    if not isinstance(raw,dict):
        raise ValueError(f"Configuration must be an object: {path}")
    for key,value in raw.items():
        if key not in {f.name for f in fields(c)}:
            raise ValueError(f"Unknown configuration field: {key}")
        current=getattr(c,key)
        if hasattr(current,"__dataclass_fields__"):
            if not isinstance(value,dict):
                raise ValueError(f"{key} must be an object.")
            for sub,val in value.items():
                if sub not in current.__dataclass_fields__:
                    raise ValueError(f"Unknown configuration field: {key}.{sub}")
                setattr(current,sub,copy.deepcopy(val))
        else:
            setattr(c,key,value)
    # Resolve paths in the file that DEFINES them, before the next layer.
    stimulus=raw.get("stimulus",{})
    for key in ("object_source","object_cache_dir"):
        if stimulus.get(key):
            value=Path(stimulus[key])
            if not value.is_absolute():
                setattr(c.stimulus,key,str((Path(path).resolve().parent/value).resolve()))


def load_config(path=None, mode=None):
    """Explicit standalone JSON; never consult mutable subject templates."""
    raw=json.loads(Path(path).read_text(encoding="utf-8-sig")) if path else {}
    if not isinstance(raw,dict):
        raise ValueError("Configuration must be an object.")
    c=defaults(mode or raw.get("mode","ccwf"))
    _overlay(c,raw,path)
    # Infer compatibility only for recorded acquisition snapshots, never templates.
    if path and Path(path).name=="config.json":
        summary_path=Path(path).parent/"summary.json"
        if summary_path.is_file():
            summary=json.loads(summary_path.read_text(encoding="utf-8-sig"))
            version=re.match(r"^(\d+)\.(\d+)\.(\d+)",str(summary.get("version","")))
            recorded=tuple(map(int,version.groups())) if version else None
            if recorded is not None and recorded<=(0,2,2) and "spatial_convention" not in raw.get("stimulus",{}):
                c.stimulus.spatial_convention="legacy-python"
            if recorded is not None and recorded<=(0,3,0):
                if "temporal_convention" not in raw.get("stimulus",{}):c.stimulus.temporal_convention="legacy-python"
                if "disparity_assignment" not in raw.get("stimulus",{}):c.stimulus.disparity_assignment="random"
                if "schedule" not in raw.get("task",{}):c.task.schedule="interval"
                if "fixation_rendering" not in raw.get("task",{}):c.task.fixation_rendering="legacy-python"
                if "marker_timing" not in raw.get("display",{}):c.display.marker_timing="fixed"
                if "operator_confirm" not in raw.get("timing",{}):c.timing.operator_confirm=False
    if mode:
        c.mode=mode
    c._subjects_dir=str(SUBJECTS_ROOT)
    if path:
        participant=next((p for p in Path(path).resolve().parents if p.name==c.subject),None)
        if participant is not None:
            c._subjects_dir=str(participant.parent)
        cache=Path(c.stimulus.object_cache_dir)
        if not cache.is_absolute():
            c.stimulus.object_cache_dir=str((Path(path).resolve().parent/cache).resolve())
        c._configuration_sources=[str(Path(path).resolve())]
    return c.validate()


SUBJECTS_ROOT=Path(__file__).resolve().parents[1]/"subjects"
FAMILY_FILES={"polar":"c_pol.json","eccentricity":"c_ecc.json","dual":"c_dual.json",
              "bar":"c_bar.json","multifocal":"c_multifocal.json","meridian":"c_meridian.json",
              "lgn":"c_lgnlocalizer.json","hrf":"c_hrf.json","localizer":"c_localizer.json"}


def load_subject_config(subject,mode="ccwf",subjects_dir=None):
    """Layer file defaults, then participant overrides; absent files fall back.

    Each directory contributes common.json, retinotopy_display.json, its
    c_<family>.json, and optionally <mode>.json, in that order. Participant
    settings override every _DEFAULT_ setting. Lists replace whole lists.
    A resolved acquisition config is saved separately for exact replay.
    """
    c=defaults(mode)
    c.subject=subject
    c.validate()  # reject path traversal before constructing a subject path
    root=Path(subjects_dir or SUBJECTS_ROOT).resolve()
    mode=parse_mode(mode).name
    c.mode=mode
    filenames=("common.json","retinotopy_display.json",FAMILY_FILES[parse_mode(mode).family],mode+".json")
    sources=[]
    directories=[root/"_DEFAULT_"]
    if subject!="_DEFAULT_":
        directories.append(root/subject)
    for directory in directories:
        for filename in filenames:
            path=directory/filename
            if not path.is_file():
                continue
            raw=json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(raw,dict):
                raise ValueError(f"Configuration must be an object: {path}")
            if "mode" in raw and raw["mode"]!=mode:
                raise ValueError(f"Mode in {path} does not match requested {mode}.")
            if "subject" in raw and raw["subject"]!=subject:
                raise ValueError(f"Subject in {path} does not match requested {subject}.")
            _overlay(c,raw,path)
            sources.append(str(path))
    # A built-in relative fallback is rooted at the chosen subjects directory.
    for key in ("object_source","object_cache_dir"):
        value=getattr(c.stimulus,key)
        if value and not Path(value).is_absolute():
            setattr(c.stimulus,key,str((root/Path(value)).resolve()))
    c._configuration_sources=sources
    c._subjects_dir=str(root)
    return c.validate()
