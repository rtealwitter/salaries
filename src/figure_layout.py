"""Audit all visible figure text at export resolution before saving."""

from itertools import combinations

from matplotlib.text import Text


def audit_text(fig, stem):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    # Matplotlib creates tick artists outside the view interval but does not draw
    # them. Exclude those unused artists from the text audit.
    undrawn = set()
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            lo, hi = sorted(axis.get_view_interval())
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                if not lo <= tick.get_loc() <= hi:
                    undrawn.update((tick.label1, tick.label2))
    labels = []
    for artist in fig.findobj(match=Text):
        if artist not in undrawn and artist.get_visible() and artist.get_text().strip():
            box = artist.get_window_extent(renderer)
            if box.width and box.height:
                labels.append((artist.get_text(), box))
    overlaps = [
        (a, b) for (a, aa), (b, bb) in combinations(labels, 2) if aa.overlaps(bb)
    ]
    bounds = fig.bbox
    clipped = [
        label
        for label, box in labels
        if box.x0 < bounds.x0
        or box.y0 < bounds.y0
        or box.x1 > bounds.x1
        or box.y1 > bounds.y1
    ]
    result = dict(
        figure=stem,
        text_items=len(labels),
        overlapping_pairs=overlaps,
        clipped_text=clipped,
    )
    if overlaps or clipped:
        raise ValueError(f"Text layout failed: {result}")
    print(f"Text audit: {stem}: {len(labels)} items, 0 overlaps, 0 clipped")
    return result
