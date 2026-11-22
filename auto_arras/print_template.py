"""Utils for printing template to arras.io."""


from time import sleep
from math import cos, sin, pi

from pynput import mouse, keyboard
from screeninfo import get_monitors
import typer
import pyautogui
from PIL import ImageOps
from .utils.gen_utils import compile_template
from typing import Annotated, Optional

from .config import TANK_FOV, WALLS_COLOR_COUNT, WALLS_TYPE_COUNT, JOINTS_TYPE_COUNT, POLYGON_SIZE_COUNT, POLYGON_TIER_COUNT, POLYGON_TYPE_COUNT, POLYGON_SIZE_MOVE_OFFSET, POLYGON_TIER_MOVE_OFFSET, POLYGON_TYPE_MOVE_OFFSET

app = typer.Typer()



mc = mouse.Controller()
kc = keyboard.Controller()

cur_joint = 0
cur_polygon = [0, 0, 0]

def get_micro_instructions(instruction) -> list[str]:
    global cur_joint
    com = instruction
    tokens = instruction.split()
    command = tokens[0]

    i = tokens[1:]
    arg_len = len(i)
    i.extend([0] * (5 - arg_len))
    try:
        MICRO_INSTRUCTIONS_TABLE = {
            'wall': {
                2: (
                    f'm {i[0]} {i[1]}',
                    't x'
                ),
                4: (
                    f'm {i[0]} {i[1]}',
                    'p x',
                    
                    f'lm {i[2]} {i[3]}',
                    'r x',
                )
            },
            'type_wall': {
                2: (
                    f'm {i[0]} {i[1]}',
                    't x'
                ),
                3: (
                    f'm {i[0]} {i[1]}',
                    't x',
                    'p z',
                    f'tm {i[2]}',
                    'r z',
                ),
                4: (
                    f'm {i[0]} {i[1]}',
                    'p x',
                    f'lm {i[2]} {i[3]}',
                    'r x',
                ),
                5: (
                    f'm {i[0]} {i[1]}',
                    'p x',
                    'p z',
                    f'tm {i[4]}',
                    'r z',
                    f'lm {i[2]} {i[3]}',
                    'r x',
                ),
            },
            'color_wall': {
                2: (
                    f'm {i[0]} {i[1]}',
                    't x',
                    'lt c'
                ),
                3: (
                    f'm {i[0]} {i[1]}',
                    't x',
                    'p c',
                    f'cm {i[2]}',
                    'r c',
                ),
                4: (
                    f'm {i[0]} {i[1]}',
                    'p x',
                    'lt c',
                    f'lm {i[2]} {i[3]}',
                    'r x',
                ),
                5: (
                    f'm {i[0]} {i[1]}',
                    'p x',
                    'p c',
                    f'cm {i[4]}',
                    'r c',
                    's',
                    f'lm {i[2]} {i[3]}',
                    'r x',
                ),
            },
            'color': {
                2: (
                    f'm {i[0]} {i[1]}',
                    'lt c'
                ),
                3: (
                    f'm {i[0]} {i[1]}',
                    'p c',
                    f'cm {i[2]}',
                    'r c'
                ),
                5: (
                    f'm {(float(i[0]) + float(i[2])) / 2} {(float(i[1]) + float(i[3])) / 2}',
                    'p c',
                    f'cm {i[4]}',
                    'r c'
                )
            },
            'wall_type': {
                3: (
                    f'm {i[0]} {i[1]}',
                    'p z',
                    f'tm {i[2]}',
                    'r z',
                )
            },
            'joint': {
                4: (
                    f'm {i[0]} {i[1]}',
                    'p j',
                    f'lm {i[2]} {i[3]}',
                    'r j'
                ),
                5: (
                    f'm {-1} {-1}',
                    f'sj {i[4]}',
                    f'm {i[0]} {i[1]}',
                    'p j',
                    f'lm {i[2]} {i[3]}',
                    'r j',
                ),
            },
            'polygon': {
                2: (
                    f'm {i[0]} {i[1]}',
                    't f'
                ),
                5: (
                    f'm {i[0]} {i[1]}',
                    't f',
                    'p z',
                    f'pcm {i[2]}',
                    'r z',
                    f'm {i[0]} {i[1]}',
                    'p z',
                    f'psm {i[3]}',
                    'r z',
                    f'm {i[0]} {i[1]}',
                    'p z',
                    f'ptm {i[4]}',
                    'r z',
                )
            },
            'polygon_type': {
                2: (
                    f'm {i[0]} {i[1]}',
                ),
                5: (
                    f'm {i[0]} {i[1]}',
                    'p z',
                    f'pcm {i[2]}',
                    'r z',
                    f'm {i[0]} {i[1]}',
                    'p z',
                    f'psm {i[3]}',
                    'r z',
                    f'm {i[0]} {i[1]}',
                    'p z',
                    f'ptm {i[4]}',
                    'r z',
                )
            },
            'team': {
                0: (
                    't y',
                )
            }
        }
    except ValueError:
        return [com]

    try:
        return MICRO_INSTRUCTIONS_TABLE[command][arg_len]
    except KeyError:
        return [com]


