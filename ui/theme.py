"""ClassFlow's shared visual language.

Change these color values to update the Phase 1 dashboard, navigation and
login accents together. The original login layout and image slots are retained.
"""

COLORS = {
    "ink": "#19263B",
    "muted": "#708097",
    "blue": "#3479E8",
    "deep_blue": "#2955CE",
    "purple": "#9D42E5",
    "orange": "#F39A1D",
    "green": "#1AB883",
    "sky": "#2B9CDB",
    "surface": "#FFFFFF",
    "page": "#F1F5FC",
    "border": "#E4EAF3",
    "nav_hover": "#EFF3FB",
}


def gradient(left=None, right=None):
    """Qt stylesheet gradient used by active navigation and feature panels."""
    return ("qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 "
            f"{left or COLORS['blue']},stop:1 {right or COLORS['purple']})")
