/* HaosuNaki responsive SVG visuals. No dependencies; data is never inserted as HTML. */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const C = { paper: '#FAF8F4', ink: '#282623', muted: '#68635D', line: '#D7D0C6', cobalt: '#244AC7', coral: '#C45C46', berry: '#A33C62', lake: '#2E7F9E', lavender: '#7668A6', tea: '#765B50' };
  const PALETTE = ['cobalt', 'coral', 'berry', 'lake', 'lavender', 'tea'];
  const KINDS = ['bar', 'line', 'scatter', 'histogram', 'stacked', 'waterfall'];
  const states = new WeakMap();
  let sequence = 0;
  const bodyFont = '"JetBrains Mono", "PingFang SC", "Noto Sans SC", sans-serif';
  const numberFont = 'Georgia, "Lora", serif';
  const canvas = document.createElement('canvas');
  const measure = canvas.getContext('2d');
  const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(entries => {
    entries.forEach(entry => {
      const state = states.get(entry.target);
      if (state && Math.abs(entry.contentRect.width - state.width) > 0.5) draw(state);
    });
  }) : null;

  function fail(message) { throw new Error(message); }
  function assert(ok, message) { if (!ok) fail(message); }
  function num(value, name) { assert(typeof value === 'number' && Number.isFinite(value), name + '必须是有限数值。'); return value; }
  function str(value, name) { assert(typeof value === 'string' && value.trim(), name + '必须是非空文字。'); return value; }
  function list(value, name) { assert(Array.isArray(value) && value.length, name + '必须是非空数组。'); return value; }
  function object(value, name) { assert(value && typeof value === 'object' && !Array.isArray(value), name + '必须是对象。'); return value; }
  function unique(items, name) { const ids = new Set(); items.forEach(item => { str(item.id, name + ' id'); assert(!ids.has(item.id), name + ' id 不得重复：' + item.id); ids.add(item.id); }); }
  function sum(values) { const total = values.reduce((a, b) => a + b, 0); assert(Number.isFinite(total), '数值合计超出可表示范围。'); return total; }
  function nearly(a, b) { return Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(a), Math.abs(b)); }
  function fmt(n) { if (n === 0) return '0'; if (Math.abs(n) >= 1e8 || Math.abs(n) < 0.001) return n.toExponential(2); return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 4 }).format(n); }
  function signed(n) { return (n >= 0 ? '+' : '−') + fmt(Math.abs(n)); }
  function element(name, attrs, text, parent) {
    const el = document.createElement(name);
    Object.entries(attrs || {}).forEach(([key, value]) => el.setAttribute(key, String(value)));
    if (text !== undefined) el.textContent = String(text);
    if (parent) parent.appendChild(el);
    return el;
  }
  function svgEl(name, attrs, text, parent) {
    const el = document.createElementNS(NS, name);
    Object.entries(attrs || {}).forEach(([key, value]) => el.setAttribute(key, String(value)));
    if (text !== undefined) el.textContent = String(text);
    if (parent) parent.appendChild(el);
    return el;
  }
  function text(svg, value, x, y, options) {
    const opts = options || {};
    return svgEl('text', { x, y, fill: opts.fill || C.ink, 'font-size': opts.size || 16, 'font-family': opts.numeric ? numberFont : bodyFont, 'text-anchor': opts.anchor || 'start', ...opts.attrs }, value, svg);
  }
  function wrapped(svg, value, x, y, width, options) {
    const opts = options || {};
    const size = opts.size || 16;
    if (measure) measure.font = size + 'px ' + (opts.numeric ? numberFont : bodyFont);
    const lines = []; let current = '';
    Array.from(String(value)).forEach(char => {
      const trial = current + char;
      const length = measure ? measure.measureText(trial).width : Array.from(trial).length * size;
      if (char === '\n' || (length > width && current)) { lines.push(current); current = char === '\n' ? '' : char; }
      else current = trial;
    });
    lines.push(current);
    lines.forEach((line, index) => text(svg, line, x, y + index * 24, opts));
    return lines.length * 24;
  }
  function mixedWrapped(svg, parts, x, y, width) {
    let row = text(svg, '', x, y), span = null, used = 0, rowIndex = 0, previousNumeric = null;
    parts.forEach(part => {
      const numeric = part.numeric === true, font = numeric ? numberFont : bodyFont;
      if (measure) measure.font = '16px ' + font;
      Array.from(String(part.value)).forEach(char => {
        const charWidth = measure ? measure.measureText(char).width : numeric ? 9 : 16;
        if (char === '\n' || (used + charWidth > width && used > 0)) {
          row = text(svg, '', x, y + (++rowIndex) * 24); span = null; previousNumeric = null; used = 0;
          if (char === '\n') return;
        }
        if (!span || previousNumeric !== numeric) {
          span = svgEl('tspan', { 'font-family': font }, '', row); previousNumeric = numeric;
        }
        span.textContent += char; used += charWidth;
      });
    });
    return (rowIndex + 1) * 24;
  }
  function line(svg, x1, y1, x2, y2, color, width, dash) {
    return svgEl('line', { x1, y1, x2, y2, stroke: color || C.line, 'stroke-width': width || 1, ...(dash ? { 'stroke-dasharray': dash } : {}) }, undefined, svg);
  }
  function rect(svg, x, y, width, height, fill) { return svgEl('rect', { x, y, width: Math.max(0, width), height: Math.max(0, height), fill }, undefined, svg); }
  function symbol(svg, x, y, color, shape, size) {
    const r = size || 5;
    if (shape === 'coral') return rect(svg, x - r, y - r, r * 2, r * 2, color);
    if (shape === 'berry') return svgEl('path', { d: 'M ' + x + ' ' + (y - r - 1) + ' L ' + (x + r + 1) + ' ' + (y + r) + ' L ' + (x - r - 1) + ' ' + (y + r) + ' Z', fill: color }, undefined, svg);
    if (shape === 'lake') return svgEl('path', { d: 'M ' + x + ' ' + (y - r - 1) + ' L ' + (x + r + 1) + ' ' + y + ' L ' + x + ' ' + (y + r + 1) + ' L ' + (x - r - 1) + ' ' + y + ' Z', fill: color }, undefined, svg);
    if (shape === 'lavender' || shape === 'tea') {
      const a = r * 0.38;
      const points = [[-a,-r],[a,-r],[a,-a],[r,-a],[r,a],[a,a],[a,r],[-a,r],[-a,a],[-r,a],[-r,-a],[-a,-a]];
      return svgEl('path', { d: points.map((p, i) => (i ? ' L ' : 'M ') + (x + p[0]) + ' ' + (y + p[1])).join('') + ' Z', fill: color, ...(shape === 'tea' ? { transform: 'rotate(45 ' + x + ' ' + y + ')' } : {}) }, undefined, svg);
    }
    return svgEl('circle', { cx: x, cy: y, r, fill: color }, undefined, svg);
  }
  function extent(values, zero) {
    let min = Math.min.apply(null, values), max = Math.max.apply(null, values);
    if (zero) { min = Math.min(0, min); max = Math.max(0, max); }
    if (min === max) { if (zero) max = min + 1; else { const pad = Math.abs(min) * 0.1 || 1; min -= pad; max += pad; } }
    assert(Number.isFinite(max - min) && max > min, '数据跨度超出可表示范围。');
    return [min, max];
  }
  function scale(domain, a, b) { return value => a + ((value - domain[0]) / (domain[1] - domain[0])) * (b - a); }
  function ticks(domain, count) { return Array.from({ length: count }, (_, i) => domain[0] + (domain[1] - domain[0]) * i / (count - 1)); }
  function color(model, item) {
    if (model.mode === 'single') return C.cobalt;
    if (model.mode === 'focus') return item.id === model.focusId ? C.cobalt : C.muted;
    return C[item.color];
  }
  function mode(model, items) {
    unique(items, '颜色对象');
    items.forEach(item => str(item.label, '对象 label'));
    if (model.mode === 'focus') {
      str(model.focusId, 'focusId');
      assert(items.some(item => item.id === model.focusId), 'focusId 必须对应本图明确的对象 id。');
    } else {
      assert(model.focusId === undefined, '仅 focus 模式可设置 focusId。');
    }
    if (model.mode === 'category') {
      assert(items.length <= 6, 'category 最多支持六个类别；更多类别请拆图或使用表格。');
      const used = new Set();
      items.forEach(item => {
        assert(PALETTE.includes(item.color), '类别 ' + item.id + ' 必须明确 color：cobalt、coral、berry、lake、lavender 或 tea。');
        assert(!used.has(item.color), '同一分类图内不同类别不得共用颜色。'); used.add(item.color);
      });
      model.categories = items;
    }
  }
  function xValue(value, type) {
    if (type === 'number') return num(value, 'x');
    str(value, '时间 x');
    assert(/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))?$/.test(value), '时间 x 使用 YYYY-MM-DD 或带时区的 ISO 时间。');
    const parsed = Date.parse(value);
    assert(Number.isFinite(parsed), '时间 x 无效：' + value);
    const datePart = value.slice(0, 10);
    const date = new Date(Date.parse(datePart + 'T00:00:00Z'));
    assert(date.toISOString().slice(0, 10) === datePart, '时间 x 的日期无效：' + value);
    return parsed;
  }
  function validate(raw) {
    const model = object(raw, '图表 JSON');
    assert(KINDS.includes(model.kind), 'kind 仅支持 bar、line、scatter、histogram、stacked、waterfall。');
    str(model.title, 'title'); str(model.unit, 'unit');
    assert(['single', 'focus', 'category'].includes(model.mode), '必须明确 mode：single、focus 或 category。');
    if (model.summary !== undefined) str(model.summary, 'summary');
    model.categories = [];
    if (model.kind === 'bar') {
      list(model.data, 'data'); unique(model.data, 'data');
      model.data.forEach(item => { str(item.label, 'label'); num(item.value, 'value'); });
      if (model.mode === 'single') { object(model.series, 'single 模式 series'); str(model.series.id, 'series.id'); str(model.series.label, 'series.label'); }
      mode(model, model.data);
    } else if (model.kind === 'line' || model.kind === 'scatter') {
      if (model.kind === 'line') assert(['number', 'time'].includes(model.xType), 'line 必须明确 xType：number 或 time。');
      str(model.xUnit, 'xUnit');
      list(model.series, 'series'); mode(model, model.series);
      if (model.mode === 'single') assert(model.series.length === 1, 'single 只允许一个测量序列。');
      model.series.forEach(series => {
        list(series.points, 'points');
        let previous = -Infinity, real = 0;
        if (model.kind === 'scatter') unique(series.points, '散点');
        series.points.forEach(point => {
          point.px = model.kind === 'line' ? xValue(point.x, model.xType) : num(point.x, 'x');
          if (model.kind === 'line') { assert(point.px > previous, '折线各序列 x 必须严格递增且无重复；不会自动排序。'); previous = point.px; }
          if (model.kind === 'scatter') { str(point.label, '散点 label'); num(point.y, 'y'); real++; }
          else if (point.y !== null) { num(point.y, 'y'); real++; }
        });
        assert(real > 0, '每个序列至少提供一个非空数值。');
      });
    } else if (model.kind === 'histogram') {
      assert(model.mode === 'single', '直方图使用 single：所有分箱属于同一频数序列。');
      assert(model.focusId === undefined, '直方图不使用 focusId。');
      str(model.xUnit, '原始数值 xUnit');
      assert(model.unit === '频数' || model.unit === '次' || model.unit === '个', '直方图 unit 必须为频数、次或个，不能使用密度或百分比。');
      list(model.values, 'values').forEach(value => num(value, '原始值'));
      list(model.binEdges, 'binEdges');
      assert(model.binEdges.length >= 2, '至少提供两个分箱边界。');
      model.binEdges.forEach(edge => num(edge, '分箱边界'));
      const gap = model.binEdges[1] - model.binEdges[0];
      assert(gap > 0 && Number.isFinite(gap), '分箱边界必须递增。');
      model.binEdges.slice(1).forEach((edge, index) => assert(nearly(edge - model.binEdges[index], gap), '仅支持等宽分箱；不得将不等宽频数画成等宽柱。'));
      const first = model.binEdges[0], last = model.binEdges[model.binEdges.length - 1];
      model.counts = Array(model.binEdges.length - 1).fill(0);
      model.values.forEach(value => {
        assert(value >= first && value <= last, '存在超出分箱边界的原始值：' + value);
        let index = model.binEdges.length - 2;
        if (value < last) index = model.binEdges.findIndex((edge, i) => i > 0 && value < edge) - 1;
        model.counts[index]++;
      });
    } else if (model.kind === 'stacked') {
      assert(model.additive === true, '堆积图必须明确 additive: true，确认各部分可加总且口径一致。');
      assert(['absolute', 'percent'].includes(model.stackMode), 'stackMode 必须明确 absolute 或 percent。');
      list(model.series, 'series'); mode(model, model.series);
      if (model.mode === 'single') assert(model.series.length === 1, 'single 堆积图只能有一个测量序列。');
      list(model.data, 'data'); unique(model.data, 'data');
      const ids = model.series.map(series => series.id);
      model.data.forEach(row => {
        str(row.label, 'label'); object(row.values, 'values');
        assert(Object.keys(row.values).length === ids.length && Object.keys(row.values).every(id => ids.includes(id)), '堆积 values 必须完整且仅包含声明的系列 id。');
        row.total = sum(ids.map(id => { const v = num(row.values[id], id); assert(v >= 0, '堆积图不接受负值。'); return v; }));
        if (model.stackMode === 'percent') assert(row.total > 0, '占比堆积图不能使用总和为 0 的行。');
      });
    } else {
      assert(model.mode === 'single', '瀑布图使用 single，表示同一余额指标的变化。');
      assert(model.focusId === undefined, '瀑布图不使用 focusId。');
      object(model.start, 'start'); object(model.end, 'end'); list(model.contributions, 'contributions');
      const all = [model.start].concat(model.contributions, [model.end]); unique(all, '瀑布步骤');
      all.forEach(row => { str(row.label, 'label'); num(row.value, 'value'); });
      let running = model.start.value;
      model.contributions.forEach(row => { row.from = running; running = sum([running, row.value]); row.to = running; });
      assert(nearly(running, model.end.value), '瀑布核对失败：期初 + 各项变化 = ' + fmt(running) + '，但显式期末为 ' + fmt(model.end.value) + '。');
    }
    return model;
  }
  function horizontalAxis(svg, domain, x, top, bottom, width, unit, bands) {
    let values = ticks(domain, width < 360 ? 3 : 5);
    if (domain[0] < 0 && domain[1] > 0) {
      values = values.filter(value => Math.abs(x(value) - x(0)) >= 44);
      values.push(0);
    }
    values.forEach(value => {
      const p = x(value);
      (bands || [[top, bottom]]).forEach(band => line(svg, p, band[0], p, band[1], value === 0 ? C.muted : C.line, value === 0 ? 2 : 1));
      text(svg, fmt(value), p, bottom + 23, { numeric: true, size: 14, anchor: p < 24 ? 'start' : p > width - 24 ? 'end' : 'middle' });
    });
    return wrapped(svg, unit, 0, bottom + 50, width, { size: 14, fill: C.muted });
  }
  function cartesian(svg, width, xd, yd, xFormatter, xUnit, yUnit) {
    const yTexts = ticks(yd, 5).map(fmt);
    const left = Math.min(width * 0.4, Math.max(42, Math.max.apply(null, yTexts.map(s => s.length)) * 8 + 14));
    const right = width - 14, top = 42, bottom = 254;
    const x = scale(xd, left, right), y = scale(yd, bottom, top);
    ticks(yd, 5).forEach(value => { const p = y(value); line(svg, left, p, right, p); text(svg, fmt(value), left - 9, p + 5, { numeric: true, size: 14, anchor: 'end' }); });
    line(svg, left, top, left, bottom, C.muted); line(svg, left, bottom, right, bottom, C.muted);
    ticks(xd, width < 430 ? 2 : 4).forEach((value, index, arr) => {
      const p = x(value); line(svg, p, bottom, p, bottom + 6, C.muted);
      text(svg, xFormatter(value), p, bottom + 25, { size: 14, numeric: true, anchor: index === 0 ? 'start' : index === arr.length - 1 ? 'end' : 'middle' });
    });
    wrapped(svg, yUnit, 0, 18, width, { size: 14, fill: C.muted });
    const extra = wrapped(svg, xUnit, left, bottom + 52, width - left, { size: 14, fill: C.muted });
    return { x, y, left, right, top, bottom, height: bottom + 54 + extra };
  }
  function drawBar(svg, model, width) {
    const domain = extent(model.data.map(row => row.value), true), x = scale(domain, 8, width - 8);
    let y = 18;
    const bars = [];
    model.data.forEach(row => {
      y += wrapped(svg, row.label, 0, y, width);
      y += mixedWrapped(svg, [{ value: fmt(row.value), numeric: true }, { value: ' ' + model.unit }], 0, y, width);
      bars.push({ row, y }); y += 42;
    });
    const unitHeight = horizontalAxis(svg, domain, x, 8, y - 18, width, model.unit, bars.map(bar => [bar.y - 3, bar.y + 24]));
    bars.forEach(({ row, y: by }) => {
      const a = x(0), b = x(row.value);
      if (row.value === 0) line(svg, a, by - 3, a, by + 23, color(model, row), 2);
      else rect(svg, Math.min(a, b), by, Math.abs(b - a), 20, color(model, row));
    });
    return y + 45 + unitHeight;
  }
  function drawXY(svg, model, width) {
    const all = model.series.flatMap(series => series.points), real = all.filter(point => point.y !== null);
    const time = model.kind === 'line' && model.xType === 'time';
    const xs = all.map(point => point.px);
    const xd = time && xs.every(value => value === xs[0]) ? [xs[0] - 86400000, xs[0] + 86400000] : extent(xs, false);
    const yd = extent(real.map(point => point.y), false);
    const formatX = value => time ? new Date(value).toISOString().slice(0, 10) : fmt(value);
    const axes = cartesian(svg, width, xd, yd, formatX, model.xUnit + (time ? '（UTC）' : ''), model.unit);
    model.series.forEach(series => {
      const fill = color(model, series), shape = model.mode === 'category' ? series.color : 'cobalt';
      if (model.kind === 'line') {
        let path = '', open = false;
        series.points.forEach(point => {
          if (point.y === null) { open = false; return; }
          path += (open ? ' L ' : ' M ') + axes.x(point.px) + ' ' + axes.y(point.y); open = true;
        });
        svgEl('path', { d: path, fill: 'none', stroke: fill, 'stroke-width': 2 }, undefined, svg);
      }
      series.points.forEach(point => { if (point.y !== null) symbol(svg, axes.x(point.px), axes.y(point.y), fill, shape, model.kind === 'scatter' ? 6 : 4); });
    });
    return axes.height;
  }
  function drawHistogram(svg, model, width) {
    const domain = [model.binEdges[0], model.binEdges[model.binEdges.length - 1]];
    const max = Math.max(1, ...model.counts);
    const axes = cartesian(svg, width, domain, [0, max], fmt, model.xUnit, model.unit);
    model.counts.forEach((count, i) => {
      const a = axes.x(model.binEdges[i]), b = axes.x(model.binEdges[i + 1]);
      rect(svg, a + 0.5, axes.y(count), b - a - 1, axes.bottom - axes.y(count), C.cobalt);
      if (b - a >= 32) text(svg, fmt(count), (a + b) / 2, Math.max(axes.top + 18, axes.y(count) - 7), { numeric: true, anchor: 'middle', fill: count === max ? C.paper : C.ink });
    });
    return axes.height;
  }
  function drawStacked(svg, model, width) {
    const percent = model.stackMode === 'percent', domain = [0, percent ? 100 : Math.max(1, ...model.data.map(row => row.total))];
    const x = scale(domain, 8, width - 8), bars = []; let y = 18;
    model.data.forEach(row => {
      y += wrapped(svg, row.label, 0, y, width);
      y += mixedWrapped(svg, [{ value: '合计 ' }, { value: fmt(row.total), numeric: true }, { value: ' ' + model.unit }], 0, y, width);
      bars.push({ row, y }); y += 34;
      model.series.forEach(series => {
        const details = [{ value: series.label + ' ' }, { value: fmt(row.values[series.id]), numeric: true }, { value: ' ' + model.unit }];
        if (percent) details.push({ value: '（' }, { value: fmt(row.values[series.id] / row.total * 100) + '%', numeric: true }, { value: '）' });
        y += mixedWrapped(svg, details, 0, y, width);
      });
      y += 20;
    });
    const unitHeight = horizontalAxis(svg, domain, x, 8, y - 24, width, percent ? '占比（%）；每行按自身总和归一化' : model.unit, bars.map(bar => [bar.y - 3, bar.y + 25]));
    bars.forEach(({ row, y: by }) => {
      let from = 0;
      model.series.forEach(series => {
        const amount = percent ? row.values[series.id] / row.total * 100 : row.values[series.id];
        rect(svg, x(from), by, x(from + amount) - x(from), 22, color(model, series)); from += amount;
      });
    });
    return y + 48 + unitHeight;
  }
  function drawWaterfall(svg, model, width) {
    const rows = [{ ...model.start, from: 0, to: model.start.value, total: true }].concat(model.contributions, [{ ...model.end, from: 0, to: model.end.value, total: true }]);
    const domain = extent(rows.flatMap(row => [row.from, row.to]), true), x = scale(domain, 8, width - 8);
    const bars = []; let y = 18;
    rows.forEach((row, i) => {
      y += wrapped(svg, row.label, 0, y, width);
      y += mixedWrapped(svg, [{ value: row.total ? fmt(row.value) : signed(row.value), numeric: true }, { value: ' ' + model.unit }], 0, y, width);
      bars.push({ row, y, i }); y += 42;
    });
    const unitHeight = horizontalAxis(svg, domain, x, 8, y - 18, width, model.unit, bars.map(bar => [bar.y - 3, bar.y + 24]));
    bars.forEach(({ row, y: by, i }) => {
      const a = x(row.from), b = x(row.to), fill = row.total ? C.ink : row.value === 0 ? C.muted : row.value > 0 ? C.coral : C.cobalt;
      if (a === b) line(svg, a, by - 2, a, by + 22, fill, 2); else rect(svg, Math.min(a, b), by, Math.abs(b - a), 20, fill);
      if (i < bars.length - 1) line(svg, b, by + 22, b, bars[i + 1].y - 3, C.muted, 1, '3 4');
    });
    return y + 45 + unitHeight;
  }
  function tableData(model) {
    if (model.kind === 'bar') return [{ title: '原始数值', heads: ['对象 ID', '对象', '数值（' + model.unit + '）'], rows: model.data.map(row => [row.id, row.label, row.value]), numeric: [2] }];
    if (model.kind === 'line' || model.kind === 'scatter') return [{ title: '原始观测', heads: model.kind === 'line' ? ['序列 ID', '序列', 'x（' + model.xUnit + '）', 'y（' + model.unit + '）'] : ['序列 ID', '序列', '点 ID', '对象', 'x（' + model.xUnit + '）', 'y（' + model.unit + '）'], rows: model.series.flatMap(series => series.points.map(point => model.kind === 'line' ? [series.id, series.label, point.x, point.y === null ? '缺失（断点）' : point.y] : [series.id, series.label, point.id, point.label, point.x, point.y])), numeric: model.kind === 'line' ? [3] : [4, 5] }];
    if (model.kind === 'histogram') return [
      { title: '原始观测', heads: ['序号', '原始值（' + model.xUnit + '）'], rows: model.values.map((value, i) => [i + 1, value]), numeric: [1] },
      { title: '分箱统计（最后一箱含右边界）', heads: ['区间（' + model.xUnit + '）', '频数'], rows: model.counts.map((count, i) => ['[' + model.binEdges[i] + ', ' + model.binEdges[i + 1] + (i === model.counts.length - 1 ? ']' : ')'), count]), numeric: [1] }
    ];
    if (model.kind === 'stacked') return [{ title: '原始分项与合计', heads: ['对象 ID', '对象'].concat(model.series.map(series => series.label + '（' + model.unit + '）'), ['合计（' + model.unit + '）']), rows: model.data.map(row => [row.id, row.label].concat(model.series.map(series => row.values[series.id]), [row.total])), numeric: model.series.map((_, i) => i + 2).concat([model.series.length + 2]) }];
    return [{ title: '瀑布原始数值与余额核对', heads: ['步骤 ID', '步骤', '类型', '输入（' + model.unit + '）', '步骤后余额（' + model.unit + '）'], rows: [[model.start.id, model.start.label, '期初', model.start.value, model.start.value]].concat(model.contributions.map(row => [row.id, row.label, '变化', signed(row.value), row.to]), [[model.end.id, model.end.label, '期末', model.end.value, model.end.value]]), numeric: [3, 4] }];
  }
  function tables(state) {
    const opened = state.host.querySelector('details.hn-data-table')?.open || false;
    const details = element('details', { class: 'hn-data-table' }); details.open = opened;
    element('summary', {}, '查看原始数据与计算口径', details);
    element('p', { class: 'hn-table-hint' }, '表格保留全部字段；窄屏可在表格内左右滚动。', details);
    tableData(state.model).forEach(data => {
      const scroll = element('div', { class: 'hn-table-scroll', tabindex: '0', role: 'region', 'aria-label': state.model.title + '：' + data.title }, undefined, details);
      const table = element('table', {}, undefined, scroll);
      element('caption', {}, data.title, table);
      const head = element('tr', {}, undefined, element('thead', {}, undefined, table));
      data.heads.forEach((value, index) => element('th', { scope: 'col', ...(data.numeric.includes(index) ? { class: 'hn-numeric' } : {}) }, value, head));
      const body = element('tbody', {}, undefined, table);
      data.rows.forEach(row => {
        const tr = element('tr', {}, undefined, body);
        row.forEach((value, index) => {
          const displayNumber = typeof value === 'number' || (typeof value === 'string' && /^[+−-]?\d[\d,]*(?:\.\d+)?(?:e[+-]?\d+)?$/i.test(value));
          element(index === 0 ? 'th' : 'td', { ...(index === 0 ? { scope: 'row' } : {}), ...(data.numeric.includes(index) ? { class: 'hn-numeric' + (displayNumber ? ' hn-number' : '') } : {}) }, value, tr);
        });
      });
    });
    return details;
  }
  function legend(model, host) {
    const entries = model.kind === 'waterfall' ? [{ label: '期初／期末', fill: C.ink }, { label: '+ 增加', fill: C.coral }, { label: '− 减少', fill: C.cobalt }, { label: '0 无变化', fill: C.muted }] : model.kind === 'histogram' ? [{ label: '同一组观测的频数', fill: C.cobalt }] : model.kind === 'bar' && model.mode === 'single' ? [{ label: model.series.label + '（所有观测同等）', fill: C.cobalt }] : (model.kind === 'bar' ? model.data : model.series).map(item => ({ label: item.label + (model.mode === 'focus' && item.id === model.focusId ? '（明确重点）' : ''), fill: color(model, item), shape: model.mode === 'category' ? item.color : 'cobalt' }));
    const listEl = element('ul', { class: 'hn-legend', 'aria-label': '图例' }, undefined, host);
    entries.forEach(entry => {
      const li = element('li', {}, undefined, listEl);
      const swatch = element('span', { class: 'hn-swatch hn-shape-' + (entry.shape || 'cobalt'), 'aria-hidden': 'true' }, undefined, li);
      swatch.style.backgroundColor = entry.fill;
      element('span', {}, entry.label, li);
    });
  }
  function note(model) {
    if (model.kind === 'line') return '横轴按真实数值或时间间隔定位；空值保留为断点，不做平滑或插值。';
    if (model.kind === 'scatter') return '横轴：' + model.xUnit + '；纵轴：' + model.unit + '。每个点是一条观测，未绘制回归线；重合观测仍保留在数据表中。';
    if (model.kind === 'histogram') return '共 ' + model.values.length + ' 条原始观测；等宽分箱，左闭右开，最后一箱含右边界；纵轴为数量频数。';
    if (model.kind === 'stacked') return model.stackMode === 'percent' ? '占比模式：各行分别除以本行总和；原始值和总和完整保留。' : '绝对量模式：各部分非负、口径一致、可加总。';
    if (model.kind === 'waterfall') return '从上到下读取；钴蓝 − 表示减少，陶珊瑚 + 表示增加，中性灰表示零变化，深色表示期初／期末；颜色只编码方向，不表示好坏。期初 + 各项变化已核对等于显式期末。';
    return '所有条形共用含零基线；负值向零点左侧延伸。';
  }
  function error(state, message) {
    state.host.replaceChildren();
    element('p', { class: 'hn-visual-error', role: 'alert' }, '无法绘制图表：' + message, state.host);
    state.figure.setAttribute('data-hn-status', 'error');
  }
  function draw(state) {
    state.width = state.plot.getBoundingClientRect().width;
    if (state.error) { error(state, state.error); return; }
    if (state.width === 0) { state.figure.setAttribute('data-hn-status', 'deferred'); return; }
    if (state.width < 160) { error(state, '容器宽度不足 160px；请扩大图表容器。'); return; }
    try {
      const dataTable = tables(state), model = state.model, width = Math.floor(state.width);
      state.host.replaceChildren();
      if (model.summary) element('p', { class: 'hn-visual-summary' }, model.summary, state.host);
      legend(model, state.host);
      const svg = svgEl('svg', { xmlns: NS, width, role: 'img', 'aria-labelledby': state.id + '-title ' + state.id + '-desc', class: 'hn-svg' }, undefined, state.host);
      svgEl('title', { id: state.id + '-title' }, model.title, svg);
      svgEl('desc', { id: state.id + '-desc' }, (model.summary ? model.summary + ' ' : '') + '单位：' + model.unit + '。' + note(model) + '完整观测见图后可展开数据表。', svg);
      const height = model.kind === 'bar' ? drawBar(svg, model, width) : model.kind === 'line' || model.kind === 'scatter' ? drawXY(svg, model, width) : model.kind === 'histogram' ? drawHistogram(svg, model, width) : model.kind === 'stacked' ? drawStacked(svg, model, width) : drawWaterfall(svg, model, width);
      svg.setAttribute('height', height); svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
      element('p', { class: 'hn-visual-note' }, note(model), state.host);
      state.host.appendChild(dataTable);
      state.figure.setAttribute('data-hn-status', 'ready');
    } catch (err) { error(state, err.message); }
  }
  function renderAll(root) {
    const scope = root || document;
    const figures = Array.from(scope.querySelectorAll('figure.hn-visual'));
    if (scope.matches && scope.matches('figure.hn-visual')) figures.unshift(scope);
    const prepared = figures.map(figure => {
      let plot = figure.querySelector(':scope > .hn-plot');
      if (!plot) plot = element('div', { class: 'hn-plot' }, undefined, figure);
      let state = states.get(plot);
      if (!state) {
        const host = element('div', { class: 'hn-rendered' }, undefined, plot);
        state = { figure, plot, host, id: 'hn-visual-' + (++sequence), width: -1 };
        states.set(plot, state); if (observer) observer.observe(plot);
      }
      state.error = null;
      try {
        const scripts = figure.querySelectorAll(':scope > script.hn-data[type="application/json"]');
        assert(scripts.length === 1, '每个 figure 必须含一个直属的 application/json .hn-data。');
        state.model = validate(JSON.parse(scripts[0].textContent));
      } catch (err) { state.error = err instanceof SyntaxError ? 'JSON 格式无效，请检查引号、逗号和转义。' : err.message; }
      return state;
    });
    const registry = new Map();
    prepared.filter(state => !state.error).forEach(state => state.model.categories.forEach(item => {
      if (!registry.has(item.id)) registry.set(item.id, []);
      registry.get(item.id).push({ state, color: item.color });
    }));
    registry.forEach((entries, id) => {
      if (new Set(entries.map(entry => entry.color)).size > 1) entries.forEach(entry => { entry.state.error = '同一页面类别 id「' + id + '」的颜色映射不一致。'; });
    });
    prepared.forEach(draw);
    return { total: prepared.length, ready: prepared.filter(state => state.figure.getAttribute('data-hn-status') === 'ready').length, deferred: prepared.filter(state => state.figure.getAttribute('data-hn-status') === 'deferred').length, errors: prepared.filter(state => state.figure.getAttribute('data-hn-status') === 'error').length };
  }
  window.HaosuNakiVisuals = Object.freeze({ renderAll });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => renderAll(), { once: true }); else renderAll();
  if (!observer) window.addEventListener('resize', () => renderAll());
  window.addEventListener('beforeprint', () => renderAll());
  window.addEventListener('afterprint', () => renderAll());
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => renderAll());
})();
