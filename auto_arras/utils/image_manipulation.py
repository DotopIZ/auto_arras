"""Tools for working with images."""

import cv2
import numpy


# pylint: disable=no-member


def resize_image(
    img: numpy.ndarray,
    resize_to: tuple[int, int],
    keep_aspect_ratio: bool = False
):
    """Resize image to given size."""

    if not keep_aspect_ratio:
        img = cv2.resize(img, resize_to)
        return img

    img_size = img.shape
    img_aspect_ratio = img_size[0] / img_size[1]

    resize_height = int(resize_to / img_aspect_ratio)
    img = cv2.resize(img, (resize_to[0], resize_height))

    return img


def get_indexes_of_pixels(pixels):
    """Returns indexes of pixels."""

    return numpy.transpose(numpy.nonzero(pixels)).tolist()
