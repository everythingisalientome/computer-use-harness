"""Convert between the model's coordinate grid and screenshot pixels.

The model answers on a grid laid over the screenshot it was sent: (0, 0) is the
top-left pixel and (grid, grid) is the bottom-right pixel. The grid size is
`coordinate_grid` in config/model-connection.yaml (1000).

This is the only place the conversion happens. The harness and the pointing
probe both use it. It makes no Windows calls, so it is safe to import anywhere.

Because the harness is DPI aware (see win32.py), screenshot pixels and screen
pixels are the same thing, so display scaling never enters this arithmetic.
"""


def grid_to_pixel(gx, gy, width, height, grid=1000):
    """Return the (x, y) pixel for grid position (gx, gy) on an image of width x height pixels.

    Grid 0 is the first pixel and grid `grid` is the last pixel (width - 1),
    so every grid position lands on a real pixel.
    """
    for value in (gx, gy):
        if not 0 <= value <= grid:
            raise ValueError(f"Grid position {value} is outside 0 to {grid}.")
    x = round(gx * (width - 1) / grid)
    y = round(gy * (height - 1) / grid)
    return x, y


def pixel_to_grid(x, y, width, height, grid=1000):
    """The reverse of grid_to_pixel, rounded to whole grid units. Used by checks and tests."""
    gx = round(x * grid / (width - 1))
    gy = round(y * grid / (height - 1))
    return gx, gy
