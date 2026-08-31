# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#                                                                             #
#   OpenBench is a chess engine testing framework authored by Andrew Grant.   #
#   <https://github.com/AndyGrant/OpenBench>           <andrew@grantnet.us>   #
#                                                                             #
#   OpenBench is free software: you can redistribute it and/or modify         #
#   it under the terms of the GNU General Public License as published by      #
#   the Free Software Foundation, either version 3 of the License, or         #
#   (at your option) any later version.                                       #
#                                                                             #
#   OpenBench is distributed in the hope that it will be useful,              #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of            #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the             #
#   GNU General Public License for more details.                              #
#                                                                             #
#   You should have received a copy of the GNU General Public License         #
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.     #
#                                                                             #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

import django
import html
import json
import re

import OpenBench.config
import OpenBench.models
import OpenBench.spsa_utils
import OpenBench.stats
import OpenBench.utils

from django.utils.safestring import mark_safe

def oneDigitPrecision(value):
    try:
        value = round(value, 1)
        if '.' not in str(value):
            return str(value) + '.0'
        pre, post = str(value).split('.')
        post += '0'
        return pre + '.' + post[0:1]
    except:
        return value

def twoDigitPrecision(value):
    try:
        value = round(value, 2)
        if '.' not in str(value):
            return str(value) + '.00'
        pre, post = str(value).split('.')
        post += '00'
        return pre + '.' + post[0:2]
    except:
        return value

def gitDiffLink(test):

    repo = OpenBench.utils.path_join(*test.dev.source.split('/')[:-2])
    repo = repo.replace('://api.github.com', '://github.com').replace('/repos/', '/')

    if test.test_mode == 'SPSA':
        return OpenBench.utils.path_join(repo, 'compare', test.dev.sha[:8])

    return OpenBench.utils.path_join(repo, 'compare',
        '{0}..{1}'.format(test.base.sha[:8], test.dev.sha[:8]))

def shortStatBlock(test):

    tri_line   = 'Games: %d W: %d L: %d D: %d' % test.as_nwld()
    penta_line = 'Ptnml(0-2): %d, %d, %d, %d, %d' % test.as_penta()

    if test.test_mode == 'SPSA':
        spsa_run = test.spsa_run # Avoid extra database accesses
        statlines = [
            'Tuning %d Parameters' % (spsa_run.parameters.count()),
            '%d/%d Iterations' % (test.games / (2 * spsa_run.pairs_per), spsa_run.iterations),
            '%d/%d Games Played' % (test.games, 2 * spsa_run.iterations * spsa_run.pairs_per)]

    elif test.test_mode == 'SPRT':
        llr_line = 'LLR: %0.2f (%0.2f, %0.2f) [%0.2f, %0.2f]' % (
            test.currentllr, test.lowerllr, test.upperllr, test.elolower, test.eloupper)
        lower, elo, upper = OpenBench.stats.Elo(test.results())
        elo_line = 'Elo: %0.2f +- %0.2f (95%%)' % (elo, max(upper - elo, elo - lower))
        statlines = [llr_line, tri_line, penta_line, elo_line] if test.use_penta else [llr_line, tri_line]

    elif test.test_mode == 'GAMES':
        lower, elo, upper = OpenBench.stats.Elo(test.results())
        elo_line = 'Elo: %0.2f +- %0.2f (95%%) [N=%d]' % (elo, max(upper - elo, elo - lower), test.max_games)
        statlines = [elo_line, tri_line, penta_line] if test.use_penta else [elo_line, tri_line]

    elif test.test_mode == 'DATAGEN':
        status_line = 'Generated %d/%d Games' % (test.games, test.max_games)
        lower, elo, upper = OpenBench.stats.Elo(test.results())
        elo_line = 'Elo: %0.2f +- %0.2f (95%%) [N=%d]' % (elo, max(upper - elo, elo - lower), test.max_games)
        statlines = [status_line, elo_line, penta_line] if test.use_penta else [status_line, elo_line, tri_line]

    return '\n'.join(statlines)

