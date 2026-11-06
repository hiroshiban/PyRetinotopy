"""Legacy wrapper names, with explicit stimulus and attention semantics."""
from dataclasses import dataclass

BASES = ("ccw", "cw", "exp", "cont", "bar", "ccwexp", "ccwcont", "cwexp",
         "cwcont", "multifocal", "meridian", "lgn", "hrf", "localizer")
SUFFIXES = {"": ("checker", "stimulus"), "f": ("checker", "fixation"),
            "d": ("disparity", "stimulus"), "df": ("disparity", "fixation"),
            "i": ("objects", "fixation")}
DISPLAY_MODES = ("mono", "parallel", "cross", "dual", "dualparallel", "dualcross",
                 "topbottom", "bottomtop", "redgreen", "greenred", "redblue",
                 "bluered", "interleavedline", "interleavedcolumn", "shutter")


@dataclass(frozen=True)
class Mode:
    name: str
    base: str
    carrier: str
    task: str
    windows: bool = False

    @property
    def family(self):
        if self.base in ("ccw", "cw"):
            return "polar"
        if self.base in ("exp", "cont"):
            return "eccentricity"
        if self.base in ("ccwexp", "ccwcont", "cwexp", "cwcont"):
            return "dual"
        return self.base


def all_modes():
    return tuple(base + suffix for base in BASES for suffix in SUFFIXES)


def parse_mode(name):
    name = name.lower()
    if name.endswith("windows"):
        base = name[:-7]
        if base not in BASES[:10]:
            raise ValueError("Window aliases support wedges, rings, bars, dual and multifocal.")
        return Mode(name, base, "checker", "none", True)
    for base in sorted(BASES, key=len, reverse=True):
        if name.startswith(base) and name[len(base):] in SUFFIXES:
            carrier, task = SUFFIXES[name[len(base):]]
            return Mode(name, base, carrier, task)
    raise ValueError(f"Unknown stimulus mode: {name!r}. Use the list command.")
