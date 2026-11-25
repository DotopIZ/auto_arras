"""Вспомогательные функции для UI."""


def rgba_list_to_hex(col, rev=False):
    r, g, b, a = col
    if rev:
        r, b = b, r
    return f"#{b:02x}{g:02x}{r:02x}"


def get_contrast_color(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return "black"
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "white" if luminance < 0.5 else "black"
    except Exception:
        return "black"


def safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default