def longStatBlock(test):

    assert test.test_mode != 'SPSA'

    threads     = int(OpenBench.utils.extract_option(test.dev_options, 'Threads'))
    hashmb      = int(OpenBench.utils.extract_option(test.dev_options, 'Hash'))
    timecontrol = test.dev_time_control + ['s', '']['=' in test.dev_time_control]
    type_text   = 'SPRT' if test.test_mode == 'SPRT' else 'Conf'

    lower, elo, upper = OpenBench.stats.Elo(test.results())

    lines = [
        'Elo   | %0.2f +- %0.2f (95%%)' % (elo, max(upper - elo, elo - lower)),
        '%-5s | %s Threads=%d Hash=%dMB' % (type_text, timecontrol, threads, hashmb),
    ]

    if test.test_mode == 'SPRT':
        lines.append('LLR   | %0.2f (%0.2f, %0.2f) [%0.2f, %0.2f]' % (
            test.currentllr, test.lowerllr, test.upperllr, test.elolower, test.eloupper))

    lines.append('Games | N: %d W: %d L: %d D: %d' % test.as_nwld())

    if test.use_penta:
        lines.append('Penta | [%d, %d, %d, %d, %d]' % test.as_penta())

    return '\n'.join(lines)

def testResultColour(test):

    if test.passed:
        if test.elolower + test.eloupper < 0: return 'blue'
        return 'green'
    if test.failed:
        if test.wins >= test.losses: return 'yellow'
        return 'red'
    return ''

def sumAttributes(iterable, attribute):
    try: return sum([getattr(f, attribute) for f in iterable])
    except: return 0

def insertCommas(value):
    return '{:,}'.format(int(value))

def prettyName(name):
    if re.search('^[0-9a-fA-F]{40}$', name):
        return name[:16].upper()
    return name

def prettyDevName(test):

    # If engines are different, use the base name + branch
    if test.dev_engine != test.base_engine:
        return '[%s] %s' % (test.base_engine, test.base.name)

    # If testing different Networks, possibly use the Network name
    if test.dev.name == test.base.name and test.dev_netname != '':

        # Nets match as well, so revert back to the branch name
        if test.dev_network == test.base_network:
            return prettyName(test.dev.name)

        # Use the network's name, if we still have it saved
        try: return OpenBench.models.Network.objects.get(sha256=test.dev_network).name
        except: return test.dev_netname # File has since been deleted ?

    return prettyName(test.dev.name)

def testIdToPrettyName(test_id):
    return prettyName(OpenBench.models.Test.objects.get(id=test_id).dev.name)

def testIdToTimeControl(test_id):
    return OpenBench.models.Test.objects.get(id=test_id).dev_time_control

def cpuflagsBlock(machine, N=8):

    reported = []
    flags    = machine.info['cpu_flags']

    general_flags   = ['BMI2', 'POPCNT']
    broad_avx_flags = ['AVX2', 'AVX', 'SSE42', 'SSE41', 'SSSE3']

    for flag in general_flags:
        if flag in flags:
            reported.append(flag)
            break

    for flag in broad_avx_flags:
        if flag in flags:
            reported.append(flag)
            break

    for flag in flags:
        if flag not in general_flags and flag not in broad_avx_flags:
            reported.append(flag)

    return ' '.join(reported)

def compilerBlock(machine):
    string = ''
    for engine, info in machine.info['compilers'].items():
        string += '%-16s %-8s (%s)\n' % (engine, info[0], info[1])
    return string

def removePrefix(value, prefix):
    return value.removeprefix(prefix)

def machine_name(machine_id):
    try:
        machine = OpenBench.models.Machine.objects.get(id=machine_id)
        return machine.info['machine_name']
    except: return 'None'


register = django.template.Library()
register.filter('oneDigitPrecision', oneDigitPrecision)
register.filter('twoDigitPrecision', twoDigitPrecision)
register.filter('gitDiffLink', gitDiffLink)
register.filter('shortStatBlock', shortStatBlock)
register.filter('longStatBlock', longStatBlock)
register.filter('testResultColour', testResultColour)
register.filter('sumAttributes', sumAttributes)
register.filter('insertCommas', insertCommas)
register.filter('prettyName', prettyName)
register.filter('prettyDevName', prettyDevName)
register.filter('testIdToPrettyName', testIdToPrettyName)
register.filter('testIdToTimeControl', testIdToTimeControl)
register.filter('cpuflagsBlock', cpuflagsBlock)
register.filter('compilerBlock', compilerBlock)
register.filter('removePrefix', removePrefix)
register.filter('machine_name', machine_name)

def book_download_link(workload):
    if workload.book_name in OpenBench.config.OPENBENCH_CONFIG['books']:
        return OpenBench.config.OPENBENCH_CONFIG['books'][workload.book_name]['source']

