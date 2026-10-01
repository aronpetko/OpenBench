/* Hover readout for the server-rendered LLR history graph.
 *
 * The SVG already carries the plotted geometry; all this adds is a crosshair
 * and a tooltip that snaps to the nearest sample, biased towards local peaks
 * so the interesting turning points are easy to land on. */

function init_llr_history_widgets() {

    document.querySelectorAll('.llr-history-widget').forEach(function(widget) {

        var history = JSON.parse(widget.dataset.history || '[]');
        if (!history.length) return;

        var svg    = widget.querySelector('.llr-history-graph');
        var line   = widget.querySelector('.llr-hover-line');
        var dot    = widget.querySelector('.llr-hover-point');
        var tip    = widget.querySelector('.llr-history-tooltip');
        var hitbox = widget.querySelector('.llr-hitbox');
        var vb     = svg.viewBox.baseVal;

        // Local minima and maxima, which we snap to when close enough
        var peaks = {};
        for (var i = 1; i < history.length - 1; i++) {
            var p = history[i - 1].l, c = history[i].l, n = history[i + 1].l;
            if ((c > p && c > n) || (c < p && c < n)) peaks[history[i].g] = true;
        }

        function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

        function show(point) {

            // Rendered server-side, off the same smoothed LLR the line's
            // gradient is coloured from
            var name = point.b;

            line.setAttribute('x1', point.x);
            line.setAttribute('x2', point.x);
            dot.setAttribute('cx', point.x);
            dot.setAttribute('cy', point.y);

            dot.classList.toggle('pos',    name === 'pos');
            dot.classList.toggle('yellow', name === 'yellow');
            dot.classList.toggle('neg',    name === 'neg');

            line.classList.add('active');
            dot.classList.add('active');

            tip.textContent = point.g.toLocaleString() + ' games   LLR ' + point.l.toFixed(2);
            tip.classList.add('active');

            var rect = svg.getBoundingClientRect();
            var px   = (point.x / vb.width ) * rect.width;
            var py   = (point.y / vb.height) * rect.height;

            tip.style.left = clamp(px + 10, 6, rect.width  - tip.offsetWidth  - 6) + 'px';
            tip.style.top  = clamp(py - tip.offsetHeight - 8, 4, rect.height - tip.offsetHeight - 4) + 'px';
        }

        function hide() {
            line.classList.remove('active');
            dot.classList.remove('active', 'pos', 'yellow', 'neg');
            tip.classList.remove('active');
        }

        function nearest(clientX) {

            var rect = svg.getBoundingClientRect();
            var lx   = ((clientX - rect.left) / rect.width) * vb.width;

            var best = history[0], best_dist = Math.abs(best.x - lx);
            var peak = null, peak_dist = Infinity;

            for (var i = 0; i < history.length; i++) {
                var dist = Math.abs(history[i].x - lx);
                if (dist < best_dist) { best = history[i]; best_dist = dist; }
                if (peaks[history[i].g] && dist < peak_dist) { peak = history[i]; peak_dist = dist; }
            }

            return (peak && peak_dist <= 5) ? peak : best;
        }

        hitbox.addEventListener('mouseenter', function(e) { show(nearest(e.clientX)); });
        hitbox.addEventListener('mousemove',  function(e) { show(nearest(e.clientX)); });
        hitbox.addEventListener('mouseleave', hide);
    });
}
