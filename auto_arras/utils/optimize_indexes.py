"""Tool for optimizing clusters of walls into big walls."""

from rich.progress import track


# May god forgive me for this code.
def is_square(
    indexes: list,
    image_size: tuple[int, int],
    square_position: tuple[int, int],
    square_size: int
) -> tuple[tuple[int, int] | None, list[tuple[int, int]]]:
    """Check if there is square of given position and size in indexes.

    If there is, return index of end of square,
    return indexes of square.
    Else, return None and position of square.

    For example: [(0, 0), (0, 1), (1, 0), (1, 1)] is square
    of size 2. Function will return:
    ((1, 1), [(0, 0), (0, 1), (1, 0), (1, 1)])
    """

    square_size -= 1

    start_x = square_position[0]
    start_y = square_position[1]

    end_x = start_x + square_size
    end_y = start_y + square_size

    # This thing improves speed like 10 times...
    if end_x > image_size[0] or end_y > image_size[1]:
        return None, [square_position]

    indexes_of_square: list[tuple[int, int]] = []

    for current_x in range(start_x, end_x+1):
        for current_y in range(start_y, end_y+1):
            if (current_x, current_y) in indexes:
                indexes_of_square.append((current_x, current_y))
            else:
                return None, [square_position]
    return (end_x, end_y), indexes_of_square


def square_indexes(
    indexes,
    image_size,
    size=2
) -> tuple[list[str], list[tuple[int, int]]]:
    """Divides image into squares of same size."""

    result = []

    indexes = list(map(tuple, indexes))
    unsquared = indexes.copy()

    for index in indexes:
        if not index:
            continue

        border, indexes_to_remove = is_square(
            indexes, image_size, index, size
        )

        for i in indexes_to_remove:
            if border:
                unsquared.remove(i)
            indexes[indexes.index(i)] = None

        if border:
            result.append(f'x {index[1]} {index[0]} {border[1]} {border[0]}')

    return result, unsquared


def optimize_indexes(indexes, image_size) -> list[str]:
    """Combines indexes into squares."""

    max_wall_size = min(image_size[0], image_size[1], 32)
    result = []

    for wall_size in track(
        range(max_wall_size, 1, -1),
        description='Optimizing indexes...'
    ):

        wall_size_template, indexes = square_indexes(
            indexes, image_size, wall_size
        )
        result.extend(wall_size_template)

    result.extend([f'x {i[1]} {i[0]}' for i in indexes])

    return result
