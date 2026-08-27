#!/usr/bin/env python
"""Figures for the three comparison sweeps.

    python -m evaluations.plot_compare                 # everything on disk
    python -m evaluations.plot_compare --theme dark

Per sweep:
  <sweep>_coverage.png   configuration x scenario, shaded by success rate
  <sweep>_runtime.png    small multiples, one panel per scenario
  <sweep>_table.md       every number, mean +/- population std
and for the FD sweep additionally
  planners_tradeoff.png  plan cost against run time, one panel per scenario
and for the baseline
  baseline_vs_planner.png
and for the separation scan
  separation_cost.png    plan cost and the planner's cost advantage vs table separation

Form rationale, continuing plot.py's:
  * The coverage matrix uses ONE shared 0..1 scale, unlike plot.py's heatmap
    which normalises each row -- every cell here is a success rate, so they are
    directly comparable and rescaling per row would be a lie.
  * Run time is small multiples with the *configuration* on the x axis and one
    panel per scenario, not grouped bars. Run times differ by two orders of
    magnitude between pick_place and at_work, so a shared y axis would flatten
    six of the seven panels into nothing.
  * A configuration that failed is drawn as an explicit marker at the baseline
    with the reason, never as a missing or zero-height bar -- absence of a bar
    would read as "zero seconds", which is the opposite of what happened.
  * Colour: only the two categorical slots already validated in plot.py. The
    second slot marks the *current default* configuration, so the reader can
    find the reference point without having to decode a ten-hue legend.
"""

from __future__ import print_function

import argparse
import json
import os
import textwrap

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from evaluations.plot import (BAR_WIDTH, DARK, DPI, FONT, THEMES, _fmt, _nonnull,
                              _save, _ticks, _tick_formatter, _value_pattern,
                              rounded_bar, style_axes)
from evaluations.run import RESULTS_DIR
from evaluations.sweep import DIAGNOSED_FAILURES

SWEEP_DIR = os.path.join(RESULTS_DIR, 'sweeps')

# Which configuration is the incumbent, per sweep -- highlighted in slot 2.
REFERENCE = {
    'algorithms': 'adaptive',
    'planners': 'ff-astar2',
    'baseline': 'planner',
}

SWEEP_TITLES = {
    'algorithms': 'PDDLStream algorithm',
    'planners': 'Fast Downward search configuration',
    'baseline': 'scripted state machine vs. planner',
}

# How to name the reference column in the legend. For the two configuration
# sweeps it really is the incumbent default; in the baseline sweep the planner is
# the thing being compared against, not a "default" among alternatives.
REFERENCE_LABEL = {
    'algorithms': 'current default ({})',
    'planners': 'current default ({})',
    'baseline': 'the {}, as measured in results.json',
}

# The same distinction, phrased for the coverage caption rather than a legend.
REFERENCE_NOTE = {
    'algorithms': 'Current default: {}.',
    'planners': 'Current default: {}.',
    'baseline': 'The {} column is the same run reported in results.json.',
}

# (key, label, unit, format)
COMPARE_METRICS = [
    ('run_time', 'Total run time', 's', '{:.3f}'),
    ('cost', 'Plan cost', '', '{:.2f}'),
    ('length', 'Plan length', 'actions', '{:.1f}'),
    ('evaluations', 'Evaluations', '', '{:.0f}'),
    ('success_rate', 'Success rate', '', '{:.2f}'),
]


def _cells(result):
    return result.get('cells', [])


def _keys(result):
    keys = []
    for cell in _cells(result):
        if cell['key'] not in keys:
            keys.append(cell['key'])
    return keys


def _rows(result):
    """(phase, scenario) in registry order, i.e. increasing complexity."""
    rows = []
    for cell in _cells(result):
        row = (cell['phase'], cell['scenario'])
        if row not in rows:
            rows.append(row)
    return rows


def _index(result):
    return {(c['phase'], c['scenario'], c['key']): c for c in _cells(result)}


def _row_label(row):
    return '{}\n{}'.format(row[0].replace('2d', ''), row[1])


def _wrap(text, fig_width, fontsize, left_margin=0.03, right_margin=0.22,
          char_width=0.0073):
    """Wrap a caption to the figure width instead of letting it run off the edge.

    matplotlib's fig.text does not wrap, and these captions are long enough that
    on a narrow figure they silently overflow -- the reader loses the end of the
    sentence with no indication anything is missing.  Width is estimated from the
    point size, which is coarse but only ever errs toward wrapping early.

    char_width is inches per character per point, measured off a rendered line in
    this font rather than guessed -- an under-estimate silently clips the text.
    Bold runs wider than regular, so headings pass a larger value.
    """
    usable = max(2.0, fig_width - left_margin - right_margin)
    columns = max(28, int(usable / (char_width * fontsize)))
    return textwrap.fill(text, columns)


def _cost_is_degenerate(result, rows, keys, index):
    """Rows whose cost is identically zero -- i.e. a domain with no action costs.

    discrete2d/domain.pddl has no `increase (total-cost)` effects, so every plan
    there costs 0.  Plotting that is worse than not plotting it: a flat row of
    zeroes on an invented axis reads as a measurement.
    """
    degenerate = []
    for row in rows:
        values = []
        for key in keys:
            average = (index.get((row[0], row[1], key)) or {}).get('average') or {}
            if average.get('solved_trials'):
                values.append(average.get('cost') or 0.)
        if values and max(values) == 0:
            degenerate.append(row)
    return degenerate


def _short_run_note(cell, target):
    """'n=1, killed' for a cell that solved but ran fewer trials than asked for.

    Without this, a cell that returned one plan and was then killed mid-sampling
    renders as a bare 1.00 beside a cell that solved 20/20 -- identical ink for
    "always works" and "worked once before we gave up on it".
    """
    if cell is None or not target:
        return None
    count = len(cell.get('trials', []))
    if not count or count >= target:
        return None
    status = cell.get('status')
    suffix = '' if status in ('ok', 'cached', None) else ', ' + str(status)
    return 'n={}{}'.format(count, suffix)