def network_download_link(workload, branch):

    assert branch in [ 'dev', 'base' ]

    sha    = workload.dev_network if branch == 'dev' else workload.base_network
    engine = workload.dev_engine  if branch == 'dev' else workload.base_engine

    # Network could have been deleted after this workload was finished
    if (network := OpenBench.models.Network.objects.filter(sha256=sha, engine=engine).first()):
        return '/networks/%s/download/%s/' % (engine, sha)

    return '/networks/%s/' % (engine)

def workload_url(workload):

    # Might be a workload id
    if type(workload) == int:
        workload = OpenBench.models.Test.objects.get(id=workload)

    # Differentiate between Tunes, Datagen, and regular Tests
    mapping = { 'SPSA' : 'tune', 'DATAGEN' : 'datagen' }
    return '/%s/%d/' % (mapping.get(workload.test_mode, 'test'), workload.id)

def workload_pretty_name(workload):

    # Might be a workload id
    if type(workload) == int:
        workload = OpenBench.models.Test.objects.get(id=workload)

    # Convert commit sha's to just the first 16 characters
    if re.search('^[0-9a-fA-F]{40}$', workload.dev.name):
        return workload.dev.name[:16].lower()

    return workload.dev.name

def git_diff_text(workload, N=24):

    dev_name = workload.dev.name
    dev_name = dev_name[:N] + '...' if len(dev_name) > N else dev_name

    base_name = workload.base.name
    base_name = base_name[:N] + '...' if len(base_name) > N else base_name

    return '%s vs %s' % (dev_name, base_name)


def test_is_smp_odds(test):
    dev_threads  = int(OpenBench.utils.extract_option(test.dev_options , 'Threads'))
    base_threads = int(OpenBench.utils.extract_option(test.base_options, 'Threads'))
    return dev_threads != base_threads

def test_is_time_odds(test):
    return test.dev_time_control != test.base_time_control

def test_is_fischer(test):
    return 'FRC' in test.book_name.upper() or '960' in test.book_name.upper()

register.filter('book_download_link', book_download_link)
register.filter('network_download_link', network_download_link)

register.filter('workload_url', workload_url)
register.filter('workload_pretty_name', workload_pretty_name)

register.filter('git_diff_text', git_diff_text)

register.filter('test_is_smp_odds'  , test_is_smp_odds  )
register.filter('test_is_time_odds' , test_is_time_odds )
register.filter('test_is_fischer'   , test_is_fischer   )


@register.filter
def next(iterable, index):
    try: return iterable[int(index) + 1]
    except: return None

@register.filter
def previous(iterable, index):
    try: return iterable[int(index) - 1]
    except: return None