def find_pixel(s, color, px_amplitude=2):
    s = ImageOps.grayscale(s)
    for x in range(s.width):
        for y in range(s.height):
            if color - px_amplitude/2 <= s.getpixel((x, y)) <= color + px_amplitude/2:
                return x, y
    return None


def apply_fov(wall_size: float, tank: str) -> float:
    return wall_size * TANK_FOV[tank]


def apply_lvl(wall_size: float, lvl: int) -> float:
    lvl_multiplier = lvl / 45
    return wall_size * lvl_multiplier


def apply_screen_height(wall_size: float) -> float:
    screen = get_monitors()[0]
    screen_height_multiplier = screen.height / 1440
    return wall_size * screen_height_multiplier


def get_px_wall_size(
    arena_size: int,
    tank: str,
    lvl: int
) -> float:
    wall_size = apply_fov(arena_size, tank)
    wall_size = apply_lvl(wall_size, lvl)
    wall_size = apply_screen_height(wall_size)
    return wall_size


def wall_pos_to_px(
    wall_pos: tuple[int | str, int | str] | list[str],
    wall_px_size: float,
    px_offset: tuple[float, float] | list[str] = (0, 0)
) -> tuple[int, int]:

    """Converts grid position to screen position.

    If get strings, tries to convert them into number.
    """

    rx = int(float(wall_pos[0]) * float(wall_px_size) + float(px_offset[0]))
    ry = int(float(wall_pos[1]) * float(wall_px_size) + float(px_offset[1]))

    return rx, ry


def angle_to_vector(angle):
    """Converts angle to vector."""

    rad_angle = angle * pi / 180
    return (sin(rad_angle), -cos(rad_angle))


def type_to_position(
    type_index, type_count, wall_px_size: float, offset=(0, 0)
):
    """Converts type to position."""

    type_max_angle = 360 / type_count
    type_vector = angle_to_vector(type_max_angle * (float(type_index) + 0.5))
    type_vector = wall_pos_to_px(type_vector, 64, offset)
    return type_vector

def polygon_size_move(siz, wall_px_size, offset=(0, 0)):
    global cur_polygon
    siz = int(siz)
    size = (siz + POLYGON_SIZE_COUNT - cur_polygon[1]) % POLYGON_SIZE_COUNT
    cur_polygon[1] = siz
    w_offset = (size * POLYGON_SIZE_MOVE_OFFSET, 0)
    #print(cur_polygon, 'a', size)
    return wall_pos_to_px(w_offset, wall_px_size, offset)

def polygon_tier_move(tier, wall_px_size, offset=(0, 0)):
    global cur_polygon
    tier = int(tier)
    size = (tier + POLYGON_TIER_COUNT - cur_polygon[2]) % POLYGON_TIER_COUNT
    cur_polygon[2] = tier
    w_offset = (size * POLYGON_TIER_MOVE_OFFSET * 0.70710678, size * POLYGON_TIER_MOVE_OFFSET * 0.70710678)
    #print(cur_polygon, 'a', size)
    return wall_pos_to_px(w_offset, wall_px_size, offset)

def polygon_class_move(typ, wall_px_size, offset=(0, 0)):
    global cur_polygon
    typ = int(typ)
    size = (typ + POLYGON_TYPE_COUNT - cur_polygon[0]) % POLYGON_TYPE_COUNT
    cur_polygon[0] = typ
    w_offset = (size * POLYGON_TYPE_MOVE_OFFSET * -0.70710678, size * POLYGON_TYPE_MOVE_OFFSET * 0.70710678)
    #print(cur_polygon, 'a', size)
    return wall_pos_to_px(w_offset, wall_px_size, offset)

