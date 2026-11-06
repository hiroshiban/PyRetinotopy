"""PyRetinotopy, derived from Hiroshi Ban's MATLAB Retinotopy package.

Geometry, schedules and exports can be used without importing PsychoPy.
"""

__version__ = "0.4.0"

from .config import ExperimentConfig, load_config
from .design import Design
from .modes import Mode, parse_mode

__all__ = ["ExperimentConfig", "load_config", "Design", "Mode", "parse_mode"]
