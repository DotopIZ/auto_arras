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

from PIL import Image

def quantize_rgba(
    image: Image.Image,
    palette: list[tuple[int, int, int, int]],
    dither: Image.Dither = Image.Dither.FLOYDSTEINBERG,
    alpha_multiplier: int | None = None,   # сохранён для обратной совместимости, не используется
) -> Image.Image:
    """
    Квантует RGBA-изображение к заданной палитре с дизерингом.

    Дизеринг применяется только к RGB-каналу (обходной путь из-за того,
    что Pillow не поддерживает дизеринг при квантовании RGBA).
    Индексы палитры, полученные для RGB-части, используются напрямую для
    итогового P-изображения с полной RGBA-палитрой.

    :param image: Исходное изображение (будет приведено к RGBA).
    :param palette: Список до 256 цветов в формате RGBA.
    :param dither: Метод дизеринга (Image.Dither.FLOYDSTEINBERG или Image.Dither.NONE).
    :param alpha_multiplier: Устаревший параметр, оставлен для совместимости.
    :return: Изображение в режиме 'P' с прикреплённой RGBA-палитрой.
    """
    if len(palette) > 256:
        raise ValueError("PIL 'P' mode поддерживает не более 256 цветов.")

    # 1. Приводим исходное изображение к RGBA и извлекаем RGB-часть
    img_rgb = image.convert("RGBA").convert("RGB")

    # 2. Палитра только из RGB-компонент — в том же порядке, что и исходная
    palette_rgb = [color[:3] for color in palette]
    palette_img = Image.new("P", (1, 1))
    flat_rgb_palette = [channel for color in palette_rgb for channel in color]
    palette_img.putpalette(flat_rgb_palette)

    # 3. Квантуем RGB с дизерингом — получаем P-изображение с индексами палитры
    quantized_p = img_rgb.quantize(palette=palette_img, dither=dither)

    # 4. Подменяем палитру на RGBA-версию.
    #    Индексы не меняются (порядок цветов сохранён), а альфа теперь
    #    берётся из палитры — как и в исходной реализации.
    flat_rgba_palette = [channel for color in palette for channel in color]
    quantized_p.putpalette(flat_rgba_palette, rawmode="RGBA")

    return quantized_p

def quantize_to_palette(silf, palette, dither=False):
    """Convert an RGB or L mode image to use a given P image's palette."""

    if dither:
        return quantize_rgba(silf, palette)
    else:
        return quantize_rgba(silf, palette, dither=Image.Dither.NONE)


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
