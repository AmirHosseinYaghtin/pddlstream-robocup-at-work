#!/usr/bin/env python
"""Plot the averaged evaluation metrics per scenario.

    python -m evaluations.plot                       # from results/results.json
    python -m evaluations.plot --theme dark
    python -m evaluations.plot -i other/results.json -o other/

Three figures per phase, plus a table view that carries every number:

  <phase>_metrics.png         small multiples, one panel per metric
  <phase>_time_breakdown.png  stacked search vs. sample time
  <phase>_heatmap.png         metric x scenario grid, each row scaled to itself
  <phase>_table.md            mean +/- population std for every metric

Form rationale (the eight metrics have eight unrelated scales, e.g. seconds vs.
fact counts vs. plan cost):
  * one panel per metric -- NEVER a second y-axis on one plot;
  * scenarios stay in the registry's complexity order on every x axis, so the
    left-to-right direction is the experiment's independent variable;
  * bars start at zero (no truncated baseline) and are one hue -- colour would
    otherwise encode rank, which it must not;
  * search/sample time is a genuine part-to-whole, so that one is stacked and
    gets two categorical hues plus a legend.

Colours come from the project's validated data-viz palette (blue slot 1 and
orange slot 2, light and dark steps); both sets pass the colourblind-separation,
lightness-band, chroma and contrast gates.
"""

from __future__ import print_function

import argparse
import json
import os

import matplotlib
matplotlib.use('Agg')  # headless: these are files, not windows

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import PathPatch
from matplotlib.path import Path

# --------------------------------------------------------------------------
# Theme -- validated palette values, one dict per mode.
# --------------------------------------------------------------------------

LIGHT = {
    'surface': '#fcfcfb',
    'ink': '#0b0b0b',
    'ink_secondary': '#52514e',
    'ink_muted': '#898781',
    'grid': '#e1e0d9',
    'axis': '#c3c2b7',
    'series': ['#2a78d6', '#eb6834'],   # categorical slots 1, 2
    # Sequential blue, steps 100 -> 700, for the heatmap only.
    'ramp': ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b'],
    'on_ramp_light': '#0b0b0b',
    'on_ramp_dark': '#ffffff',
}

DARK = {
    'surface': '#1a1a19',
    'ink': '#ffffff',
    'ink_secondary': '#c3c2b7',
    'ink_muted': '#898781',
    'grid': '#2c2c2a',
    'axis': '#383835',
    'series': ['#3987e5', '#d95926'],
    'ramp': ['#0d366b', '#184f95', '#256abf', '#3987e5', '#6da7ec', '#9ec5f4', '#cde2fb'],
    'on_ramp_light': '#ffffff',
    'on_ramp_dark': '#0b0b0b',
}

THEMES = {'light': LIGHT, 'dark': DARK}

FONT = ['DejaVu Sans', 'sans-serif']

# --------------------------------------------------------------------------
# Metric presentation. Order == the order they are plotted.
# --------------------------------------------------------------------------

# (key, panel title, unit suffix, value format)
METRIC_SPECS = [
    ('run_time', 'Total run time', 's', '{:.3f}'),
    ('search_time', 'Search time', 's', '{:.3f}'),
    ('sample_time', 'Sample time', 's', '{:.3f}'),
    ('evaluations', 'Evaluations', '', '{:.0f}'),
    ('iterations', 'Iterations', '', '{:.1f}'),
    ('complexity', 'Final complexity limit', '', '{:.1f}'),
    ('skeletons', 'Plan skeletons', '', '{:.1f}'),
    ('cost', 'Plan cost', '', '{:.2f}'),
]

TABLE_SPECS = METRIC_SPECS + [
    ('length', 'Plan length', 'actions', '{:.1f}'),
    ('success_rate', 'Success rate', '', '{:.2f}'),
]

BAR_WIDTH = 0.58        # thin marks: a bar narrower than its gap
CORNER_PX = 4.0         # rounded data-end
GAP_PX = 2.0            # surface gap between stacked segments
DPI = 200


# --------------------------------------------------------------------------
# Rounded bars
# --------------------------------------------------------------------------

