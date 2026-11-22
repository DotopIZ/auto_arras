"""Subcommands for generating templates."""

from typing import Any

import typer
from PIL import Image
from typing import Annotated, Optional


from .utils.optimize_indexes import to_walls, get_squares, color_squares, read_schematic
from .utils.image_manipulation import (
    resize_image, quantize_to_palette, black_and_white,
)
from .config import WALL_COLORS, WALL_TYPE_COLORS, POLYGON_SIZE_COUNT, POLYGON_TIER_COUNT, POLYGON_TYPE_COUNT
from .utils.util_types import FilePathType
from .utils.template_utils import save_template
from .utils.gen_utils import compile_template

# pylint: disable=no-member


app = typer.Typer()


@app.callback()
def generate(save_path: Annotated[Optional[typer.FileTextWrite], typer.Option("--save-path", "-s")] = "template.txt", print_result: bool = False):
    """Generates template and saves it in file."""
    
    

    return save_path


def result_callback(function_result: Any, save_path: typer.FileTextWrite, print_result: bool = False):
    """Saves generation result to file."""

    if print_result:
        print(function_result)
    print("Готово!")
    return save_template(function_result, save_path)


app = typer.Typer(callback=generate, result_callback=result_callback)


@app.command()
def image(
    image_path: FilePathType,
    resize: Annotated[Optional[tuple[int, int]], typer.Option("--resize", "-r")] = None,
    keep_aspect_ratio: Annotated[Optional[bool], typer.Option("--keep-aspect-ratio/--dont-keep-aspect-ratio", "-k/-K")] = True,
    color: Annotated[Optional[bool], typer.Option("--colorful/--colorless", "-c/-C")] = True,
    dither: Annotated[Optional[bool], typer.Option("--dither", "-d")] = False,
    resample:  Annotated[Optional[bool], typer.Option("--resample", "-s")] = False,
    bw_threshold: Annotated[Optional[int], typer.Option("--b&w_threshold", "-b")] = 127,
    bw_invert: Annotated[Optional[bool], typer.Option("--invert/--dont-invert", "-i/-I")] = False,
    optimize: Annotated[Optional[bool], typer.Option("--optimize/--dont-optimize", "-o/-O")] = True,
    preview: Annotated[Optional[bool], typer.Option("--preview/--dont-preview", "-p/-P")] = True,
    joint: bool = False,
) -> list[str]:
    """Converts image to walls."""

    img: Image.Image = Image.open(image_path)

    if resize is not None:
        img = resize_image(img, resize, keep_aspect_ratio, resample)

    if color:
        img = quantize_to_palette(img, WALL_COLORS, dither)
    else:
        img = black_and_white(img, WALL_COLORS, bw_threshold, bw_invert)
    
    if optimize:
        if color:
            image_template, wall_count = color_squares(img, joint=joint)
        else:
            image_template, skip, wall_count = get_squares(img, True, joint=joint)
    else:
        image_template, wall_count = to_walls(img)
    print(f"Сгенерерировано {wall_count} стен, чтоб стереть напиши 'python main.py generate clear {wall_count}' и затем 'python main.py paste'")

    if preview:
        print("Открыто превью полученного изображение")
        img.save("preview.png") # in case img.show doesnt work
        img.show("Превью полученного изображения")

    return image_template


@app.command()
def schematic(
    image_path: FilePathType,
    ignore_color: tuple[int, int, int, int] = (255, 255, 255, 255),
    preview: Annotated[Optional[bool], typer.Option("--preview/--dont-preview", "-p/-P")] = True,
) -> list[str]:
    """Converts schematic image to walls."""

    img: Image.Image = Image.open(image_path)

    img = quantize_to_palette(img, WALL_TYPE_COLORS)
    ret = read_schematic(img)

    if preview:
        print("Открыто превью схематики")
        img.show("Превью схематики")

    return ret


@app.command()
def clear(times: int):
    """Uses whirpool and kill to delete entities"""
    ret = ['t w', 't k'] * times
    return ret

@app.command()
def ruler(ruler_length: int):
    """Debug ruler used to calibrate tank FOV multiplier."""

    template = []
    for wall_x in range(0, ruler_length+1):
        wall_y = wall_x % 2
        wall_y = round(wall_y)

        command = f'wall {wall_x} {wall_y}'
        template.append(command)

    return template

@app.command()
def polygons():
    """Generates a grid of polygons of different type size and tier"""
    ret = []
    for a in range(POLYGON_TYPE_COUNT):
        for b in range(POLYGON_SIZE_COUNT):
            for c in range(POLYGON_TIER_COUNT):
                ret.append(f"polygon {a*2+c*2} {b*2} {a} {b} {c}")
    return ret

@app.command()
def compile(template: typer.FileText):
    """Compiles template file by replacing cmds with their aliases. Print template does it by default."""
    print(f"TILE {template}")
    return compile_template(template)
