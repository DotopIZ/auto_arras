"""Tools for working with images."""

import numpy as np
from PIL import Image
from PIL import ImageFile
from ..config import WALL_COLORS, wall_colors_to_index, WALL_TYPE_COLORS



# Пришлось попросить у иишки код попросить сгенерить потому что pil кусок говна сука почему
# я не могу rgba изображение блять к палитре квантизировать твоей встроенной функцией( ыыы
# так типа исторически сложилось- ДА МНЕ ПОХУЙ СУКА) ну вот сука почему им не сделать фцнкцию
# для этого, зачем мне костыли городить...
import numpy as np
from PIL import Image

def quantize_rgba(
    image: Image.Image,
    palette: list[tuple[int, int, int, int]],
    chunk_size: int = 500000, 
    alpha_multiplier: int = 2 
) -> Image.Image:
    """Highly optimized quantization using NumPy matrix multiplication.
    
    :param image: Input PIL Image.
    :param palette: List of up to 256 RGBA tuples.
    :param chunk_size: Increased to 500k as memory footprint is now much lower.
    :param alpha_multiplier: Scales alpha. 2 equates to an alpha weight of 4.
    :return: Quantized PIL Image in 'P' mode with RGBA palette attached.
    """
    if len(palette) > 256:
        raise ValueError("PIL 'P' mode supports a maximum of 256 colors.")

    # 1. Convert to int32 to prevent math overflow and enable fast processing
    img_np = np.array(image.convert("RGBA"), dtype=np.int32)
    palette_np = np.array(palette, dtype=np.int32)

    # 2. Pre-scale alpha channel to naturally weight it in Euclidean space
    if alpha_multiplier != 1:
        img_np[:, :, 3] *= alpha_multiplier
        palette_np[:, 3] *= alpha_multiplier

    height, width, _ = img_np.shape
    pixels = img_np.reshape(-1, 4)

    # 3. Precompute the Palette squared sum (the Y^2 in our formula)
    # Shape becomes (P,) where P is the number of colors in the palette
    palette_sq = np.sum(palette_np ** 2, axis=1)

    closest_indices = np.empty(len(pixels), dtype=np.uint8)

    # 4. Process in chunks using fast Matrix Multiplication (np.dot)
    for i in range(0, len(pixels), chunk_size):
        chunk = pixels[i : i + chunk_size]
        
        # X dot Y (Matrix multiplication is heavily optimized in NumPy)
        # Shape: (chunk_size, 4) @ (4, P) -> (chunk_size, P)
        xy_dot = np.dot(chunk, palette_np.T)
        
        # Calculate distance proxy: Y^2 - 2XY
        # We drop X^2 because it doesn't change which palette color is closest
        dist_proxy = palette_sq - (2 * xy_dot)
        
        # Find the index of the minimum distance
        closest_indices[i : i + chunk_size] = np.argmin(dist_proxy, axis=1)

    # 5. Build 'P' mode image
    out_img = Image.fromarray(closest_indices.reshape(height, width), mode="P")

    # Flatten original palette (not the scaled one) and attach
    flat_palette = [channel for color in palette for channel in color]
    out_img.putpalette(flat_palette, rawmode="RGBA")

    return out_img

def quantize_to_palette(silf, palette, dither=False):
    """Convert an RGB or L mode image to use a given P image's palette."""

    return quantize_rgba(silf, palette)


def black_and_white(img: Image.Image, palette, threshold, invert: bool = False):
    img = img.convert("L")
    #img.paste()
    if invert:
        img = img.point(lambda i: 255 if i < threshold else 20)
    else:
        img = img.point(lambda i: 255 if i > threshold else 20)
    img = img.convert("P", palette=palette)
    return img


def resize_image(
    img: Image.Image,
    resize_to: tuple[int, int],
    keep_aspect_ratio: bool = False,
    resample: bool = False,
) -> Image.Image:
    """Resize image to given size."""
    
    resampler = Image.Resampling.BOX
    if resample:
        resampler = Image.Resampling.LANCZOS

    if not keep_aspect_ratio:
        img = img.resize(resize_to, resampler)
        return img

    img.thumbnail(resize_to, resampler)

    return img