def _px_to_data(ax, pixels, panel_inches):
    """Convert a length in CSS-ish px to data units on both axes.

    Done arithmetically from the panel's inch size rather than from a live
    transform so the geometry does not depend on when the figure is drawn.
    Returns (dx, dy) such that dx and dy cover the same on-screen distance.
    """
    panel_w, panel_h = panel_inches
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    dx = (x1 - x0) * (pixels / float(DPI)) / panel_w
    dy = (y1 - y0) * (pixels / float(DPI)) / panel_h
    return dx, dy


def rounded_bar(ax, center, height, width, color, panel_inches, base=0.):
    """A bar with a square baseline end and a rounded data end."""
    if height is None:
        return
    x0, x1 = center - width / 2., center + width / 2.
    top = base + height
    _, ry = _px_to_data(ax, CORNER_PX, panel_inches)
    rx = min(CORNER_PX / float(DPI) / panel_inches[0] * (ax.get_xlim()[1] - ax.get_xlim()[0]),
             width / 2.)
    ry = min(ry, abs(height))
    if rx <= 0 or ry <= 0:
        ax.add_patch(PathPatch(Path([(x0, base), (x1, base), (x1, top), (x0, top)],
                                    [Path.MOVETO] + [Path.LINETO] * 3),
                               facecolor=color, edgecolor='none', zorder=3))
        return
    verts = [
        (x0, base), (x1, base),
        (x1, top - ry),
        (x1, top), (x1 - rx, top),     # quadratic corner
        (x0 + rx, top),
        (x0, top), (x0, top - ry),     # quadratic corner
        (x0, base),
    ]
    codes = [
        Path.MOVETO, Path.LINETO,
        Path.LINETO,
        Path.CURVE3, Path.CURVE3,
        Path.LINETO,
        Path.CURVE3, Path.CURVE3,
        Path.CLOSEPOLY,
    ]
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=color,
                           edgecolor='none', zorder=3))


# --------------------------------------------------------------------------
# Shared chrome
# --------------------------------------------------------------------------

def style_axes(ax, theme, ygrid=True):
    ax.set_facecolor(theme['surface'])
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.spines['bottom'].set_color(theme['axis'])
    ax.spines['bottom'].set_linewidth(0.8)
    ax.tick_params(axis='both', length=0, colors=theme['ink_muted'], labelsize=8)
    if ygrid:
        # Solid hairlines, one shade off the surface -- never dashed.
        ax.yaxis.grid(True, color=theme['grid'], linewidth=0.8, linestyle='-')
        ax.set_axisbelow(True)
    ax.xaxis.grid(False)


def _fmt(value, pattern):
    return 'n/a' if value is None else pattern.format(value)


def _nonnull(values):
    return [v for v in values if v is not None]


# --------------------------------------------------------------------------
# Figure 1 -- small multiples, one panel per metric
# --------------------------------------------------------------------------

