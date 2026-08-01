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
        "RSPWN": [[63, 188, 138, 255]],
        "PRWALL": [[173, 164, 164, 255]]
    },
    "JOINTS": {
        "FIXED": [[0, 255, 255, 255], [], "line"],
        "MIN DIST": [[0, 85, 0, 255], [], "line"],
        "MAX DIST": [[0, 170, 0, 255], [], "line"],
        "FIX DIST": [[0, 255, 0, 255], [], "line"],
        "FIX ANGL": [[0, 0, 255, 255], [], "line"],
        "FIX ANGL MIN DIST": [[0, 85, 255, 255], [], "line"],
        "FIX ANGL MAX DIST": [[0, 170, 255, 255], [], "line"],
    },
    "OTHER": {
        "POLY": [[112, 146, 190, 255], ["CLASS", "SIZE", "TIER"]],
    },
}

EDITOR_TOOL_TO_ID = {}

for group, tools in EDITOR_TOOLS.items():
    print(f"{group=}")
    for i, k in enumerate(tools.keys()):
        print(f"{i=} {k=}")
        EDITOR_TOOL_TO_ID[k] = str(i)

EDITOR_TOOL_TO_GROUP = {}

for group, tools in EDITOR_TOOLS.items():
    for k in tools.keys():
        EDITOR_TOOL_TO_GROUP[k] = group



WTC_TRNSP_PX_ID = len(WALL_TYPE_COLORS) - 1
WC_TRNSP_PX_ID =  len(WALL_COLORS) - 1

WALLS_TYPE_COUNT = 19
WALLS_COLOR_COUNT = 20

JOINTS_TYPE_COUNT = 7

POLYGON_SIZE_COUNT = 5
POLYGON_TIER_COUNT = 6
POLYGON_TYPE_COUNT = 5
POLYGON_SIZE_MOVE_OFFSET = 2 / 6 * POLYGON_SIZE_COUNT
POLYGON_TIER_MOVE_OFFSET = 2 / 6 * POLYGON_TIER_COUNT
POLYGON_TYPE_MOVE_OFFSET = 2 / 6 * POLYGON_TYPE_COUNT

TANK_FOV = {
    'spectator': 0.43278
}

MAX_WALL_SIZE = 64
