"""Subcommands for generating templates."""

from typing import Any

import cv2
import typer

from .utils.optimize_indexes import optimize_indexes
from .utils.image_manipulation import (
    resize_image, get_indexes_of_pixels
)
from .utils.util_types import FilePathType
from .utils.template_utils import save_template


# pylint: disable=no-member

app = typer.Typer()


@app.callback()
def generate(save_path: typer.FileTextWrite):
    """Generates template and saves it in file."""

    return save_path


def result_callback(function_result: Any, save_path: typer.FileTextWrite):
    """Saves generation result to file."""

    return save_template(function_result, save_path)


app = typer.Typer(callback=generate, result_callback=result_callback)


@app.command()
def image(
    image_path: FilePathType,
    resize: tuple[int, int] | None = None,
    keep_aspect_ratio: bool = False,
) -> list[str]:
    """Converts image to walls."""

    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)

    if resize:
        img = resize_image(img, resize, keep_aspect_ratio)

    """
    blur = cv2.medianBlur(img, 5)
    sharpen_kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpen = cv2.filter2D(blur, -1, sharpen_kernel)
    """

    pixels = img < 129

    img_size = img.shape
    indexes_of_pixels = get_indexes_of_pixels(pixels)
    image_template = optimize_indexes(indexes_of_pixels, img_size)

    return image_template


@app.command()
def ruler(ruler_length: int):
    """Debug ruler."""

    template = []
    for wall_x in range(0, ruler_length+1):
        wall_y = wall_x % 2
        wall_y = round(wall_y)

        command = f'x {wall_x} {wall_y}'
        template.append(command)

    return template
