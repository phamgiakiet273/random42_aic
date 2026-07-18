"""Dominant-color extraction and step-sort ordering, shared by the live rerank
service and the offline color-generation pre-processing script (formerly two
independent copies: color_sort_gen.py and rerank_handler.py's _step())."""

from __future__ import annotations

import colorsys
import math

from imagedominantcolor import DominantColor


def get_dominant_color(image_path):
    """Return the dominant RGB color of the image at `image_path`."""
    dominantcolor = DominantColor(image_path)
    return dominantcolor.rgb


def get_luminance(r, g, b):
    """Perceptual luminance approximation for RGB step-sorting."""
    return math.sqrt(0.241 * r + 0.691 * g + 0.068 * b)


def step_sort_key(r, g, b, repetitions=1):
    """Step-sort key (hue/luminance/value bucketed and serpentined) for color ordering."""
    lum = get_luminance(r, g, b)
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    h2 = int(h * repetitions)
    lum2 = int(lum * repetitions)
    v2 = int(v * repetitions)

    if h2 % 2 == 1:
        v2 = repetitions - v2
        lum2 = repetitions - lum2

    return (h2, lum2, v2)