def _status_note(cell):
    """Short human-readable reason a cell produced no plan."""
    if cell is None:
        return 'not run'
    if cell.get('hang_site'):
        return 'hang: ' + cell['hang_site']
    average = cell.get('average') or {}
    if not average:
        return 'no data'
    if average.get('solved_trials'):
        return None
    errors = [t.get('error') for t in cell.get('trials', []) if t.get('error')]
    if errors:
        first = errors[0]
        return first.split(':')[0][:22]
    if average.get('timeout_rate'):
        return 'timeout'
    return 'no plan'


# --------------------------------------------------------------------------
# Figure 1 -- coverage matrix
# --------------------------------------------------------------------------

def plot_coverage(result, theme, out_path):
    keys, rows, index = _keys(result), _rows(result), _index(result)
    cmap = LinearSegmentedColormap.from_list('seq_blue', theme['ramp'])

    panel_w = max(6.0, 1.15 * len(keys) + 2.8)
    panel_h = 0.72 * len(rows) + 2.2
    fig, ax = plt.subplots(figsize=(panel_w, panel_h), dpi=DPI)
    fig.patch.set_facecolor(theme['surface'])
    ax.set_facecolor(theme['surface'])

    for r, row in enumerate(rows):
        for c, key in enumerate(keys):
            cell = index.get((row[0], row[1], key))
            average = (cell or {}).get('average') or {}
            rate = average.get('success_rate')
            note = _status_note(cell)

            if rate is None:
                # Nothing measured: leave the surface bare and say so.
                ax.text(c + 0.5, r + 0.5, note or 'n/a', ha='center', va='center',
                        color=theme['ink_muted'], fontsize=7.5)
                continue
            ax.add_patch(plt.Rectangle((c + 0.03, r + 0.03), 0.94, 0.94,
                                       facecolor=cmap(rate), edgecolor='none'))
            # on_ramp_light is the ink for the ramp's LOW end, on_ramp_dark for
            # its HIGH end -- DARK's ramp runs dark-to-light, so which swatch is
            # physically lighter differs by theme.
            ink = theme['on_ramp_light'] if rate < 0.55 else theme['on_ramp_dark']
            short = _short_run_note(cell, result.get('config', {}).get('trials'))
            if rate == 0 and note:
                ax.text(c + 0.5, r + 0.38, '0.00', ha='center', va='center',
                        color=ink, fontsize=8.5)
                ax.text(c + 0.5, r + 0.68, note, ha='center', va='center',
                        color=ink, fontsize=6.5)
            elif short:
                ax.text(c + 0.5, r + 0.38, '{:.2f}'.format(rate), ha='center',
                        va='center', color=ink, fontsize=8.5)
                ax.text(c + 0.5, r + 0.68, short, ha='center', va='center',
                        color=ink, fontsize=6.5)
            else:
                ax.text(c + 0.5, r + 0.5, '{:.2f}'.format(rate), ha='center',
                        va='center', color=ink, fontsize=8.5)

    ax.set_xlim(0, len(keys))
    ax.set_ylim(len(rows), 0)
    ax.set_xticks([i + 0.5 for i in range(len(keys))])
    ax.set_xticklabels(keys, fontsize=8.5, rotation=30, ha='left')
    ax.set_yticks([i + 0.5 for i in range(len(rows))])
    ax.set_yticklabels([_row_label(row) for row in rows], fontsize=8.5)
    ax.tick_params(axis='both', length=0, colors=theme['ink_secondary'])
    ax.xaxis.set_ticks_position('top')
    for side in ('top', 'right', 'left', 'bottom'):
        ax.spines[side].set_visible(False)

    reference = REFERENCE.get(result['sweep'])
    trials = result.get('config', {}).get('trials')
    # DARK's ramp runs dark-to-light, so the direction word has to follow it.
    direction = 'Brighter' if theme is DARK else 'Darker'
    # The heading goes on the figure, not the axes: with only two columns the
    # figure is narrow, the axes starts well to the right of it (the row labels
    # are wide), and an axes title long enough to name the sweep ran straight off
    # the right edge with nothing to show it had been cut.
    heading = _wrap('Fraction of trials that produced a plan -- by {}'.format(
        SWEEP_TITLES.get(result['sweep'], result['sweep'])),
        panel_w, 11.5, right_margin=0.06, char_width=0.0083)
    head_lines = heading.count('\n') + 1
    fig.text(0.012, 1 - 0.10 / panel_h, heading, color=theme['ink'],
             fontsize=11.5, fontweight='bold', ha='left', va='top')
    caption = _wrap(
        '{} = more reliable, on one shared 0-1 scale. Up to {} trials per cell; '
        'a cell labelled n=k ran fewer, either because the probe found it unsolvable '
        'or because it was killed mid-cell, so its rate rests on k trials. '
        '{}'.format(direction, trials,
                    REFERENCE_NOTE.get(result['sweep'], 'Current default: {}.')
                    .format(reference) if reference else ''),
        panel_w, 8.5, right_margin=0.06)
    lines = caption.count('\n') + 1
    fig.text(0.012, 0.016, caption,
             color=theme['ink_secondary'], fontsize=8.5, ha='left', va='bottom')
    # Reserve the heading's own space at the top: without the axes title there,
    # tight_layout only knows about the rotated column labels.
    fig.tight_layout(rect=(0, 0.035 + 0.020 * lines, 1,
                           1 - (0.10 + 0.24 * head_lines) / panel_h))
    _save(fig, out_path, theme)


# --------------------------------------------------------------------------
# Figure 2 -- run time, one panel per scenario
# --------------------------------------------------------------------------