def llr_history_graph(test, width=340, height=120):

    ## Render the LLR-over-games series as a standalone inline SVG. Doing this
    ## server-side keeps the workload page free of charting dependencies, and
    ## lets the graph render before any JavaScript runs. The hover readout is
    ## wired up in workload.html, using the JSON we stash on the wrapper.

    if test.test_mode != 'SPRT':
        return ''

    history     = list(OpenBench.utils.load_llr_history(test))
    cur_verdict = int(test.wins >= test.losses)

    # The series always starts at the origin, and ends at the present
    if not history or history[0][0] != 0:
        history.insert(0, [0, 0.0])
    if history[-1][0] != test.games or history[-1][1] != test.currentllr:
        history.append([test.games, test.currentllr, cur_verdict])

    x_max = max(max(p[0] for p in history), 1)

    # Center 0.00 vertically, and pad out past the widest observed value
    observed = max(abs(test.lowerllr), abs(test.upperllr), max(abs(p[1]) for p in history))
    extent   = max(observed * 1.15, 0.5)
    y_min, y_max = -extent, extent

    L, R, T, B = 8, 8, 8, 8
    iw, ih = max(width - L - R, 1), max(height - T - B, 1)

    sx = lambda v : L + iw * (v / x_max)
    sy = lambda v : T + ih * (1.0 - (v - y_min) / (y_max - y_min))

    verdict = lambda p : p[2] if len(p) >= 3 else cur_verdict

    points = [{
        'g' : p[0], 'l' : round(p[1], 4), 'v' : verdict(p),
        'x' : round(sx(p[0]), 2), 'y' : round(sy(p[1]), 2),
    } for p in history]

    # Above 0.0 is green; below is red, unless we are winning on raw score
    def band(p):
        if p['l'] >= 0.0: return 'pos'
        return 'yellow' if p['v'] else 'neg'

    # Split the polyline at each colour change, interpolating the zero crossing
    def crossing(a, b):
        denom = b['l'] - a['l']
        if abs(denom) < 1e-7: return None
        r = -a['l'] / denom
        return {
            'g' : a['g'] + r * (b['g'] - a['g']), 'l' : 0.0, 'v' : b['v'],
            'x' : round(a['x'] + r * (b['x'] - a['x']), 2), 'y' : round(sy(0.0), 2),
        }

    segments = { 'pos' : [], 'yellow' : [], 'neg' : [] }
    segment  = [points[0]]
    category = band(points[0])

    for i in range(1, len(points)):

        a, b, b_category = points[i-1], points[i], band(points[i])

        if b_category == category:
            segment.append(b)
            continue

        if (a['l'] >= 0.0) != (b['l'] >= 0.0):
            cross = crossing(a, b)
            if cross: segment.append(cross)
            if len(segment) >= 2: segments[category].append(segment)
            segment = [cross, b] if cross else [b]
        else:
            if len(segment) >= 2: segments[category].append(segment)
            segment = [a, b]

        category = b_category

    if len(segment) >= 2:
        segments[category].append(segment)

    def polylines(name):
        return ''.join(
            '<polyline class="llr-path llr-path-%s" points="%s"/>' % (
                name, ' '.join('%.2f,%.2f' % (p['x'], p['y']) for p in seg))
            for seg in segments[name])

    grid = []
    for v in (y_max, 0.0, y_min):
        grid.append('<line class="llr-grid" x1="%d" y1="%.2f" x2="%d" y2="%.2f"/>' % (
            L, sy(v), width - R, sy(v)))
    for v in (x_max / 4.0, x_max / 2.0, 3.0 * x_max / 4.0):
        grid.append('<line class="llr-grid" x1="%.2f" y1="%d" x2="%.2f" y2="%d"/>' % (
            sx(v), T, sx(v), height - B))

    guides = []
    for v, name in ((test.lowerllr, 'llr-bound'), (0.0, 'llr-zero'), (test.upperllr, 'llr-bound')):
        guides.append('<line class="%s" x1="%d" y1="%.2f" x2="%d" y2="%.2f"/>' % (
            name, L, sy(v), width - R, sy(v)))
        if name == 'llr-bound':
            guides.append('<text class="llr-bound-label" x="%d" y="%.2f">%+.2f</text>' % (
                L + 4, sy(v) + (11.0 if v > 0 else -3.5), v))

    last      = points[-1]
    last_band = band(last)
    clip_id   = 'llr-reveal-%d' % (test.id)

    halo = '' if test.finished else (
        '<circle class="llr-endpoint-halo llr-fill-%s" cx="%.2f" cy="%.2f" r="2.8"/>' % (
            last_band, last['x'], last['y']))

    return mark_safe((
        '<div class="llr-history-widget" data-history="%s">'
          '<div class="llr-history-chart">'
            '<div class="llr-history-yaxis"><div>%+.2f</div><div>0.00</div><div>%+.2f</div></div>'
            '<div class="llr-history-main">'
              '<div class="llr-history-plot">'
                '<svg class="llr-history-graph" viewBox="0 0 %d %d" preserveAspectRatio="none" role="img" aria-label="%s">'
                  '<defs><clipPath id="%s"><rect class="llr-reveal" x="0" y="0" width="%d" height="%d"/></clipPath></defs>'
                  '<rect class="llr-bg" x="0" y="0" width="%d" height="%d"/>'
                  '%s%s'
                  '<g clip-path="url(#%s)">%s%s%s</g>'
                  '<g class="llr-endpoint-grp">%s'
                    '<circle class="llr-endpoint llr-fill-%s" cx="%.2f" cy="%.2f" r="2.8"/>'
                  '</g>'
                  '<line class="llr-hover-line" x1="%.2f" y1="%d" x2="%.2f" y2="%d"/>'
                  '<circle class="llr-hover-point" cx="%.2f" cy="%.2f" r="3.2"/>'
                  '<rect class="llr-hitbox" x="0" y="0" width="%d" height="%d"/>'
                '</svg>'
                '<div class="llr-history-tooltip"></div>'
              '</div>'
              '<div class="llr-history-xaxis"><div>0</div><div>%s</div><div>%s games</div></div>'
            '</div>'
          '</div>'
        '</div>'
    ) % (
        html.escape(json.dumps(points, separators=(',', ':'))),
        y_max, y_min,
        width, height,
        html.escape('LLR %.2f after %d games' % (test.currentllr, test.games)),
        clip_id, width, height,
        width, height,
        ''.join(grid), ''.join(guides),
        clip_id, polylines('pos'), polylines('yellow'), polylines('neg'),
        halo, last_band, last['x'], last['y'],
        last['x'], T, last['x'], height - B,
        last['x'], last['y'],
        width, height,
        insertCommas(int(round(x_max / 2.0))), insertCommas(x_max),
    ))