def plot_metric_panels(phase, trials, theme, out_path):
    scenarios = phase['scenarios']
    labels = [s['label'] for s in scenarios]
    ncols, nrows = 4, 2
    panel_w, panel_h = 2.9, 2.55
    header = 1.15
    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(ncols * panel_w, nrows * panel_h + header), dpi=DPI)
    fig.patch.set_facecolor(theme['surface'])
    fig_h = nrows * panel_h + header

    for index, (key, title, unit, pattern) in enumerate(METRIC_SPECS):
        ax = axes[index // ncols][index % ncols]
        means = [s['average'].get(key) for s in scenarios]
        stds = [s['average'].get(key + '_std') for s in scenarios]
        present = _nonnull(means)

        heading = title if not unit else '{} ({})'.format(title, unit)
        ax.set_title(heading, color=theme['ink'], fontsize=9.5,
                     fontweight='normal', loc='left', pad=8)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=8)
        ax.set_xlim(-0.6, len(labels) - 0.4)

        # Two degenerate cases get a plain statement instead of a plot: a metric
        # the algorithm never reported, and a metric that is identically zero
        # (discrete2d has no action costs, so its 'cost' is always 0 -- an empty
        # panel with a lone '0.00' floating on the baseline reads as a bug).
        note = None
        if not present:
            note = 'not reported by this algorithm'
        elif max(present) == 0:
            note = 'zero in every scenario'
        if note is not None:
            ax.text(0.5, 0.5, note, transform=ax.transAxes, ha='center', va='center',
                    color=theme['ink_muted'], fontsize=8.5)
            style_axes(ax, theme, ygrid=False)
            ax.set_yticks([])
            continue

        top = max(m + (s or 0.) for m, s in zip(means, stds) if m is not None)
        ax.set_ylim(0, top * 1.3)
        ax.set_yticks(_ticks(0, ax.get_ylim()[1]))
        ax.yaxis.set_major_formatter(_tick_formatter(top))
        pattern = _value_pattern(present, pattern)

        for position, (mean, std) in enumerate(zip(means, stds)):
            rounded_bar(ax, position, mean, BAR_WIDTH, theme['series'][0],
                        (panel_w, panel_h))
            if mean is not None and std:
                ax.errorbar(position, mean, yerr=std, ecolor=theme['ink_muted'],
                            elinewidth=1.0, capsize=3, capthick=1.0, fmt='none',
                            zorder=4)

        # Direct-label selectively: the extreme, plus the most complex scenario
        # (the right-hand end) when that is not already the extreme. Every other
        # number lives in the table view.
        peak = max(range(len(means)), key=lambda i: -1 if means[i] is None else means[i])
        last = max(i for i in range(len(means)) if means[i] is not None)
        for position in sorted({peak, last}):
            ax.annotate(_fmt(means[position], pattern),
                        (position, means[position] + (stds[position] or 0.)),
                        textcoords='offset points', xytext=(0, 6), ha='center',
                        color=theme['ink_secondary'], fontsize=8.5)

        style_axes(ax, theme)

    fig.tight_layout(rect=(0, 0, 1, 1 - header / fig_h))
    fig.text(0.011, 1 - 0.34 / fig_h,
             '{} -- planner metrics by scenario'.format(phase['phase']),
             color=theme['ink'], fontsize=13, fontweight='bold', ha='left', va='center')
    fig.text(0.011, 1 - 0.68 / fig_h,
             'Adaptive algorithm, mean of {} trials. Scenarios are ordered left to right by '
             'increasing complexity; error bars are the population standard deviation.'.format(trials),
             color=theme['ink_secondary'], fontsize=9, ha='left', va='center')
    _save(fig, out_path, theme)


def _value_pattern(values, default):
    """Widen the format when the default would print every value as 0.000."""
    ceiling = max(abs(v) for v in values)
    if ceiling == 0:
        return default
    if ceiling < 1e-3:
        return '{:.2e}'
    if ceiling < 1e-2 and default.endswith('3f}'):
        return '{:.5f}'
    return default


def _tick_formatter(ceiling):
    from matplotlib.ticker import FuncFormatter
    if 0 < ceiling < 1e-3:
        return FuncFormatter(lambda v, _: '0' if v == 0 else '{:.0e}'.format(v))
    if ceiling < 1:
        return FuncFormatter(lambda v, _: '0' if v == 0 else ('%g' % v))
    return FuncFormatter(lambda v, _: '%g' % v)


def _ticks(low, high, count=3):
    """`count`+1 evenly spaced ticks over [low, high], rounded to a nice step."""
    if high <= low:
        return [low]
    raw = (high - low) / float(count)
    magnitude = 10 ** int(_floor_log10(raw))
    for multiple in (1, 2, 2.5, 5, 10):
        step = multiple * magnitude
        if step >= raw:
            break
    ticks, value = [], low
    while value <= high + step * 1e-9:
        ticks.append(round(value, 10))
        value += step
    return ticks


def _floor_log10(value):
    import math
    return math.floor(math.log10(value)) if value > 0 else 0


# --------------------------------------------------------------------------
# Figure 2 -- run time decomposed into search vs. sample
# --------------------------------------------------------------------------

