"""
Centralized styling constants for HTML reports.
Consolidates colors, spacing, typography, and reusable style definitions
used across all report variants.
"""

# ─────────────────────────────────────────────
# Color Palette
# ─────────────────────────────────────────────
COLORS = {
    "success": "#22c55e",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "muted": "#94a3b8",
    "text_primary": "#1e293b",
    "text_secondary": "#475569",
    "text_tertiary": "#64748b",
    "text_disabled": "#cbd5e1",
    "bg_light": "#f8fafc",
    "bg_lighter": "#f1f5f9",
    "border": "#cbd5e1",
    "error_bg": "#fef2f2",
    "error_text": "#b91c1c",
    "error_border": "#fecaca",
    "warning_bg": "#fffbeb",
    "warning_text": "#92400e",
    "warning_border": "#fde68a",
    "minor_bg": "#f8fafc",
    "minor_text": "#475569",
    "minor_border": "#e2e8f0",
}

# ─────────────────────────────────────────────
# Typography
# ─────────────────────────────────────────────
FONTS = {
    "family": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    "weight_normal": "400",
    "weight_medium": "500",
    "weight_semibold": "600",
    "weight_bold": "700",
    "weight_extrabold": "800",
}

# ─────────────────────────────────────────────
# Spacing
# ─────────────────────────────────────────────
SPACING = {
    "xs": "4px",
    "sm": "8px",
    "md": "12px",
    "lg": "14px",
    "xl": "16px",
    "xxl": "24px",
    "xxxl": "32px",
}

# ─────────────────────────────────────────────
# Score Badge Styles
# ─────────────────────────────────────────────
SCORE_STYLES = {
    "PASS": ("✓", COLORS["success"]),
    "FAIL": ("✗", COLORS["danger"]),
    "N/A": ("–", COLORS["muted"]),
    "ERROR": ("!", COLORS["warning"]),
}

# ─────────────────────────────────────────────
# Severity Badge Styles
# ─────────────────────────────────────────────
SEVERITY_STYLES = {
    "Critical": (COLORS["error_bg"], COLORS["error_text"], COLORS["error_border"]),
    "Major": (COLORS["warning_bg"], COLORS["warning_text"], COLORS["warning_border"]),
    "Minor": (COLORS["minor_bg"], COLORS["minor_text"], COLORS["minor_border"]),
}

# ─────────────────────────────────────────────
# Common Inline Styles
# ─────────────────────────────────────────────
STYLES = {
    "badge": (
        "display:inline-flex;align-items:center;gap:4px;"
        "color:#fff;padding:3px 10px;border-radius:20px;"
        "font-weight:700;font-size:0.78em;letter-spacing:0.03em"
    ),
    "badge_rate": (
        "display:inline-flex;align-items:center;gap:4px;"
        "color:#fff;padding:3px 10px;border-radius:20px;"
        "font-weight:700;font-size:0.78em"
    ),
    "failure_category_pill": (
        "background:{bg};color:{text};border:1px solid {border};"
        "padding:1px 7px;border-radius:20px;font-size:0.78em;font-weight:600"
    ),
    "severity_pill": (
        "background:{bg};color:{text};border:1px solid {border};"
        "padding:2px 8px;border-radius:20px;font-size:0.75em;"
        "font-weight:700;white-space:nowrap"
    ),
}


def table_header_style() -> str:
    """Common table header cell styling."""
    return (
        f"padding:{SPACING['lg']} {SPACING['lg']};white-space:nowrap;font-weight:600;"
        f"text-align:center;border-bottom:2px solid {COLORS['border']};vertical-align:bottom"
    )


def table_cell_style() -> str:
    """Common table cell styling."""
    return f"padding:{SPACING['lg']} {SPACING['lg']};font-weight:600;color:{COLORS['text_primary']}"


def badge_style(background_color: str) -> str:
    """Generate badge style with given background color."""
    return f"{STYLES['badge']};background:{background_color}"


def badge_rate_style(background_color: str) -> str:
    """Generate rate badge style with given background color."""
    return f"{STYLES['badge_rate']};background:{background_color}"
