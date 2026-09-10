"""Pure geometry helpers for print-safe, low-overlap chart placement."""
from __future__ import annotations


def intersection_area(a, b):
    """Intersection area for ``(x, y, width, height)`` tuples."""
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[0] + a[2], b[0] + b[2])
    bottom = min(a[1] + a[3], b[1] + b[3])
    return max(0.0, right - left) * max(0.0, bottom - top)


def best_position(page_width, page_height, width, height, occupied=(), margin=10.0):
    """Choose the lowest-overlap candidate, preferring lower-right on ties."""
    max_x = page_width - margin - width
    max_y = page_height - margin - height
    if max_x < margin or max_y < margin:
        raise ValueError("Chart does not fit inside the page margins.")
    candidates = [
        (max_x, max_y), (margin, max_y), (max_x, margin), (margin, margin),
        ((page_width - width) / 2.0, max_y),
        ((page_width - width) / 2.0, margin),
        (max_x, (page_height - height) / 2.0),
        (margin, (page_height - height) / 2.0),
    ]
    best, best_score = candidates[0], float("inf")
    for candidate in candidates:
        rect = (candidate[0], candidate[1], width, height)
        score = sum(intersection_area(rect, other) * weight
                    for other, weight in occupied)
        if score < best_score:
            best, best_score = candidate, score
    return best