def plot_time_breakdown(phase, trials, theme, out_path):
    scenarios = phase['scenarios']
    labels = [s['label'] for s in scenarios]
    search = [s['average'].get('search_time') or 0. for s in scenarios]
    sample = [s['average'].get('sample_time') or 0. for s in scenarios]
    totals = [a + b for a, b in zip(search, sample)]

    panel_w, panel_h = max(5.2, 1.5 * len(labels) + 2.2), 4.2
    fig, ax = plt.subplots(figsize=(panel_w, panel_h), dpi=DPI)
    fig.patch.set_facecolor(theme['surface'])

    ax.set_xlim(-0.6, len(labels) - 0.4)
    ax.set_ylim(0, (max(totals) if max(totals) > 0 else 1.) * 1.22)
    ax.set_yticks(_ticks(0, ax.get_ylim()[1]))
    _, gap = _px_to_data(ax, GAP_PX, (panel_w, panel_h))

    for position, (lower, upper) in enumerate(zip(search, sample)):
        rounded_bar(ax, position, lower, BAR_WIDTH, theme['series'][0],
                    (panel_w, panel_h))
        # A 2px surface gap separates the segments -- never an outline.
        if upper > gap:
            rounded_bar(ax, position, upper - gap, BAR_WIDTH, theme['series'][1],
                        (panel_w, panel_h), base=lower + gap)
        ax.annotate('{:.3f}s'.format(lower + upper), (position, lower + upper),
                    textcoords='offset points', xytext=(0, 7), ha='center',
                    color=theme['ink_secondary'], fontsize=9)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=0 if len(labels) < 5 else 20,
                       ha='center' if len(labels) < 5 else 'right', fontsize=9)
    ax.set_ylabel('seconds', color=theme['ink_muted'], fontsize=9)
    style_axes(ax, theme)

    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=theme['series'][0], edgecolor='none'),
               plt.Rectangle((0, 0), 1, 1, facecolor=theme['series'][1], edgecolor='none')]
    legend = ax.legend(handles, ['search time', 'sample time'], loc='upper left',
                       frameon=False, fontsize=9, handlelength=1.1, handleheight=1.1,
                       borderpad=0., labelspacing=0.5)
    for text in legend.get_texts():
        text.set_color(theme['ink_secondary'])

    ax.set_title('{} -- where the time goes (adaptive, mean of {} trials)'.format(
        phase['phase'], trials), color=theme['ink'], fontsize=12,
        fontweight='bold', loc='left', pad=16)
    fig.tight_layout()
    _save(fig, out_path, theme)


# --------------------------------------------------------------------------
# Figure 3 -- metric x scenario heatmap, each row scaled to its own maximum
# --------------------------------------------------------------------------

def plot_heatmap(phase, trials, theme, out_path):
    scenarios = phase['scenarios']
    labels = [s['label'] for s in scenarios]
    specs = [spec for spec in METRIC_SPECS
             if _nonnull([s['average'].get(spec[0]) for s in scenarios])]

    cmap = LinearSegmentedColormap.from_list('seq_blue', theme['ramp'])
    panel_w = max(5.4, 1.55 * len(labels) + 3.4)
    panel_h = 0.62 * len(specs) + 1.9
    fig, ax = plt.subplots(figsize=(panel_w, panel_h), dpi=DPI)
    fig.patch.set_facecolor(theme['surface'])
    ax.set_facecolor(theme['surface'])

    for row, (key, title, unit, pattern) in enumerate(specs):
        values = [s['average'].get(key) for s in scenarios]
        ceiling = max(_nonnull(values))
        pattern = _value_pattern(_nonnull(values), pattern)
        for column, value in enumerate(values):
            if value is None:
                continue
            fraction = 0. if ceiling <= 0 else value / float(ceiling)
            face = cmap(fraction)
            # 2px surface gap: inset every cell instead of stroking it.
            ax.add_patch(plt.Rectangle((column + 0.03, row + 0.03), 0.94, 0.94,
                                       facecolor=face, edgecolor='none'))
            ink = theme['on_ramp_dark'] if fraction < 0.55 else theme['on_ramp_light']
            ax.text(column + 0.5, row + 0.5, _fmt(value, pattern), ha='center',
                    va='center', color=ink, fontsize=8.5)

    ax.set_xlim(0, len(labels))
    ax.set_ylim(len(specs), 0)
    ax.set_xticks([i + 0.5 for i in range(len(labels))])
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_yticks([i + 0.5 for i in range(len(specs))])
    ax.set_yticklabels(['{}{}'.format(s[1], ' ({})'.format(s[2]) if s[2] else '')
                        for s in specs], fontsize=9)
    ax.tick_params(axis='both', length=0, colors=theme['ink_secondary'])
    ax.xaxis.set_ticks_position('top')
    for side in ('top', 'right', 'left', 'bottom'):
        ax.spines[side].set_visible(False)

    ax.set_title('{} -- each row shaded against its own maximum (mean of {} trials)'.format(
        phase['phase'], trials), color=theme['ink'], fontsize=11.5,
        fontweight='bold', loc='left', pad=30)
    fig.text(0.012, 0.015,
             'Darker = larger. Rows are shaded independently because the metrics '
             'do not share a scale; cell text is the actual mean.',
             color=theme['ink_secondary'], fontsize=8.5, ha='left')
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    _save(fig, out_path, theme)