def plot_metric_by_scenario(result, theme, out_path, metric='run_time',
                            title='Total run time', unit='s', pattern='{:.3f}'):
    keys, rows, index = _keys(result), _rows(result), _index(result)
    reference = REFERENCE.get(result['sweep'])

    # A cost panel for a domain without action costs is a row of zeroes on an
    # invented axis. Drop those rows and say which, rather than draw them.
    dropped = []
    if metric == 'cost':
        dropped = _cost_is_degenerate(result, rows, keys, index)
        rows = [row for row in rows if row not in dropped]
    if not rows:
        print('Skipping {} -- no scenario has a non-degenerate {}'.format(out_path, metric))
        return

    ncols = 4 if len(rows) > 3 else len(rows)
    nrows = int((len(rows) + ncols - 1) // ncols)
    panel_w = max(2.9, 0.42 * len(keys) + 1.5)
    panel_h = 2.75
    header = 1.25
    fig, axes = plt.subplots(nrows, ncols, squeeze=False,
                             figsize=(ncols * panel_w, nrows * panel_h + header), dpi=DPI)
    fig.patch.set_facecolor(theme['surface'])
    fig_h = nrows * panel_h + header

    for position, row in enumerate(rows):
        ax = axes[position // ncols][position % ncols]
        means, stds, notes = [], [], []
        for key in keys:
            cell = index.get((row[0], row[1], key))
            average = (cell or {}).get('average') or {}
            solved = average.get('solved_trials') or 0
            # A configuration that never solved has no meaningful run time --
            # its `run_time` is just however long it spent failing.
            means.append(average.get(metric) if solved else None)
            stds.append(average.get(metric + '_std') if solved else None)
            notes.append(None if solved else _status_note(cell))

        ax.set_title('{}  {}'.format(row[0].replace('2d', ''), row[1]),
                     color=theme['ink'], fontsize=9.5, loc='left', pad=8)
        ax.set_xticks(range(len(keys)))
        ax.set_xticklabels(keys, rotation=45, ha='right', fontsize=7)
        ax.set_xlim(-0.6, len(keys) - 0.4)

        present = _nonnull(means)
        if not present:
            ax.text(0.5, 0.5, 'no configuration produced a plan', transform=ax.transAxes,
                    ha='center', va='center', color=theme['ink_muted'], fontsize=8)
            style_axes(ax, theme, ygrid=False)
            ax.set_yticks([])
            continue

        top = max(m + (s or 0.) for m, s in zip(means, stds) if m is not None)
        ax.set_ylim(0, (top or 1.) * 1.32)
        ax.set_yticks(_ticks(0, ax.get_ylim()[1]))
        ax.yaxis.set_major_formatter(_tick_formatter(top))
        cell_pattern = _value_pattern(present, pattern)

        for i, (mean, std) in enumerate(zip(means, stds)):
            if mean is None:
                # Explicit failure marker at the baseline, plus the reason.
                ax.plot([i], [0], marker='x', markersize=5,
                        color=theme['ink_muted'], zorder=5, clip_on=False)
                if notes[i]:
                    ax.annotate(notes[i], (i, 0), textcoords='offset points',
                                xytext=(0, 7), ha='center', rotation=90,
                                color=theme['ink_muted'], fontsize=6.5, va='bottom')
                continue
            colour = theme['series'][1] if key_is_reference(keys[i], reference) \
                else theme['series'][0]
            rounded_bar(ax, i, mean, BAR_WIDTH, colour, (panel_w, panel_h))
            if std:
                ax.errorbar(i, mean, yerr=std, ecolor=theme['ink_muted'],
                            elinewidth=1.0, capsize=2.5, capthick=1.0, fmt='none',
                            zorder=4)

        best = min((i for i in range(len(means)) if means[i] is not None),
                   key=lambda i: means[i])
        marks = {best}
        if reference in keys:
            marks.add(keys.index(reference))
        if len(present) <= 3:
            # Count the columns that actually produced a plan, not the columns in
            # the sweep: a panel where only two configurations solved anything is
            # a two-bar panel, and the reader wants both numbers. "Best plus
            # reference" also collapses to a single label whenever the best *is*
            # the reference, which would label some panels twice and others once.
            marks = set(range(len(keys)))
        for i in sorted(marks):
            if means[i] is None:
                continue
            ax.annotate(_fmt(means[i], cell_pattern), (i, means[i] + (stds[i] or 0.)),
                        textcoords='offset points', xytext=(0, 6), ha='center',
                        color=theme['ink_secondary'], fontsize=8)

        style_axes(ax, theme)

    for spare in range(len(rows), nrows * ncols):
        axes[spare // ncols][spare % ncols].axis('off')

    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=theme['series'][0], edgecolor='none'),
               plt.Rectangle((0, 0), 1, 1, facecolor=theme['series'][1], edgecolor='none')]
    legend = fig.legend(handles, ['configuration under test',
                                  REFERENCE_LABEL.get(result['sweep'],
                                                      'current default ({})').format(reference)],
                        loc='upper right', bbox_to_anchor=(0.995, 1 - 0.30 / fig_h),
                        frameon=False, fontsize=8.5, ncol=1, handlelength=1.1,
                        handleheight=1.1, borderpad=0.)
    for text in legend.get_texts():
        text.set_color(theme['ink_secondary'])

    fig.tight_layout(rect=(0, 0, 1, 1 - header / fig_h))
    heading = '{}{} by {}'.format(title, ' ({})'.format(unit) if unit else '',
                                  SWEEP_TITLES.get(result['sweep'], result['sweep']))
    fig.text(0.011, 1 - 0.34 / fig_h, heading, color=theme['ink'], fontsize=13,
             fontweight='bold', ha='left', va='center')
    # The scale note has to follow the metric: "run times span two orders of
    # magnitude" is the reason for per-panel y axes on the time figure, and is
    # simply untrue on the cost figure.
    scale_note = ('run times span two orders of magnitude'
                  if metric == 'run_time' else
                  'the scenarios differ too much in size to share one')
    subtitle = ('One panel per scenario, each with its own y scale -- {}. Error bars are '
                'the population standard deviation; x marks a configuration that produced '
                'no plan.'.format(scale_note))
    if dropped:
        subtitle += ' {} omitted: no action costs in that domain, so cost is 0 by ' \
                    'construction.'.format(', '.join(_row_label(row).replace('\n', '/')
                                                     for row in dropped))
    fig.text(0.011, 1 - 0.70 / fig_h,
             _wrap(subtitle, ncols * panel_w, 9),
             color=theme['ink_secondary'], fontsize=9, ha='left', va='top')
    _save(fig, out_path, theme)


def key_is_reference(key, reference):
    return reference is not None and key == reference


# --------------------------------------------------------------------------
# Figure 3 -- cost against time (FD configs)
# --------------------------------------------------------------------------

def plot_tradeoff(result, theme, out_path):
    keys, rows, index = _keys(result), _rows(result), _index(result)
    reference = REFERENCE.get(result['sweep'])

    # Same reasoning as the cost figure: a facet for a domain with no action
    # costs has no trade-off in it, and three such facets crowded out the four
    # that do. Drop them and name them in the subtitle.
    dropped = _cost_is_degenerate(result, rows, keys, index)
    rows = [row for row in rows if row not in dropped]
    if not rows:
        print('Skipping {} -- no scenario has action costs'.format(out_path))
        return

    ncols = 4 if len(rows) > 3 else len(rows)
    nrows = int((len(rows) + ncols - 1) // ncols)
    panel_w, panel_h, header = 3.1, 2.9, 1.3
    fig, axes = plt.subplots(nrows, ncols, squeeze=False,
                             figsize=(ncols * panel_w, nrows * panel_h + header), dpi=DPI)
    fig.patch.set_facecolor(theme['surface'])
    fig_h = nrows * panel_h + header

    for position, row in enumerate(rows):
        ax = axes[position // ncols][position % ncols]
        points = []
        for key in keys:
            cell = index.get((row[0], row[1], key))
            average = (cell or {}).get('average') or {}
            if not average.get('solved_trials'):
                continue
            time_value, cost_value = average.get('run_time'), average.get('cost')
            if time_value is None or cost_value is None:
                continue
            points.append((key, time_value, cost_value))

        ax.set_title('{}  {}'.format(row[0].replace('2d', ''), row[1]),
                     color=theme['ink'], fontsize=9.5, loc='left', pad=8)

        if len(points) < 1:
            ax.text(0.5, 0.5, 'no solved configuration', transform=ax.transAxes,
                    ha='center', va='center', color=theme['ink_muted'], fontsize=8)
            style_axes(ax, theme, ygrid=False)
            ax.set_xticks([])
            ax.set_yticks([])
            continue

        costs = [p[2] for p in points]
        times = [p[1] for p in points]
        span_x = (max(times) - min(times)) or max(times) or 1.
        span_y = (max(costs) - min(costs)) or max(costs) or 1.
        # Limits before labels: label placement needs to know where the panel
        # edges are, so a point near the right edge can be labelled leftward
        # instead of off the figure.
        x_lo, x_hi = max(0., min(times) - 0.16 * span_x), max(times) + 0.30 * span_x
        y_lo, y_hi = min(costs) - 0.22 * span_y, max(costs) + 0.25 * span_y
        ax.set_xlim(x_lo, x_hi)
        ax.set_ylim(y_lo, y_hi)

        # Pareto frontier: nothing else is both faster and cheaper.
        frontier = {key for key, t, c in points
                    if not any(t2 <= t and c2 <= c and (t2, c2) != (t, c)
                               for _, t2, c2 in points)}

        # Label the cost outliers too -- an unlabelled outlier is the one point a
        # reader most wants named, and "the frontier plus the default" leaves
        # exactly those anonymous.  A quarter of the panel's cost span above the
        # median is the threshold: below that the spread is noise and naming a
        # "worst" would overstate it.  All of them, not just the maximum: on
        # multi_object two configurations sit together well above the cluster, and
        # naming one of the pair invites the reader to think the other is fine.
        median_cost = sorted(costs)[len(costs) // 2]
        frontier.update(key for key, _, c in points
                        if c - median_cost > 0.25 * span_y)

        # These panels are small and several configurations land within a few
        # milliseconds of each other, so fixed label offsets overlapped and were
        # unreadable. Place each label in the first candidate slot that is clear
        # of the ones already placed, clear of every *other* configuration's dot,
        # and inside the panel.
        placed = []
        candidates = [(7, 3, 'left'), (7, -13, 'left'), (7, 17, 'left'),
                      (-7, 3, 'right'), (-7, -13, 'right'), (-7, 17, 'right'),
                      (7, -25, 'left'), (7, 29, 'left'),
                      (-7, -25, 'right'), (-7, 29, 'right')]
        # Offsets are in points; converting them to axes fractions needs the
        # axes height, not a constant, or the collision test compares a fraction
        # against offsets that are effectively zero and never separates anything.
        frac_per_pt = 1. / max(40., panel_h * 72. * 0.62)
        # Markers, in axes fractions. Labels have to dodge these too: checking
        # only against other labels let a label land on top of a dot, which in
        # the multi_object panel hid the reference marker behind "ff-eager".
        markers = [(key, (t - x_lo) / (x_hi - x_lo), (c - y_lo) / (y_hi - y_lo))
                   for key, t, c in points]
        for key, time_value, cost_value in sorted(points, key=lambda p: -p[2]):
            is_ref = key_is_reference(key, reference)
            ax.scatter([time_value], [cost_value], s=44 if is_ref else 26,
                       facecolor=theme['series'][1] if is_ref else theme['series'][0],
                       edgecolor='none', zorder=4)
            if not (is_ref or key in frontier):
                continue
            fx = (time_value - x_lo) / (x_hi - x_lo)
            fy = (cost_value - y_lo) / (y_hi - y_lo)
            # A label needs roughly this much of the panel to the side it points.
            width = 0.055 + 0.030 * len(key)

            def _cost_of(candidate):
                """How bad this slot is: off-panel, on a label, or on a dot."""
                dx, dy, side = candidate
                anchor = (fx + (0.045 if side == 'left' else -0.045),
                          fy + dy * frac_per_pt)
                span = ((anchor[0], anchor[0] + width) if side == 'left'
                        else (anchor[0] - width, anchor[0]))
                off = 0 if (span[0] > -0.01 and span[1] < 1.01
                            and -0.01 < anchor[1] < 1.01) else 1
                hits = sum(1 for px, py in placed
                           if abs(anchor[0] - px) <= width * 0.55
                           and abs(anchor[1] - py) <= 0.055)
                dots = sum(1 for other, mx, my in markers
                           if other != key
                           and span[0] - 0.02 <= mx <= span[1] + 0.02
                           and abs(anchor[1] - my) < 0.040)
                return off * 4 + hits * 2 + dots, anchor

            # Score every slot and take the least-bad one. Taking the first clear
            # slot and falling back to candidates[0] put the fallback label right
            # back on top of whatever it was dodging.
            scored = []
            for i, candidate in enumerate(candidates):
                score, anchor = _cost_of(candidate)
                scored.append((score, i, candidate, anchor))
            _, _, choice, anchor = min(scored)
            placed.append(anchor)
            # A label pushed well clear of its dot stops being attached to it --
            # in the multi_object cluster three dots sit within a few pixels, so a
            # displaced label could belong to any of them. Past the first ring of
            # offsets, draw a hairline leader back to the point it names.
            leader = None
            if abs(choice[1]) > 18:
                leader = dict(arrowstyle='-', color=theme['ink_muted'],
                              linewidth=0.6, shrinkA=1, shrinkB=3)
            ax.annotate(key, (time_value, cost_value), textcoords='offset points',
                        xytext=(choice[0], choice[1]), ha=choice[2], fontsize=7,
                        color=theme['ink_secondary'], zorder=6, arrowprops=leader)

        ax.set_xlabel('run time (s)', color=theme['ink_muted'], fontsize=8)
        ax.set_ylabel('plan cost', color=theme['ink_muted'], fontsize=8)
        ax.yaxis.set_major_formatter(_tick_formatter(max(costs)))
        ax.xaxis.set_major_formatter(_tick_formatter(max(times)))
        style_axes(ax, theme)
        ax.xaxis.grid(True, color=theme['grid'], linewidth=0.8, linestyle='-')

    for spare in range(len(rows), nrows * ncols):
        axes[spare // ncols][spare % ncols].axis('off')

    fig.tight_layout(rect=(0, 0, 1, 1 - header / fig_h))
    fig.text(0.011, 1 - 0.34 / fig_h,
             'Plan quality against planning time, by Fast Downward search configuration',
             color=theme['ink'], fontsize=13, fontweight='bold', ha='left', va='center')
    subtitle = ('Down and to the left is better. Labelled points are the Pareto frontier, '
                'the current default, and any configuration whose cost stands clear of the '
                'rest. Note that the A* configurations run at cost_type=PLUSONE, '
                'so they minimise cost-plus-one-per-action, not the cost plotted here -- none of '
                'them is a ground-truth optimum.')
    if dropped:
        subtitle += ' {} omitted: no action costs in that domain.'.format(
            ', '.join(_row_label(row).replace('\n', '/') for row in dropped))
    fig.text(0.011, 1 - 0.72 / fig_h, _wrap(subtitle, ncols * panel_w, 8.5),
             color=theme['ink_secondary'], fontsize=8.5, ha='left', va='top')
    _save(fig, out_path, theme)


# --------------------------------------------------------------------------
# Figure 4 -- how the planner/state-machine gap scales with table separation
# --------------------------------------------------------------------------

# Slot assignment follows the baseline sweep exactly -- script in slot 0,
# planner in slot 1 -- because these two figures sit next to each other in the
# write-up and they compare the same two things.  Swapping the hues between them
# would be worse than any argument for a different order here: REFERENCE marks the
# planner as the reference column in the baseline sweep, and the reference always
# takes slot 1.
SEPARATION_SERIES = [
    ('script', 'scripted state machine', 0),
    ('planner', 'PDDLStream planner', 1),
]
SEPARATION_MARKER = {0: 's', 1: 'o'}


def _separation_xy(points, side, key):
    """(separation, value, std) triples, skipping separations with no solution."""
    xs, ys, errors = [], [], []
    for point in points:
        value = (point.get(side) or {}).get(key)
        if value is None:
            continue
        xs.append(point['separation'])
        ys.append(value)
        errors.append((point[side].get(key + '_std') or 0.))
    return xs, ys, errors


def _separation_line(ax, theme, xs, ys, errors, colour, marker):
    ax.errorbar(xs, ys, yerr=errors if any(errors) else None,
                color=colour, linewidth=2.0, marker=marker, markersize=6,
                markerfacecolor=colour, markeredgecolor=theme['surface'],
                # A 2px surface ring keeps the two series legible where they
                # cross or run close, which they do at the small separations.
                markeredgewidth=1.5, ecolor=theme['ink_muted'], elinewidth=1.0,
                capsize=2.5, zorder=4)


def plot_separation(result, theme, out_path):
    """Plan cost against table separation, and the gap it opens, as two panels.

    A line chart because the x axis is a continuous quantity that was swept, not
    a set of named configurations -- the slope is the finding, and bars hide a
    slope.  The gap gets its own panel rather than a second y axis on the first:
    cost units and percent do not share a scale, and a dual axis lets the author
    choose where the two curves appear to cross.
    """
    points = [p for p in result.get('points', [])
              if p['planner']['cost'] is not None or p['script']['cost'] is not None]
    if len(points) < 2:
        print('Skipping {} -- need at least two separations'.format(out_path))
        return
    shipped = result.get('config', {}).get('shipped_separation')

    panel_w, panel_h, header = 4.0, 3.0, 1.45
    fig, axes = plt.subplots(1, 2, figsize=(2 * panel_w, panel_h + header), dpi=DPI)
    fig.patch.set_facecolor(theme['surface'])
    fig_h = panel_h + header

    separations = [p['separation'] for p in points]
    x_lo = min(separations) - 0.06 * (max(separations) - min(separations))
    # Headroom on the right for the direct labels at the last point.
    x_hi = max(separations) + 0.30 * (max(separations) - min(separations))

    # -- Panel 1: cost -----------------------------------------------------
    cost_ax = axes[0]
    all_costs = []
    for side, label, slot in SEPARATION_SERIES:
        xs, ys, errors = _separation_xy(points, side, 'cost')
        if not xs:
            continue
        all_costs.extend(ys)
        _separation_line(cost_ax, theme, xs, ys, errors, theme['series'][slot],
                         SEPARATION_MARKER[slot])
        cost_ax.annotate(label, (xs[-1], ys[-1]), textcoords='offset points',
                         xytext=(8, -2), ha='left', va='center', fontsize=8,
                         color=theme['ink_secondary'], zorder=6)
    cost_ax.set_ylabel('plan cost', color=theme['ink_muted'], fontsize=8)
    cost_ax.set_title('Plan cost', color=theme['ink'], fontsize=9.5, loc='left', pad=8)
    if all_costs:
        span = (max(all_costs) - min(all_costs)) or 1.
        cost_ax.set_ylim(min(all_costs) - 0.14 * span, max(all_costs) + 0.14 * span)
        cost_ax.yaxis.set_major_formatter(_tick_formatter(max(all_costs)))

    # -- Panel 2: the gap --------------------------------------------------
    gap_ax = axes[1]
    gap_x = [p['separation'] for p in points if p['gap_fraction'] is not None]
    gap_y = [100. * p['gap_fraction'] for p in points if p['gap_fraction'] is not None]
    if gap_x:
        # The quantity plotted is the *planner's* advantage, so it wears the
        # planner's hue and marker from panel 1 rather than a third colour.
        _separation_line(gap_ax, theme, gap_x, gap_y, [0.] * len(gap_x),
                         theme['series'][1], SEPARATION_MARKER[1])
        gap_ax.annotate('{:.0f}%'.format(gap_y[-1]), (gap_x[-1], gap_y[-1]),
                        textcoords='offset points', xytext=(8, -2), ha='left',
                        va='center', fontsize=8, color=theme['ink_secondary'])
        # Zero is meaningful here -- it is "the two are the same cost" -- so the
        # panel includes it rather than cropping to the data range.
        gap_ax.set_ylim(min(0., min(gap_y) - 3.), max(gap_y) * 1.22)
    gap_ax.set_ylabel('planner cheaper by (%)', color=theme['ink_muted'], fontsize=8)
    gap_ax.set_title('Cost advantage', color=theme['ink'], fontsize=9.5,
                     loc='left', pad=8)

    for ax in axes:
        ax.set_xlim(x_lo, x_hi)
        ax.set_xlabel('table separation (m)', color=theme['ink_muted'], fontsize=8)
        ax.set_xticks(separations)
        ax.xaxis.set_major_formatter(_tick_formatter(max(separations)))
        style_axes(ax, theme)
        # A swept continuous x deserves vertical guides: the reader's question is
        # "what is it at separation 8", which is a lookup along x.
        ax.xaxis.grid(True, color=theme['grid'], linewidth=0.8, linestyle='-')
        if shipped is not None and x_lo <= shipped <= x_hi:
            ax.axvline(shipped, color=theme['axis'], linewidth=1.0, zorder=1)
            ax.annotate('shipped', (shipped, 1.0), xycoords=('data', 'axes fraction'),
                        textcoords='offset points', xytext=(4, -8), ha='left',
                        va='top', fontsize=7.5, color=theme['ink_muted'])

    handles = [plt.Line2D([], [], color=theme['series'][slot], linewidth=2.0,
                          marker=SEPARATION_MARKER[slot], markersize=6,
                          markeredgecolor=theme['surface'], markeredgewidth=1.5,
                          label=label)
               for _, label, slot in SEPARATION_SERIES]
    fig.legend(handles=handles, loc='upper right',
               bbox_to_anchor=(0.995, 1 - 0.30 / fig_h), frameon=False, fontsize=8.5,
               labelcolor=theme['ink_secondary'])

    fig.tight_layout(rect=(0, 0, 1, 1 - header / fig_h))
    # Kept short on purpose: the legend sits at the same height on the right, and a
    # longer heading runs straight into it.
    fig.text(0.011, 1 - 0.34 / fig_h,
             'Cost gap against table separation (multi_object)',
             color=theme['ink'], fontsize=13, fontweight='bold', ha='left', va='center')

    config = result.get('config', {})
    planner_slope, script_slope = (config.get('planner_cost_slope'),
                                   config.get('script_cost_slope'))
    slopes = ('' if planner_slope is None or script_slope is None else
              ' Least-squares cost per metre of separation: planner {:+.1f}, state '
              'machine {:+.1f}.'.format(planner_slope, script_slope))
    trials = config.get('trials') or 0
    subtitle = ('The finding is the slope, not any single separation. Every plan here is 12 '
                'actions with 6 base moves, so the flat per-action charges cancel and distance '
                'driven is the whole cost signal. The planner loads all three cubes onto the '
                'tray and crosses between the tables once; the fixed-order state machine '
                'crosses once per cube, so its cost grows with separation about {} times as '
                'fast.{} {} trial{} per point; error bars are the population standard '
                'deviation.'.format(
                    'four' if not (planner_slope and script_slope)
                    else '{:.0f}'.format(script_slope / planner_slope),
                    slopes, trials, '' if trials == 1 else 's'))
    fig.text(0.011, 1 - 0.72 / fig_h, _wrap(subtitle, 2 * panel_w, 8.5),
             color=theme['ink_secondary'], fontsize=8.5, ha='left', va='top')
    _save(fig, out_path, theme)


def write_separation_table(result, out_path):
    config = result.get('config', {})
    lines = ['# Cost against table separation -- mean +/- population std', '',
             'Scenario {} / {}, algorithm {}, {} trials per side per separation. '
             'The scenario ships at separation {:.1f}.'.format(
                 config.get('phase'), config.get('scenario'), config.get('algorithm'),
                 config.get('trials'), config.get('shipped_separation') or float('nan')),
             '',
             '| separation | planner cost | state machine cost | gap | planner cheaper by | '
             'planner tray peak | planner base travel | state machine base travel | '
             'solved (planner / script) |',
             '|---|---|---|---|---|---|---|---|---|']
    for point in result.get('points', []):
        planner, script = point['planner'], point['script']

        def cost_cell(side):
            if side['cost'] is None:
                return '_no solution_'
            return '{:.2f} ± {:.2f}'.format(side['cost'], side['cost_std'])

        lines.append('| {:.1f}{} | {} | {} | {} | {} | {} | {} | {} | {} / {} |'.format(
            point['separation'], ' **(shipped)**' if point['shipped'] else '',
            cost_cell(planner), cost_cell(script),
            '{:.2f}'.format(point['gap']) if point['gap'] is not None else '-',
            '{:.1f}%'.format(100. * point['gap_fraction'])
            if point['gap_fraction'] is not None else '-',
            '{:.1f}'.format(planner['tray_peak']) if planner['tray_peak'] else '-',
            '{:.2f}'.format(planner['travel']) if planner['travel'] else '-',
            '{:.2f}'.format(script['travel']) if script['travel'] else '-',
            planner['solved_trials'], script['solved_trials']))
    lines += ['',
              '`tray peak` is the largest number of objects on the tray at once, so it is '
              'the mechanism behind the gap: the planner reaches 3, and the state machine '
              'is structurally 1 -- it transfers objects one at a time in a fixed order.',
              '',
              'Cost per unit separation (least squares): planner {}, state machine {}.'.format(
                  '{:+.2f}'.format(config['planner_cost_slope'])
                  if config.get('planner_cost_slope') is not None else 'n/a',
                  '{:+.2f}'.format(config['script_cost_slope'])
                  if config.get('script_cost_slope') is not None else 'n/a'),
              '',
              'Caveat, as recorded in separation.py: `adaptive` persists its stream '
              'statistics per domain, so absolute costs shift by a few units between '
              'campaigns. The slope is the reproducible quantity, not the offset.',
              '']
    with open(out_path, 'w') as fh:
        fh.write('\n'.join(lines))
    print('Wrote', out_path)


# --------------------------------------------------------------------------
# Table view
# --------------------------------------------------------------------------

def write_table(result, out_path):
    keys, rows, index = _keys(result), _rows(result), _index(result)
    config = result.get('config', {})
    lines = ['# {} -- mean +/- population std'.format(
        SWEEP_TITLES.get(result['sweep'], result['sweep'])), '']
    lines.append('Up to {} trials per cell.{}'.format(
        config.get('trials'),
        ' Cells the probe found unsolvable were re-run at n={} instead; they are '
        'marked below.'.format(config.get('failed_trials'))
        if config.get('failed_trials') else ''))
    lines.append('')

    for metric, title, unit, pattern in COMPARE_METRICS:
        values = []
        for row in rows:
            for key in keys:
                average = (index.get((row[0], row[1], key)) or {}).get('average') or {}
                if average.get(metric) is not None:
                    values.append(average[metric])
        if not values:
            continue
        cell_pattern = _value_pattern(values, pattern)
        lines.append('## {}{}'.format(title, ' ({})'.format(unit) if unit else ''))
        lines.append('')
        if metric == 'cost':
            # The figures drop these rows; the table keeps them, so it has to say
            # why they are flat. A column of 0.00 with no note reads as a
            # measurement rather than as an absent axis.
            degenerate = _cost_is_degenerate(result, rows, keys, index)
            if degenerate:
                lines.append('{} report 0 by construction: that domain\'s '
                             'domain.pddl has no `increase (total-cost)` effects, '
                             'so no action carries a cost.'.format(
                                 ', '.join('{} / {}'.format(*row)
                                           for row in degenerate)))
                lines.append('')
        lines.append('| scenario | ' + ' | '.join(keys) + ' |')
        lines.append('|' + '|'.join(['---'] * (len(keys) + 1)) + '|')
        for row in rows:
            cells = ['{} / {}'.format(row[0], row[1])]
            for key in keys:
                cell = index.get((row[0], row[1], key))
                average = (cell or {}).get('average') or {}
                mean = average.get(metric)
                std = average.get(metric + '_std')
                solved = average.get('solved_trials') or 0
                if mean is None or (metric != 'success_rate' and not solved):
                    cells.append('_{}_'.format(_status_note(cell) or 'n/a'))
                elif std:
                    cells.append('{} ± {}'.format(_fmt(mean, cell_pattern),
                                                  _fmt(std, cell_pattern)))
                else:
                    cells.append(_fmt(mean, cell_pattern))
            lines.append('| ' + ' | '.join(cells) + ' |')
        lines.append('')

    lines.append('## Trials actually run per cell')
    lines.append('')
    lines.append('| scenario | ' + ' | '.join(keys) + ' |')
    lines.append('|' + '|'.join(['---'] * (len(keys) + 1)) + '|')
    for row in rows:
        cells = ['{} / {}'.format(row[0], row[1])]
        for key in keys:
            cell = index.get((row[0], row[1], key))
            if cell is None:
                cells.append('-')
                continue
            count = len(cell.get('trials', []))
            note = ' ({})'.format(cell['status']) if cell.get('status') not in ('ok', 'cached') else ''
            cells.append('{}{}'.format(count, note))
        lines.append('| ' + ' | '.join(cells) + ' |')
    lines.append('')

    # Two of the failures are silent by the time they reach us -- FD swallows its
    # own exit code, and the AssertionError text is not self-explanatory -- so the
    # hand-diagnosed cause is attached here rather than left for the reader to
    # rediscover.  Only for keys that actually failed in this sweep, and only when
    # the failure was not a hang: a hang already carries its site inline, and
    # binding's at_work hang is a different fault from the AssertionError the
    # probe saw it raise on the same cell -- attaching that note here would file
    # the measured failure under the wrong cause.
    failed = set()
    for key in keys:
        for row in rows:
            cell = index.get((row[0], row[1], key))
            if ((cell or {}).get('average') or {}).get('solved_trials'):
                continue
            if cell is not None and cell.get('hang_site'):
                continue
            failed.add(key)
    notes = [(key, DIAGNOSED_FAILURES[key]) for key in keys
             if key in failed and key in DIAGNOSED_FAILURES]
    if notes:
        lines.append('## Why these configurations found no plan')
        lines.append('')
        for key, note in notes:
            lines.append('- **{}** -- {}'.format(key, note))
        lines.append('')

    with open(out_path, 'w') as fh:
        fh.write('\n'.join(lines))
    print('Wrote', out_path)


# --------------------------------------------------------------------------
# Baseline: script vs. planner, side by side
# --------------------------------------------------------------------------

def build_baseline_comparison(baseline, main_results):
    """Fold the headline planner run into the baseline sweep as a second key."""
    cells = list(baseline['cells'])
    for phase in main_results.get('phases', []):
        for scenario in phase['scenarios']:
            cells.append({
                'axis': 'baseline', 'key': 'planner',
                'phase': phase['phase'], 'scenario': scenario['label'],
                'problem': scenario['problem'], 'complexity': scenario['complexity'],
                'requested_trials': main_results['config']['trials'],
                'status': 'ok',
                'trials': scenario['trials'],
                'average': scenario['average'],
            })
    # Keep script and planner adjacent per scenario, scenarios in registry order.
    order = {}
    for cell in cells:
        order.setdefault((cell['phase'], cell['scenario']), len(order))
    cells.sort(key=lambda c: (order[(c['phase'], c['scenario'])],
                              0 if c['key'] == 'script' else 1))
    return {
        'sweep': 'baseline',
        'config': {'trials': main_results['config']['trials'],
                   'script': baseline.get('config', {})},
        'cells': cells,
    }


# --------------------------------------------------------------------------

def plot_sweep(result, out_dir, theme_name='light'):
    theme = THEMES[theme_name]
    plt.rcParams['font.family'] = FONT
    plt.rcParams['axes.unicode_minus'] = False
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    sweep = result['sweep']
    suffix = '' if theme_name == 'light' else '_dark'

    # The separation scan is a swept parameter, not a set of configuration cells,
    # so it has its own shape and its own figure and shares none of the machinery
    # below.
    if sweep == 'separation':
        plot_separation(result, theme,
                        os.path.join(out_dir, 'separation_cost{}.png'.format(suffix)))
        if theme_name == 'light':
            write_separation_table(result, os.path.join(out_dir, 'separation_table.md'))
        return

    plot_coverage(result, theme,
                  os.path.join(out_dir, '{}_coverage{}.png'.format(sweep, suffix)))
    plot_metric_by_scenario(result, theme,
                            os.path.join(out_dir, '{}_runtime{}.png'.format(sweep, suffix)))
    if sweep == 'planners':
        plot_tradeoff(result, theme,
                      os.path.join(out_dir, 'planners_tradeoff{}.png'.format(suffix)))
    if sweep == 'baseline':
        plot_metric_by_scenario(
            result, theme,
            os.path.join(out_dir, 'baseline_cost{}.png'.format(suffix)),
            metric='cost', title='Plan cost', unit='', pattern='{:.2f}')
    if theme_name == 'light':
        write_table(result, os.path.join(out_dir, '{}_table.md'.format(sweep)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-i', '--in-dir', default=SWEEP_DIR)
    parser.add_argument('-o', '--out-dir', default=None)
    parser.add_argument('--theme', default='light', choices=sorted(THEMES))
    parser.add_argument('--sweep', default=None,
                        help='Only this sweep (algorithms / planners / baseline / separation)')
    args = parser.parse_args(argv)

    out_dir = args.out_dir or args.in_dir
    wanted = ([args.sweep] if args.sweep else
              ['algorithms', 'planners', 'baseline', 'separation'])

    for sweep in wanted:
        path = os.path.join(args.in_dir, '{}.json'.format(sweep))
        if not os.path.exists(path):
            print('Skipping {} -- {} not found'.format(sweep, path))
            continue
        with open(path) as fh:
            result = json.load(fh)
        if sweep == 'baseline':
            main_path = os.path.join(RESULTS_DIR, 'results.json')
            if os.path.exists(main_path):
                with open(main_path) as fh:
                    result = build_baseline_comparison(result, json.load(fh))
            else:
                print('No results.json -- plotting the script alone, with no planner column')
        plot_sweep(result, out_dir, theme_name=args.theme)


if __name__ == '__main__':
    main()
