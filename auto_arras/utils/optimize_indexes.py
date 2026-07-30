"""Tool for optimizing clusters of walls into big walls."""

from rich.progress import track
from ..config import MAX_WALL_SIZE, WTC_TRNSP_PX_ID, WC_TRNSP_PX_ID, WALLS_COLOR_COUNT, WALLS_TYPE_COUNT
from PIL import Image, ImageChops
import heapq
import numpy as np
from time import sleep


def get_squares(img: Image.Image, trnsp: bool = False, color: int | None = None, skip_mask: np.array | None = None, joint: bool = False):
    if trnsp:
        img = img.point(lambda i: 1 if i == 20 else 0)
    img_width, img_height = img.size
    max_square_size = min(img_width, img_height)
    if skip_mask is None:
        skip_mask = np.zeros((img_height, img_width))
    # adding 1s to size to prevent indexError(lazy shitty fix)
    square_size_on_pixel = np.zeros((img_height + 1, img_width + 1), dtype=np.uint16)
    img_loaded = img.load()
    squares: list[tuple[int, int, int]] = []
    for y in range(img_height-1, 0, -1):
        for x in range(img_width-1, 0, -1):
            pixel = img_loaded[x, y]
            #print(f'{str(pixel):>3}', end='')
            if pixel:
                square_size = min(
                    square_size_on_pixel[y + 1, x],
                    square_size_on_pixel[y, x + 1],
                    square_size_on_pixel[y + 1, x + 1],
                    MAX_WALL_SIZE - 1,
                ) + 1
                square_size_on_pixel[y, x] = square_size
                squares.append((square_size, x, y))
        #print('\n', end='')
    squares.sort(key=lambda i:(max_square_size - i[0], i[1:]))
    result_squares = []
    ret = []
    wall_count = 0
    for index, square in enumerate(squares):
        size, x, y = square
        if not skip_mask[y, x]:
            skip_mask[y:(y + size), x:(x + size)] = 1
            result_squares.append((square))
            wall_count += 1
            if color is None:
                ret.append(f"wall {x} {y} {(x + size - 1)} {(y + size - 1)}")
            else:
                if index == 0:
                    ret.append(f"color_wall {x} {y} {(x + size - 1)} {(y + size - 1)} {color}")
                else:
                    ret.append(f"color_wall {x} {y} {(x + size - 1)} {(y + size - 1)}")
            if joint:
                ret.append(f"joint {x} {y} -1 -1")
    #print(square_size_on_pixel, squares, "\nres\n", skip_mask, result_squares)
    return ret, skip_mask, wall_count


def color_squares(img: Image.Image, backgr: bool = False, joint: bool = True):
    ret = []
    wall_count = 0
    img_width, img_height = img.size
    colors = [[i, 0, Image.new("1", img.size, color=0)] for i in range(WALLS_COLOR_COUNT)]
    for index, pixel in enumerate(img.getdata()):
        if pixel == WC_TRNSP_PX_ID:
            continue
        x = index % img_width
        y = index // img_width
        colors[pixel][1] += 1
        colors[pixel][2].putpixel((x, y), 255)
    colors.sort(key=lambda i: (i[1], i[0]))
    skip_mask = np.zeros((img_height, img_width), dtype=np.uint8)
    color_img = Image.new('1', img.size)
    if joint:
        ret.append("wall -1 -1")
    for color in colors:
        if backgr:
            color_img = ImageChops.logical_or(color[2], color_img)
            sqcode, ret_skip_mask, wall_countr = get_squares(color_img, color=color[0], skip_mask=skip_mask, joint=joint)
        else:
            sqcode, ret_skip_mask, wall_countr = get_squares(color[2], color=color[0], skip_mask=skip_mask, joint=joint)
        wall_count += wall_countr
        ret.extend(sqcode)
        ret.extend("s")
        skip_mask = np.logical_or(ret_skip_mask, skip_mask)
    return ret, wall_count


def to_walls(img: Image.Image):
    result = []
    img_width, img_height = img.size
    img_loaded = img.load()
    wall_count = 0
    for y in range(img_height):
        for x in range(img_width):
            pixel = img_loaded[x, y]
            if pixel == 100:
                continue
            wall_count += 1
            result.append(f"wall {x} {y}")
    
    return result, wall_count


def read_schematic(img: Image.Image):
    print(img.palette)
    result = []
    img_width, img_height = img.size
    img_loaded = img.load()
    colors = [Image.new("1", img.size, color=0) for i in range(WALLS_TYPE_COUNT)]
    print(colors)
    wall_count = 0
    for index, pixel in enumerate(img.getdata()):
        if pixel == WTC_TRNSP_PX_ID:
            continue
        x = index % img_width
        y = index // img_width
        print(pixel)
        colors[pixel].putpixel((x, y), 255)
    print(img_width, img_height)
    for i, wtype in enumerate(colors):
        print(wtype)
        img = wtype.load()
        for y in range(img_height):
            for x in range(img_width):
                pixel = img[x, y]
                if pixel == 0:
                    continue
                if wall_count == 0:
                    result.append(f"type_wall {x} {y} {i}")
                else:
                    result.append(f"type_wall {x} {y}")
                wall_count += 1
    
    return result