"""Utils for printing template to arras.io."""


from time import sleep
from math import cos, sin, pi

from pynput import mouse, keyboard
import typer


# uv run main.py paste --arena-size 8 --press-interval 0.08 templates/bad_apple.txt

# uv run main.py generate templates/bad_apple_400x400.txt image images/bad_apple.png --resize 400 400

app = typer.Typer()

WALLS_TYPE_COUNT = 19

mc = mouse.Controller()
kc = keyboard.Controller()


def cell_to_px(
    cell_pos: tuple[int | str, int | str] | list[str],
    cell_size: float,
    px_offset: tuple[float, float] | list[str]
) -> tuple[int, int]:

    """Converts grid position to screen position.

    If get strings, tries to convert them into number.

    Args:
        cell_pos (tuple[int, int]): grid position
        px_offset (tuple[int, int], optional): pixel offset. Defaults to (0, 0)

    Returns:
        tuple[int, int]: screen position
    """

    rx = int(float(cell_pos[0]) * float(cell_size) + float(px_offset[0]))
    ry = int(float(cell_pos[1]) * float(cell_size) + float(px_offset[1]))

    return rx, ry


def angle_to_vector(angle):
    """Converts angle to vector."""

    angle = angle * pi / 180
    return (sin(angle), -cos(angle))


def type_to_position(
    type_index, type_count, cell_size, offset=(0, 0)
):
    """Converts type to position."""

    type_angle = 360 / type_count
    type_vector = angle_to_vector(type_angle * (float(type_index) + 0.5))
    type_vector = cell_to_px(type_vector, cell_size, offset)
    return type_vector


def exec_instruction(
    instruction: str,
    cell_size: float,
    mouse_og_pos: tuple[float, float] | list[str],
    press_interval: float,
):
    """Executes template's instruction."""

    instruction = instruction.strip()

    tokens = instruction.split()
    command = tokens[0]
    args = tokens[1:]
    args_len = len(args)

    if args_len >= 2:
        mc.position = cell_to_px(args[:2], cell_size, mouse_og_pos)
    m_position_before = mc.position
    sleep(press_interval)

    kc.press(command)
    if args_len >= 3:
        sleep(press_interval)
        match command:
            case 'x':
                mc.position = cell_to_px(args[2:4], cell_size, mouse_og_pos)
            case 'z':
                mc.position = type_to_position(
                    args[2], WALLS_TYPE_COUNT, cell_size, mc.position
                )
        sleep(press_interval)
    kc.release(command)

    tokens.extend([str(m_position_before), str(mc.position)])

    for i in (tokens):
        print(f'{str(i):<5}', end=' ')
    print('')


@app.callback(invoke_without_command=True)
def paste(
    template: typer.FileText,
    cell_size: float = 0.395,
    arena_size: int = 64,
    press_interval: float = 0.01,
):
    """Pastes template in arras.io from text or file."""

    input('Press enter to paste. It will start after 5 seconds.')
    sleep(5)

    cell_size = arena_size * cell_size
    mouse_og_pos = mc.position

    print(f'TEMPLATE: {template}')
    print(f'ARENA_SIZE: {arena_size}')
    print(f'CELL_SIZE: {cell_size}')
    print(f'MOUSE_OG_POSITION: {mouse_og_pos}')
    print(f'PRESS_INTERVAL: {press_interval}')

    kc.press('`')
    for instruction in template:
        exec_instruction(instruction, cell_size, mouse_og_pos, press_interval)
        sleep(press_interval)
    kc.release('`')