def select_joint(joint, press_interval):
    global cur_joint
    joint = int(joint)
    joff = (joint + JOINTS_TYPE_COUNT - cur_joint) % JOINTS_TYPE_COUNT
    cur_joint = joint
    for i in range(joff):
        kc.press('j')
        kc.release('j')
        sleep(press_interval)

def exec_instruction(
    instruction: str,
    wall_px_size: float,
    mouse_og_pos: tuple[float, float] | list[str],
    press_interval: float,
):
    """Compiles macro instruction."""

    instruction = instruction.strip()

    tokens = instruction.split()
    command = tokens[0]
    args = tokens[1:]
    args_len = len(args)
    do_sleep = True

    if args_len > 0:
        if args[-1] == 'i':
            do_sleep = False
            args.pop()

    match command:
        case 'p':
            kc.press(args[0])
        case 'r':
            kc.release(args[0])
        case 't':
            kc.press(args[0])
            kc.release(args[0])
        case 'lt':
            kc.press(args[0])
            sleep(press_interval)
            kc.release(args[0])
        case 'm':
            mc.position = wall_pos_to_px(args[:2], wall_px_size, mouse_og_pos)
        case 'lm':
            mc.position = wall_pos_to_px(args[:2], wall_px_size, mouse_og_pos)
        case 'tm':
            mc.position = type_to_position(
                    args[0], WALLS_TYPE_COUNT, wall_px_size, mc.position
                )
        case 'cm':
            mc.position = type_to_position(
                    args[0], WALLS_COLOR_COUNT, wall_px_size, mc.position
                )
        case 'psm':
            mc.position = polygon_size_move(args[0], wall_px_size, mc.position)
        case 'ptm':
            mc.position = polygon_tier_move(args[0], wall_px_size, mc.position)
        case 'pcm':
            mc.position = polygon_class_move(args[0], wall_px_size, mc.position)
        case 'sj':
            select_joint(args[0], press_interval)
        case 's':
            sleep(press_interval)
        case 'ls':
            sleep(press_interval*3)


@app.callback(invoke_without_command=True)
def paste(
    template: Annotated[Optional[typer.FileText], typer.Option("--template", "-t")] = "template.txt",
    arena_size: Annotated[Optional[int], typer.Option("--arena-size", "-s")] = 64,
    lvl: int = 45,
    tank: str = 'spectator',
    press_interval: Annotated[Optional[float], typer.Option("--press-interval", "-p")] = 0.05,
    seconds_before_paste: float = 5,
    grid_search_radius: int = 20,
    snap_to_grid: bool = False,
    snap_offset: float = 0.5,
):
    """Pastes template in arras.io from text or file."""
    
    template = compile_template(template)

    input(f"""Press enter to paste. It will start after {seconds_before_paste} seconds.
NOTE: BEFORE PASTING STARTS YOU NEED TO:
 - BE IN FULLSCREEN MODE OF ARRAS.IO
 - HAVE FORCE 16:9 ASPECT RATIO ENABLED(arras.io Settings > Secrets)
 - HAVE DEFAULT ZOOM FOR YOUR TANK
 - HAVE TANK {tank}
 - HAVE LEVEL {lvl}
OR ELSE THE MACRO WILL WORK WRONG.""")
    sleep(seconds_before_paste)

    wall_px_size: float = get_px_wall_size(arena_size, tank, lvl)
    mouse_og_pos = mc.position

    if snap_to_grid:
        # Snapping mouse to grid
        grid_screenshot = pyautogui.screenshot(region=(
            mouse_og_pos[0] - grid_search_radius,
            mouse_og_pos[1] - grid_search_radius,
            grid_search_radius * 2,
            grid_search_radius * 2
        ))

        corner_color = 211
        grid_corner = find_pixel(grid_screenshot, corner_color)
        snap_offset = max(snap_offset * wall_px_size, 27.69792)
        if grid_corner is not None:
            mouse_og_pos = (
                grid_corner[0] + mouse_og_pos[0] - grid_search_radius + wall_px_size/2,
                grid_corner[1] + mouse_og_pos[1] - grid_search_radius + wall_px_size/2
            )
            mc.position = mouse_og_pos

    #sleep(1)
    
    cur_joint = 0

    kc.press('`')
    for instruction in template:
        micro_instructions = get_micro_instructions(instruction)
        for micro_instruction in micro_instructions:
            exec_instruction(
                micro_instruction, wall_px_size, mouse_og_pos, press_interval
            )
            sleep(press_interval)
    kc.release('`')
