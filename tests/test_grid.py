"""Tests for the grid-to-pixel conversion (harness/screen/grid.py)."""

import pytest

from harness.screen.grid import grid_to_pixel, pixel_to_grid


def test_corners_land_on_the_first_and_last_pixel():
    assert grid_to_pixel(0, 0, 1920, 1080) == (0, 0)
    assert grid_to_pixel(1000, 1000, 1920, 1080) == (1919, 1079)


def test_middle():
    assert grid_to_pixel(500, 500, 1920, 1080) == (960, 540)


@pytest.mark.parametrize("width, height", [(1920, 1080), (2560, 1440), (3840, 2160), (1366, 768)])
def test_every_grid_position_is_on_the_screen(width, height):
    for g in range(0, 1001):
        x, y = grid_to_pixel(g, g, width, height)
        assert 0 <= x < width and 0 <= y < height


def test_round_trip_is_within_one_grid_unit():
    for g in range(0, 1001, 7):
        x, y = grid_to_pixel(g, g, 1920, 1080)
        back_x, back_y = pixel_to_grid(x, y, 1920, 1080)
        assert abs(back_x - g) <= 1 and abs(back_y - g) <= 1


def test_other_grid_size():
    assert grid_to_pixel(100, 100, 1001, 1001, grid=100) == (1000, 1000)


@pytest.mark.parametrize("gx, gy", [(-1, 0), (0, 1001), (1000.5, 0)])
def test_outside_the_grid_is_refused(gx, gy):
    with pytest.raises(ValueError):
        grid_to_pixel(gx, gy, 1920, 1080)
