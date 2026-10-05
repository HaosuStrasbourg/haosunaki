/* HaosuNaki v1.2 · Dependency-free, explicit-level box-and-line diagrams. */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const states = new WeakMap();
  const PALETTE = ['cobalt', 'coral', 'berry', 'lake', 'lavender', 'tea'];
  const kindNames = { flow: '流程图', architecture: '架构图', relationship: '关系图' };
  const typeNames = { process: '步骤', decision: '判断', external: '外部对象', group: '边界' };
  let sequence = 0;
  const fail = message => { throw new Error(message); };
  const nonempty = value => typeof value === 'string' && value.trim().length > 0;
  const element = (tag, className, text) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text != null) el.textContent = text;
    return el;
  };
  const svgElement = (tag, attrs) => {
    const el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(key => el.setAttribute(key, attrs[key]));
    return el;
  };

  function validate(input) {
    if (!input || typeof input !== 'object' || Array.isArray(input)) fail('图示数据须为 JSON 对象。');
    if (!['flow', 'architecture', 'relationship'].includes(input.kind)) fail('kind 须为 flow、architecture 或 relationship。');
    if (!nonempty(input.title)) fail('请提供 title。');
    if (!Array.isArray(input.nodes) || !input.nodes.length) fail('请提供非空 nodes。');
    if (!Array.isArray(input.edges)) fail('请明确提供 edges；无连线时写 []。');
    const byId = new Map();
    const categories = new Map();
    const nodes = input.nodes.map(raw => {
      if (!raw || !nonempty(raw.id) || raw.id !== raw.id.trim()) fail('每个节点必须有不含首尾空白的稳定 id。');
      if (byId.has(raw.id)) fail('重复节点 id：' + raw.id);
      if (!nonempty(raw.label)) fail('节点 ' + raw.id + ' 缺少 label。');
      const type = raw.type || 'process';
      if (!['process', 'decision', 'external', 'group'].includes(type)) fail('节点 ' + raw.id + ' 的 type 不支持。');
      if (raw.focus != null && typeof raw.focus !== 'boolean') fail('focus 须为 true 或 false。');
      if (raw.color != null && (!nonempty(raw.category) || !PALETTE.includes(raw.color))) fail('类别颜色必须同时指定 category 与 cobalt/coral/berry/lake/lavender/tea 之一。');
      if (raw.category != null && (!nonempty(raw.category) || !raw.color)) fail('category 需要明确的 color 映射。');
      if (raw.category) {
        if (categories.has(raw.category) && categories.get(raw.category) !== raw.color) fail('同一类别不能使用不同颜色：' + raw.category);
        categories.set(raw.category, raw.color);
      }
      const node = Object.assign({}, raw, { type });
      byId.set(node.id, node);
      return node;
    });
    if (categories.size > 6) fail('分类图最多同时使用六类；更多类别请拆图。');
    if (new Set(categories.values()).size !== categories.size) fail('同一分类图内不同类别不得共用颜色。');
    const groups = nodes.filter(node => node.type === 'group');
    const leaves = nodes.filter(node => node.type !== 'group');
    if (!leaves.length) fail('至少需要一个普通节点。');
    const focused = nodes.filter(node => node.focus);
    if (focused.length > 1) fail('一张图只突出一个明确重点；同等对象请用类别。');
    if (focused.length && categories.size) fail('请在单一重点与分类配色中选择一种语义。');
    if (groups.some(node => node.focus || node.category)) fail('边界保持中性色；重点或类别请标在成员节点上。');
    const membership = new Map();
    groups.forEach(group => {
      if (!Array.isArray(group.members) || !group.members.length) fail('边界 ' + group.id + ' 需要非空 members。');
      group.members.forEach(id => {
        if (!byId.has(id) || byId.get(id).type === 'group') fail('边界成员须为已声明的普通节点：' + id);
        if (membership.has(id)) fail('节点不能重复归属或嵌套边界：' + id);
        membership.set(id, group.id);
      });
    });
    if (!Array.isArray(input.levels) || !input.levels.length) fail('请用 levels 显式声明从上到下的层级；不会自动猜层级。');
    const placed = new Set();
    const levels = input.levels.map(row => {
      if (!Array.isArray(row) || !row.length) fail('levels 的每层须为非空 id 数组。');
      row.forEach(id => {
        if (!byId.has(id) || byId.get(id).type === 'group') fail('levels 中只能引用已声明的普通节点：' + id);
        if (placed.has(id)) fail('levels 重复引用节点：' + id);
        placed.add(id);
      });
      return row.slice();
    });
    if (placed.size !== leaves.length) fail('levels 必须且只能包含全部普通节点一次。');
    const edgeKeys = new Set();
    const edges = input.edges.map((raw, index) => {
      if (!raw || !byId.has(raw.from) || !byId.has(raw.to)) fail('连线 ' + (index + 1) + ' 引用了缺失的节点 id。');
      if (byId.get(raw.from).type === 'group' || byId.get(raw.to).type === 'group') fail('连线必须连接普通节点；边界不充当流程步骤。');
      if (raw.from === raw.to) fail('自循环请拆成明确的返回步骤并说明条件。');
      if (typeof raw.directed !== 'boolean') fail('每条连线必须显式声明 directed: true 或 false。');
      const line = raw.line || 'solid';
      if (!['solid', 'dashed'].includes(line)) fail('line 须为 solid 或 dashed。');
      if (raw.label != null && !nonempty(raw.label)) fail('连线 label 若提供，须为非空文字。');
      if (input.kind === 'relationship' && !nonempty(raw.label)) fail('关系图的每条连线需要 label，说明关系含义。');
      const key = JSON.stringify([raw.from, raw.to, raw.label || '', raw.directed, line]);
      if (edgeKeys.has(key)) fail('发现重复连线，请保留一次或明确不同关系。');
      edgeKeys.add(key);
      return Object.assign({}, raw, { line, index });
    });
    leaves.filter(node => node.type === 'decision').forEach(node => {
      const outgoing = edges.filter(edge => edge.from === node.id);
      if (outgoing.some(edge => !edge.directed || !nonempty(edge.label))) fail('判断节点的每条分支须有明确条件 label 与 directed: true。');
    });
    return { kind: input.kind, title: input.title, nodes, leaves, groups, byId, levels, edges };
  }

  const rectOf = item => ({ left: item.x, right: item.x + item.w, top: item.y, bottom: item.y + item.h });
  const overlaps = (a, b, gap = 0) => a.left < b.right + gap && a.right > b.left - gap && a.top < b.bottom + gap && a.bottom > b.top - gap;
  const inside = (p, r) => p.x > r.left + .1 && p.x < r.right - .1 && p.y > r.top + .1 && p.y < r.bottom - .1;
  function clearSegment(a, b, obstacles) {
    return !obstacles.some(r => {
      if (Math.abs(a.x - b.x) < .1) return a.x > r.left + .1 && a.x < r.right - .1 && Math.max(a.y, b.y) > r.top + .1 && Math.min(a.y, b.y) < r.bottom - .1;
      return a.y > r.top + .1 && a.y < r.bottom - .1 && Math.max(a.x, b.x) > r.left + .1 && Math.min(a.x, b.x) < r.right - .1;
    });
  }
  const unique = values => Array.from(new Set(values.map(value => Math.round(value * 10) / 10))).sort((a, b) => a - b);
  const distance = (a, b) => Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
  function simplify(points) {
    return points.filter((point, i) => !i || i === points.length - 1 || !((points[i - 1].x === point.x && point.x === points[i + 1].x) || (points[i - 1].y === point.y && point.y === points[i + 1].y)));
  }

  // A small visibility grid routes around every node; no guessed edges or freehand paths.
  function route(start, end, obstacles, width, height, usedSegments) {
    const xs = unique([start.x, end.x, 16, width - 16].concat(obstacles.flatMap(r => [r.left, r.right])));
    const ys = unique([start.y, end.y, 16, height - 16].concat(obstacles.flatMap(r => [r.top, r.bottom])));
    const points = [];
    const lookup = new Map();
    xs.forEach((x, xi) => ys.forEach((y, yi) => {
      const p = { x, y, xi, yi };
      if (x >= 0 && x <= width && y >= 0 && y <= height && !obstacles.some(r => inside(p, r))) {
        lookup.set(xi + ':' + yi, points.length);
        points.push(p);
      }
    }));
    const indexOf = p => lookup.get(xs.indexOf(Math.round(p.x * 10) / 10) + ':' + ys.indexOf(Math.round(p.y * 10) / 10));
    const startIndex = indexOf(start), endIndex = indexOf(end);
    if (startIndex == null || endIndex == null) fail('节点间距不足，无法连接边框；请拆图或调整 levels。');
    const adjacency = points.map(() => []);
    points.forEach((p, i) => {
      [[p.xi + 1, p.yi], [p.xi, p.yi + 1]].forEach(([xi, yi]) => {
        const j = lookup.get(xi + ':' + yi);
        if (j != null && clearSegment(p, points[j], obstacles)) {
          const dir = p.x === points[j].x ? 2 : 1;
          const shared = usedSegments.some(s => dir === s.dir && (dir === 2 ? p.x === s.a.x && Math.max(p.y, points[j].y) > Math.min(s.a.y, s.b.y) && Math.min(p.y, points[j].y) < Math.max(s.a.y, s.b.y) : p.y === s.a.y && Math.max(p.x, points[j].x) > Math.min(s.a.x, s.b.x) && Math.min(p.x, points[j].x) < Math.max(s.a.x, s.b.x)));
          const cost = distance(p, points[j]) + (shared ? 90 : 0);
          adjacency[i].push({ i: j, dir, cost });
          adjacency[j].push({ i, dir, cost });
        }
      });
    });
    const heap = [];
    function push(item) {
      heap.push(item);
      let i = heap.length - 1;
      while (i > 0) {
        const parent = (i - 1) >> 1;
        if (heap[parent].cost <= item.cost) break;
        heap[i] = heap[parent]; i = parent;
      }
      heap[i] = item;
    }
    function pop() {
      const top = heap[0], last = heap.pop();
      if (heap.length) {
        let i = 0;
        while (i * 2 + 1 < heap.length) {
          let child = i * 2 + 1;
          if (child + 1 < heap.length && heap[child + 1].cost < heap[child].cost) child++;
          if (heap[child].cost >= last.cost) break;
          heap[i] = heap[child]; i = child;
        }
        heap[i] = last;
      }
      return top;
    }
    const best = new Map(), previous = new Map();
    const firstKey = startIndex + ':0';
    best.set(firstKey, 0); push({ key: firstKey, i: startIndex, dir: 0, cost: 0 });
    let finish;
    while (heap.length) {
      const current = pop();
      if (current.cost !== best.get(current.key)) continue;
      if (current.i === endIndex) { finish = current.key; break; }
      adjacency[current.i].forEach(next => {
        const cost = current.cost + next.cost + (current.dir && current.dir !== next.dir ? 28 : 0);
        const key = next.i + ':' + next.dir;
        if (!best.has(key) || cost < best.get(key)) {
          best.set(key, cost); previous.set(key, current.key);
          push({ key, i: next.i, dir: next.dir, cost });
        }
      });
    }
    if (!finish) fail('此连线无法避开节点；请增加层间空间或拆分图示。');
    const path = [];
    while (finish) {
      path.push(points[Number(finish.split(':')[0])]);
      finish = previous.get(finish);
    }
    return simplify(path.reverse().map(p => ({ x: p.x, y: p.y })));
  }

  function portSide(from, to) {
    if (to.row > from.row) return ['bottom', 'top'];
    if (to.row < from.row) return ['top', 'bottom'];
    return to.x > from.x ? ['right', 'left'] : ['left', 'right'];
  }
  function makePort(box, side, offset) {
    const vertical = side === 'top' || side === 'bottom';
    const x = vertical ? box.x + box.w / 2 + offset : box.x + (side === 'right' ? box.w : 0);
    const y = vertical ? box.y + (side === 'bottom' ? box.h : 0) : box.y + box.h / 2 + offset;
    const dx = side === 'right' ? 18 : side === 'left' ? -18 : 0;
    const dy = side === 'bottom' ? 18 : side === 'top' ? -18 : 0;
    return { border: { x, y }, outside: { x: x + dx, y: y + dy } };
  }
  function getPorts(model, boxes) {
    const buckets = new Map(), result = new Map();
    model.edges.forEach(edge => {
      const from = boxes.get(edge.from), to = boxes.get(edge.to);
      const sides = portSide(from, to);
      [[from, to, sides[0], 'from'], [to, from, sides[1], 'to']].forEach(([box, other, side, role]) => {
        const key = box.id + ':' + side;
        if (!buckets.has(key)) buckets.set(key, []);
        buckets.get(key).push({ edge, box, other, side, role });
      });
    });
    buckets.forEach(items => {
      items.sort((a, b) => (a.side === 'top' || a.side === 'bottom' ? a.other.x - b.other.x : a.other.y - b.other.y) || a.edge.index - b.edge.index);
      items.forEach((item, i) => {
        const capacity = (item.side === 'top' || item.side === 'bottom' ? item.box.w : item.box.h) - 44;
        const span = Math.min(capacity, (items.length - 1) * 28);
        const offset = items.length === 1 ? 0 : -span / 2 + span * i / (items.length - 1);
        if (!result.has(item.edge.index)) result.set(item.edge.index, {});
        result.get(item.edge.index)[item.role] = makePort(item.box, item.side, offset);
      });
    });
    return result;
  }

  function relationshipText(model) {
    const lines = model.edges.map(edge => model.byId.get(edge.from).label + (edge.directed ? ' → ' : ' — ') + model.byId.get(edge.to).label + (edge.label ? '：' + edge.label : '') + (edge.line === 'dashed' ? '（虚线）' : ''));
    model.groups.forEach(group => lines.push('边界“' + group.label + '”包含：' + group.members.map(id => model.byId.get(id).label).join('、') + '。'));
    model.leaves.filter(node => !model.edges.some(edge => edge.from === node.id || edge.to === node.id)).forEach(node => lines.push('独立节点：' + node.label + '。'));
    return lines;
  }

  function draw(figure, canvas, model, state) {
    if (!canvas.clientWidth) { figure.dataset.diagramState = 'deferred'; state.width = 0; return; }
    const previousScroll = canvas.scrollLeft;
    const previousWidth = state.width;
    const available = Math.max(220, Math.floor(canvas.clientWidth));
    const maxColumns = Math.max.apply(null, model.levels.map(row => row.length));
    const horizontalGap = 64, sideMargin = model.groups.length ? 48 : 32;
    const nodeWidth = Math.max(200, Math.min(224, Math.floor((available - sideMargin * 2 - horizontalGap * (maxColumns - 1)) / maxColumns)));
    const width = Math.max(available, maxColumns * nodeWidth + horizontalGap * (maxColumns - 1) + sideMargin * 2);
    const stage = element('div', 'hn-diagram-stage');
    stage.style.width = width + 'px';
    stage.setAttribute('role', 'img');
    const relations = relationshipText(model);
    stage.setAttribute('aria-label', model.title + '。' + kindNames[model.kind] + '。' + relations.join(' '));
    const boxes = new Map();
    model.levels.forEach((row, rowIndex) => row.forEach(id => {
      const node = model.byId.get(id);
      const el = element('div', 'hn-diagram-node');
      el.dataset.nodeId = id; el.dataset.type = node.type;
      if (node.focus) el.dataset.focus = 'true';
      if (node.color) el.dataset.color = node.color;
      if (node.type === 'decision' || node.type === 'external') el.append(element('span', 'hn-diagram-node-tag', typeNames[node.type]));
      if (node.category) el.append(element('span', 'hn-diagram-node-tag', node.category));
      el.append(element('span', 'hn-diagram-node-label', node.label));
      el.style.width = nodeWidth + 'px';
      el.setAttribute('aria-hidden', 'true');
      stage.append(el);
      boxes.set(id, { id, el, row: rowIndex, w: nodeWidth, h: 0, x: 0, y: 0 });
    }));
    canvas.replaceChildren(stage);
    let y = model.groups.length ? 72 : 24;
    model.levels.forEach(row => {
      const total = row.length * nodeWidth + (row.length - 1) * horizontalGap;
      const x = (width - total) / 2;
      let tallest = 0;
      row.forEach((id, index) => {
        const box = boxes.get(id);
        box.h = Math.ceil(box.el.getBoundingClientRect().height);
        box.x = x + index * (nodeWidth + horizontalGap); box.y = y;
        box.el.style.left = box.x + 'px'; box.el.style.top = box.y + 'px';
        tallest = Math.max(tallest, box.h);
      });
      y += tallest + (model.groups.length ? 120 : 100);
    });
    const height = y - (model.groups.length ? 120 : 100) + (model.groups.length ? 40 : 24);
    stage.style.height = height + 'px';
    const nodeRects = Array.from(boxes.values()).map(rectOf);
    const obstacles = nodeRects.map(r => ({ left: r.left - 12, right: r.right + 12, top: r.top - 12, bottom: r.bottom + 12 }));
    const occupiedLabels = [];
    const groupRects = [];
    model.groups.forEach(group => {
      const members = group.members.map(id => boxes.get(id));
      const left = Math.min.apply(null, members.map(box => box.x)) - 20;
      const right = Math.max.apply(null, members.map(box => box.x + box.w)) + 20;
      const top = Math.min.apply(null, members.map(box => box.y)) - 48;
      const bottom = Math.max.apply(null, members.map(box => box.y + box.h)) + 20;
      const boundary = { left, right, top, bottom };
      if (Array.from(boxes.values()).some(box => !group.members.includes(box.id) && overlaps(boundary, rectOf(box)))) fail('边界“' + group.label + '”会包入非成员；请让成员相邻或拆图。');
      if (groupRects.some(rect => overlaps(boundary, rect))) fail('边界发生重叠，请调整成员层级或拆成两张图。');
      groupRects.push(boundary);
      const el = element('div', 'hn-diagram-group');
      Object.assign(el.style, { left: left + 'px', top: top + 'px', width: (right - left) + 'px', height: (bottom - top) + 'px' });
      el.setAttribute('aria-hidden', 'true'); stage.append(el);
      const label = element('div', 'hn-diagram-group-label', group.label);
      Object.assign(label.style, { left: (left + 10) + 'px', top: (top + 10) + 'px', maxWidth: (right - left - 20) + 'px' });
      label.setAttribute('aria-hidden', 'true'); stage.append(label);
      const labelRect = { left: left + 10, right: left + 10 + label.offsetWidth, top: top + 10, bottom: top + 10 + label.offsetHeight };
      if (labelRect.bottom > Math.min.apply(null, members.map(box => box.y)) - 8) fail('边界名称过长，请缩短标签并将解释放到图注。');
      occupiedLabels.push(labelRect);
      obstacles.push({ left: labelRect.left - 6, right: labelRect.right + 6, top: labelRect.top - 6, bottom: labelRect.bottom + 6 });
    });
    const svg = svgElement('svg', { class: 'hn-diagram-svg', width, height, viewBox: '0 0 ' + width + ' ' + height, 'aria-hidden': 'true' });
    const defs = svgElement('defs');
    const markerId = 'hn-arrow-' + state.id;
    const marker = svgElement('marker', { id: markerId, markerWidth: 10, markerHeight: 10, refX: 9, refY: 5, orient: 'auto', markerUnits: 'userSpaceOnUse', viewBox: '0 0 10 10' });
    marker.append(svgElement('path', { d: 'M1 1 L9 5 L1 9', fill: 'none', stroke: '#68635D', 'stroke-width': 2 }));
    defs.append(marker); svg.append(defs); stage.prepend(svg);
    const ports = getPorts(model, boxes), usedSegments = [];
    model.edges.forEach(edge => {
      const pair = ports.get(edge.index);
      const middle = route(pair.from.outside, pair.to.outside, obstacles, width, height, usedSegments);
      const points = simplify([pair.from.border].concat(middle, [pair.to.border]));
      const path = svgElement('path', { class: 'hn-diagram-edge', d: points.map((point, i) => (i ? 'L' : 'M') + point.x + ' ' + point.y).join(' '), 'data-line': edge.line, 'data-from': edge.from, 'data-to': edge.to });
      if (edge.directed) path.setAttribute('marker-end', 'url(#' + markerId + ')');
      svg.append(path);
      const segments = points.slice(1).map((p, i) => ({ a: points[i], b: p, dir: points[i].x === p.x ? 2 : 1 }));
      usedSegments.push.apply(usedSegments, segments);
      if (edge.label) {
        const label = element('div', 'hn-diagram-edge-label', edge.label);
        label.style.maxWidth = '148px'; label.setAttribute('aria-hidden', 'true'); stage.append(label);
        const lw = label.offsetWidth, lh = label.offsetHeight;
        const candidates = [];
        segments.forEach((segment, i) => {
          const mid = { x: (segment.a.x + segment.b.x) / 2, y: (segment.a.y + segment.b.y) / 2 };
          if (segment.dir === 1) {
            candidates.push({ left: mid.x - lw / 2, top: mid.y - lh - 4, rank: i === 0 ? 1 : 0 });
            candidates.push({ left: mid.x - lw / 2, top: mid.y + 4, rank: 2 });
          } else {
            candidates.push({ left: mid.x + 6, top: mid.y - lh / 2, rank: 3 });
            candidates.push({ left: mid.x - lw - 6, top: mid.y - lh / 2, rank: 4 });
          }
        });
        candidates.sort((a, b) => a.rank - b.rank);
        const chosen = candidates.find(candidate => {
          candidate.right = candidate.left + lw; candidate.bottom = candidate.top + lh;
          return candidate.left >= 0 && candidate.right <= width && candidate.top >= 0 && candidate.bottom <= height && !nodeRects.concat(occupiedLabels).some(rect => overlaps(candidate, rect, 4)) && usedSegments.every(segment => clearSegment(segment.a, segment.b, [candidate]));
        });
        if (!chosen) fail('连线标签没有足够空间；请缩短标签或拆图。');
        label.style.left = chosen.left + 'px'; label.style.top = chosen.top + 'px'; occupiedLabels.push(chosen);
        obstacles.push({ left: chosen.left - 4, right: chosen.right + 4, top: chosen.top - 4, bottom: chosen.bottom + 4 });
      }
    });
    const overflow = width > available + 1;
    figure.dataset.overflow = String(overflow);
    canvas.setAttribute('role', 'region');
    canvas.setAttribute('aria-label', model.title + (overflow ? '，可左右滚动查看完整图形' : '图形'));
    if (overflow) canvas.setAttribute('tabindex', '0'); else canvas.removeAttribute('tabindex');
    figure.querySelectorAll('[data-hn-generated]').forEach(el => el.remove());
    const note = element('p', 'hn-diagram-scroll-note', '可左右滚动查看完整结构；文字关系清单提供同等信息。');
    note.hidden = !overflow; note.dataset.hnGenerated = 'true';
    const details = element('details', 'hn-diagram-relations'); details.dataset.hnGenerated = 'true';
    const summary = element('summary', '', '文字关系清单'); details.append(summary);
    details.append(element('p', '', '箭头表示已声明的方向；无箭头表示普通关联。上下位置只按作者声明的层级排列。'));
    const list = element('ul'); relations.forEach(line => list.append(element('li', '', line))); details.append(list);
    if (state.detailsOpen) details.open = true;
    details.addEventListener('toggle', () => { state.detailsOpen = details.open; });
    canvas.before(note);
    canvas.after(details);
    if (overflow) {
      // First view shows the leading node; same-width redraws preserve the reader's scroll position.
      const lead = boxes.get(model.levels[0][0]);
      canvas.scrollLeft = previousWidth === canvas.clientWidth ? previousScroll : Math.max(0, Math.min(width - available, lead.x + lead.w / 2 - available / 2));
    }
    figure.dataset.diagramState = 'ready';
    state.width = canvas.clientWidth;
  }

  function render(figure) {
    if (!figure || !figure.matches('figure.hn-diagram')) return false;
    const canvas = figure.querySelector('.hn-diagram-canvas');
    if (!canvas) return false;
    let state = states.get(figure);
    if (!state) {
      state = { id: ++sequence, width: -1, detailsOpen: false, queued: false }; states.set(figure, state);
      if ('ResizeObserver' in window) {
        state.observer = new ResizeObserver(() => {
          if (Math.abs(canvas.clientWidth - state.width) > 1 && !state.queued) {
            state.queued = true;
            window.requestAnimationFrame(() => { state.queued = false; if (figure.isConnected) render(figure); });
          }
        });
        state.observer.observe(canvas);
      }
    }
    try {
      const script = figure.querySelector('script.hn-diagram-data[type="application/json"]');
      if (!script) fail('缺少 application/json.hn-diagram-data。');
      const model = validate(JSON.parse(script.textContent));
      const mappings = new Map(model.nodes.filter(node => node.category).map(node => [node.category, node.color]));
      // 显式 category 是页面内的稳定身份；单图 render/resize 也检查其余图示的映射。
      document.querySelectorAll('figure.hn-diagram script.hn-diagram-data[type="application/json"]').forEach(peer => {
        if (peer === script) return;
        let data;
        try { data = JSON.parse(peer.textContent); } catch (_) { return; }
        if (!data || !Array.isArray(data.nodes)) return;
        data.nodes.forEach(node => {
          if (node && mappings.has(node.category) && PALETTE.includes(node.color) && mappings.get(node.category) !== node.color) fail('同一页面类别「' + node.category + '」的颜色映射不一致。');
        });
      });
      draw(figure, canvas, model, state);
      return true;
    } catch (error) {
      canvas.replaceChildren(element('p', 'hn-diagram-error', '图示未生成：' + error.message));
      canvas.removeAttribute('tabindex'); canvas.setAttribute('role', 'region'); canvas.setAttribute('aria-label', '图示数据错误');
      figure.querySelectorAll('[data-hn-generated]').forEach(el => el.remove());
      figure.dataset.diagramState = 'error'; figure.dataset.overflow = 'false'; state.width = canvas.clientWidth;
      return false;
    }
  }
  function renderAll(root) {
    const scope = root || document;
    const figures = Array.from(scope.querySelectorAll('figure.hn-diagram'));
    if (scope.matches && scope.matches('figure.hn-diagram')) figures.unshift(scope);
    return figures.map(figure => ({ figure, ok: render(figure) }));
  }
  window.HaosuNakiDiagrams = Object.freeze({ renderAll, render, validate });
  const boot = () => { renderAll(); if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => renderAll()); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true }); else boot();
  if (!('ResizeObserver' in window)) window.addEventListener('resize', () => renderAll());
  window.addEventListener('beforeprint', () => document.querySelectorAll('.hn-diagram-relations').forEach(details => { details.dataset.wasOpen = String(details.open); details.open = true; }));
  window.addEventListener('afterprint', () => document.querySelectorAll('.hn-diagram-relations').forEach(details => { details.open = details.dataset.wasOpen === 'true'; delete details.dataset.wasOpen; }));
}());