# --------------------------------------------------------------------------
# Table view
# --------------------------------------------------------------------------

def write_table(phase, trials, out_path):
    """Markdown table view: identity and value never depend on colour alone."""
    scenarios = phase['scenarios']
    lines = ['# {} -- adaptive, mean +/- population std over {} trials'.format(
        phase['phase'], trials), '']
    header = ['metric'] + [s['label'] for s in scenarios]
    lines.append('| ' + ' | '.join(header) + ' |')
    lines.append('|' + '|'.join(['---'] * len(header)) + '|')
    for key, title, unit, pattern in TABLE_SPECS:
        name = '{}{}'.format(title, ' ({})'.format(unit) if unit else '')
        means = _nonnull([s['average'].get(key) for s in scenarios])
        if means:
            pattern = _value_pattern(means, pattern)
        cells = [name]
        for scenario in scenarios:
            mean = scenario['average'].get(key)
            std = scenario['average'].get(key + '_std')
            if mean is None:
                cells.append('n/a')
            elif std:
                cells.append('{} ± {}'.format(_fmt(mean, pattern), _fmt(std, pattern)))
            else:
                cells.append(_fmt(mean, pattern))
        lines.append('| ' + ' | '.join(cells) + ' |')
    lines += ['', '## Scenario complexity (x-axis order)', '']
    for index, scenario in enumerate(scenarios):
        lines.append('{}. **{}** (`-p {}`) -- {}'.format(
            index + 1, scenario['label'], scenario['problem'], scenario['complexity']))
    lines.append('')
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))
    print('Wrote', out_path)


# --------------------------------------------------------------------------

def _save(fig, out_path, theme):
    fig.savefig(out_path, facecolor=theme['surface'], dpi=DPI)
    plt.close(fig)
    print('Wrote', out_path)


def plot_results(results, out_dir, theme='light'):
    palette = THEMES[theme]
    plt.rcParams['font.family'] = FONT
    plt.rcParams['axes.unicode_minus'] = False
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    trials = results['config']['trials']
    suffix = '' if theme == 'light' else '_dark'

    for phase in results['phases']:
        name = phase['phase']
        plot_metric_panels(phase, trials, palette,
                           os.path.join(out_dir, '{}_metrics{}.png'.format(name, suffix)))
        plot_time_breakdown(phase, trials, palette,
                            os.path.join(out_dir, '{}_time_breakdown{}.png'.format(name, suffix)))
        plot_heatmap(phase, trials, palette,
                     os.path.join(out_dir, '{}_heatmap{}.png'.format(name, suffix)))
        write_table(phase, trials, os.path.join(out_dir, '{}_table.md'.format(name)))


def main(argv=None):
    from evaluations.run import RESULTS_DIR, RESULTS_FILE
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-i', '--input', default=os.path.join(RESULTS_DIR, RESULTS_FILE),
                        help='results.json written by evaluations.run (default: %(default)s)')
    parser.add_argument('-o', '--out-dir', default=None,
                        help='Where to write the figures (default: alongside the input)')
    parser.add_argument('--theme', default='light', choices=sorted(THEMES),
                        help='Palette to render with (default: %(default)s)')
    args = parser.parse_args(argv)

    with open(args.input) as f:
        results = json.load(f)
    out_dir = args.out_dir or os.path.dirname(os.path.abspath(args.input))
    plot_results(results, out_dir=out_dir, theme=args.theme)


if __name__ == '__main__':
    main()
