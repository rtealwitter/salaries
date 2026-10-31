"""Audit all visible figure text at export resolution before saving."""

from itertools import combinations

import numpy as np
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


def resolve_label_overlaps(ax, texts, targets):
    """Finish automatic layout with deterministic pixel-space separation and audit."""
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    initial = {id(t): ax.transData.transform(t.get_position())[1] for t in texts}
    for iteration in range(600):
        overlaps = 0
        for j, a in enumerate(texts):
            for b in texts[j + 1 :]:
                aa = a.get_window_extent(renderer).expanded(1.035, 1.12)
                bb = b.get_window_extent(renderer).expanded(1.035, 1.12)
                if not aa.overlaps(bb):
                    continue
                overlaps += 1
                lower, upper = (a, b) if initial[id(a)] <= initial[id(b)] else (b, a)
                lb = lower.get_window_extent(renderer).expanded(1.035, 1.12)
                ub = upper.get_window_extent(renderer).expanded(1.035, 1.12)
                shift = (lb.y1 - ub.y0 + 1) / 2
                for t, delta in [(lower, -shift), (upper, shift)]:
                    pos = ax.transData.transform(t.get_position())
                    pos[1] += delta
                    pos[1] = np.clip(pos[1], ax.bbox.y0 + 12, ax.bbox.y1 - 12)
                    t.set_position(ax.transData.inverted().transform(pos))
        if not overlaps:
            break
    remaining = sum(
        a.get_window_extent(renderer).overlaps(b.get_window_extent(renderer))
        for j, a in enumerate(texts)
        for b in texts[j + 1 :]
    )
    if remaining:
        raise ValueError(
            f"{remaining} unresolved text overlaps in {ax.get_title(loc='left')}"
        )
    for t, target in zip(texts, targets):
        distance = np.linalg.norm(
            ax.transData.transform(t.get_position()) - ax.transData.transform(target)
        )
        if distance > 12:
            ax.annotate(
                "",
                xy=target,
                xytext=t.get_position(),
                arrowprops=dict(arrowstyle="-", color="#9ba8b1", lw=0.6),
                zorder=1,
            )
    print(
        f"Label audit: {ax.get_title(loc='left')}: {len(texts)} labels, {remaining} overlaps"
    )