register.filter('llr_history_graph', llr_history_graph)


## Stat Blocks, laid out as a labelled table
##
## Same numbers as longStatBlock, but with the label in its own gutter and
## each figure annotated with what it actually is, so the block
## reads without having to remember the column order. Values are white,
## groupings and units grey, labels teal. The copy buttons read innerText,
## so what lands on the clipboard is exactly what is on screen.

PENTA_MARKS = ['\u207b\u00b2', '\u207b\u00b9', '\u2070', '\u207a\u00b9', '\u207a\u00b2']

def _sb(css_class, text):
    return '<span class="%s">%s</span>' % (css_class, html.escape(text))

def _sb_row(label, body):
    return _sb('sb-label', '%-5s' % (label)) + '  ' + body

def longStatBlockHTML(test):

    assert test.test_mode != 'SPSA'

    lines = []

    if test.test_mode == 'SPRT':
        lines.append(_sb_row('LLR',
            _sb('sb-value', '%+0.2f' % (test.currentllr))
          + _sb('sb-dim'  , '  (%+0.2f, %+0.2f)' % (test.lowerllr, test.upperllr))
          + _sb('sb-unit' , ' bounds')
          + _sb('sb-dim'  , '  [%0.2f, %0.2f]' % (test.elolower, test.eloupper))
          + _sb('sb-unit' , ' elo')))

    lower, elo, upper = OpenBench.stats.Elo(test.results())

    lines.append(_sb_row('ELO',
        _sb('sb-value', '%+0.2f' % (elo))
      + _sb('sb-dim'  , ' \u00b1 ')
      + _sb('sb-value', '%0.2f' % (max(upper - elo, elo - lower)))
      + _sb('sb-dim'  , '  (%+0.2f, %+0.2f)' % (lower, upper))
      + _sb('sb-unit' , ' 95%')))

    threads     = int(OpenBench.utils.extract_option(test.dev_options, 'Threads'))
    hashmb      = int(OpenBench.utils.extract_option(test.dev_options, 'Hash'))
    timecontrol = test.dev_time_control + ['s', '']['=' in test.dev_time_control]

    lines.append(_sb_row('CONF',
        _sb('sb-value', timecontrol)
      + _sb('sb-dim'  , '  \u00b7  ')
      + _sb('sb-value', '%d' % (threads))
      + _sb('sb-unit' , ' thread' + ('s' if threads != 1 else ''))
      + _sb('sb-dim'  , '  \u00b7  ')
      + _sb('sb-value', '%d' % (hashmb))
      + _sb('sb-unit' , ' mb hash')))

    games, wins, losses, draws = test.as_nwld()
    share = lambda n : (100.0 * n / games) if games else 0.0

    counts = ''
    for name, value in (('w', wins), ('d', draws), ('l', losses)):
        if counts: counts += _sb('sb-dim', '  ')
        counts += (_sb('sb-dim'  , '%0.1f%% ' % (share(value)))
                 + _sb('sb-value', insertCommas(value))
                 + _sb('sb-unit' , name))

    lines.append(_sb_row('GAMES',
        _sb('sb-value', insertCommas(games))
      + _sb('sb-dim'  , '  (') + counts + _sb('sb-dim', ')')))

    if test.use_penta:
        penta = _sb('sb-dim', '[')
        for i, value in enumerate(test.as_penta()):
            if i: penta += _sb('sb-dim', '  ')
            penta += _sb('sb-value', insertCommas(value)) + _sb('sb-unit', PENTA_MARKS[i])
        lines.append(_sb_row('PENTA', penta + _sb('sb-dim', ']')))

    return mark_safe('\n'.join(lines))

register.filter('longStatBlockHTML', longStatBlockHTML)
