from .utils.config_utils import *

WALL_COLORS, wall_colors_to_index = parse_wall_list([
    [203, 164, 60, 255],
    [63, 188, 138, 255],
    [65, 62, 224, 255],
    [156, 102, 204, 255],
    [128, 243, 253, 255],
    [111, 111, 114, 255],
    [247, 235, 232, 255],
    [75, 199, 239, 255],
    [109, 137, 231, 255],
    [223, 106, 141, 255],
    [186, 219, 122, 255],
    [195, 153, 239, 255],
    [126, 232, 185, 255],
    [219, 211, 122, 255],
    [173, 164, 164, 255],
    [72, 72, 72, 255],
    [167, 167, 175, 255],
    [255, 255, 255, 255],
    [219, 219, 219, 255],
    [0, 0, 0, 255],
])

WALL_TYPE_COLORS, wall_type_colors_to_index = parse_wall_list([
])

EDITOR_TOOLS = {
    "WALLS": {
        "WALL": [[173, 164, 164, 255]],
        "DMG": [[65, 62, 224, 255]],
        "HEAL": [[63, 188, 138, 255]],
        "BNCE": [[0, 0, 0, 255]],
        "SHRNK": [[195, 153, 239, 255]],
        "GROW": [[186, 219, 122, 255]],
        "EYE": [[75, 199, 239, 255]],
        "UP": [[111, 111, 114, 255]],
        "DOWN": [[111, 111, 114, 255]],
        "LEFT": [[111, 111, 114, 255]],
        "RIGHT": [[111, 111, 114, 255]],
        "STICK": [[247, 235, 232, 255]],
        "FAKE": [[173, 164, 164, 255]],
        "COL CH": [[247, 235, 232, 255]],
        "COL FL": [[247, 235, 232, 255]],
        "TM CH": [[65, 62, 224, 255]],
        "TM FL": [[65, 62, 224, 255]],
        "TP": [[203, 164, 60, 255]],
        "RSPWN": [[63, 188, 138, 255]]
    }
}

EDITOR_TOOL_TO_ID = {}

for group, tools in EDITOR_TOOLS.items():
    for i, k in enumerate(tools.keys()):
        EDITOR_TOOL_TO_ID[k] = str(i)




WTC_TRNSP_PX_ID = len(WALL_TYPE_COLORS) - 1
WC_TRNSP_PX_ID =  len(WALL_COLORS) - 1

WALLS_TYPE_COUNT = 19
WALLS_COLOR_COUNT = 20

TANK_FOV = {
    'spectator': 0.43278
}

MAX_WALL_SIZE = 64
