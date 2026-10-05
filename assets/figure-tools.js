/* HaosuNaki：导出当前 SVG 图面；不抓取资源、不打包本机字体。 */
(function (global) {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const FONT_NAMES = new Set(['IBM Plex Mono', 'JetBrains Mono', 'Lora']);
  const PROPS = ('color fill fill-opacity fill-rule clip-rule stroke stroke-width stroke-opacity ' +
    'stroke-dasharray stroke-dashoffset stroke-linecap stroke-linejoin stroke-miterlimit opacity ' +
    'display visibility font-family font-size font-weight font-style font-stretch font-variant ' +
    'font-feature-settings font-variation-settings font-kerning text-anchor dominant-baseline ' +
    'alignment-baseline baseline-shift letter-spacing word-spacing text-decoration white-space ' +
    'text-rendering shape-rendering image-rendering paint-order vector-effect marker-start marker-mid ' +
    'marker-end clip-path mask filter stop-color stop-opacity flood-color flood-opacity lighting-color ' +
    'mix-blend-mode isolation transform transform-origin transform-box').split(' ');

  async function exportSVG(svg, filename = 'HaosuNaki-figure.svg', options = {}) {
    if (!svg || svg.nodeType !== 1 || svg.namespaceURI !== NS || svg.localName !== 'svg') {
      throw new Error('导出目标必须是内联 SVG。');
    }
    if (!svg.isConnected) throw new Error('请先将 SVG 放入当前页面，再导出计算后的样式。');
    const doc = svg.ownerDocument;
    const win = doc.defaultView;
    if (doc.fonts) await doc.fonts.ready;
    const base = new URL(doc.URL);
    base.hash = '';
    const clone = svg.cloneNode(true);
    const originals = [svg, ...svg.querySelectorAll('*')];
    const copies = [clone, ...clone.querySelectorAll('*')];
    const idList = originals.map(n => n.id).filter(Boolean);
    const ids = new Set(idList);
    if (ids.size !== idList.length) throw new Error('当前 SVG 存在重复 ID，请先为节点和图形定义分配唯一 ID。');
    const usedFonts = new Set();

    function localRef(value) {
      if (value.startsWith('#')) return value;
      let resolved;
      try { resolved = new URL(value, doc.baseURI); } catch (_) { return null; }
      const hash = resolved.hash;
      resolved.hash = '';
      return hash && resolved.href === base.href ? hash : null;
    }
    function checkedRef(value) {
      const ref = localRef(value);
      let id;
      try { id = ref && decodeURIComponent(ref.slice(1)); } catch (_) { id = null; }
      if (!id || !ids.has(id)) throw new Error('图中包含外部资源或 SVG 之外的引用：请把定义移入当前 SVG。');
      return ref;
    }
    function normalizeURLs(value) {
      return value.replace(/url\(\s*(['"]?)(.*?)\1\s*\)/gi, (_, q, url) =>
        'url("' + checkedRef(url) + '")');
    }

    originals.forEach((node, index) => {
      const copy = copies[index];
      if (node.namespaceURI !== NS || /^(script|foreignObject|animate|animateMotion|animateTransform|set)$/i.test(node.localName)) {
        throw new Error('此图包含脚本、外部文档或 SVG 动画；请先转成安全的静态 SVG。');
      }
      // 页面样式被下面的计算样式替代；只另行嵌入明确允许的开放字体。
      if (node.localName === 'style') { copy.remove(); return; }
      copy.removeAttribute('style');
      for (const attr of [...node.attributes]) {
        if (/^on/i.test(attr.name)) throw new Error('SVG 含事件属性，请用页面 JavaScript 绑定事件后再导出。');
        if (attr.localName === 'href') {
          const value = attr.value.trim();
          let replacement;
          if (node.localName === 'image' && /^data:image\/(png|jpeg|gif|webp);base64,[A-Za-z0-9+/=\s]+$/i.test(value)) {
            replacement = value;
          } else if (node.localName === 'a' && /^https?:\/\//i.test(value)) {
            replacement = localRef(value) ? checkedRef(value) : value;
          } else {
            replacement = checkedRef(value);
          }
          copy.setAttributeNS(attr.namespaceURI, attr.name, replacement);
        } else if (attr.name !== 'style' && /url\(/i.test(attr.value)) {
          copy.setAttributeNS(attr.namespaceURI, attr.name, normalizeURLs(attr.value));
        }
      }
      const style = win.getComputedStyle(node);
      PROPS.forEach(property => {
        const value = style.getPropertyValue(property);
        if (value) copy.style.setProperty(property, normalizeURLs(value));
      });
      // 支持用 CSS 指定 SVG 几何；没有计算值时保留原属性。
      if (/^(path|rect|circle|ellipse|image|use)$/.test(node.localName)) {
        ['d', 'x', 'y', 'cx', 'cy', 'r', 'rx', 'ry', 'width', 'height'].forEach(property => {
          const value = style.getPropertyValue(property);
          if (value && value !== 'auto' && value !== 'none') copy.style.setProperty(property, value);
        });
      }
      style.fontFamily.split(',').forEach(f => usedFonts.add(f.trim().replace(/^['"]|['"]$/g, '')));
    });

    const fontFaces = [];
    const embeddedFamilies = new Set();
    doc.querySelectorAll('style').forEach(style => {
      for (const match of style.textContent.matchAll(/@font-face\s*\{[^{}]*\}/gi)) {
        const family = match[0].match(/font-family\s*:\s*(['"]?)([^;'"}]+)\1\s*[;}]/i);
        const name = family && family[2].trim();
        if (!FONT_NAMES.has(name) || !usedFonts.has(name)) continue;
        const urls = [...match[0].matchAll(/url\(\s*(['"]?)(.*?)\1\s*\)/gi)];
        if (urls.some(m => !/^data:(font\/|application\/(font-|x-font-|vnd\.ms-fontobject|octet-stream))/i.test(m[2]))) {
          throw new Error('开放字体仍引用外部文件；请先在页面中内嵌字体，再导出。');
        }
        if (urls.length) {
          fontFaces.push(match[0]);
          embeddedFamilies.add(name);
        }
      }
    });
    const licenseTexts = [];
    if (embeddedFamilies.size) {
      const licenseTemplate = doc.getElementById('font-license-notices');
      const notices = licenseTemplate && licenseTemplate.content
        ? [...licenseTemplate.content.querySelectorAll('pre[data-family]')] : [];
      embeddedFamilies.forEach(family => {
        const notice = notices.find(n => n.getAttribute('data-family').trim() === family);
        const text = notice && notice.textContent.trim();
        if (!text || !/copyright/i.test(text) || !/SIL OPEN FONT LICENSE/i.test(text)) {
          throw new Error('无法导出字体 ' + family + '：页面缺少对应的原始版权声明和 OFL 许可文本。');
        }
        licenseTexts.push(text);
      });
    }

    let box = (svg.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    if (box.length !== 4 || !box.every(Number.isFinite) || box[2] <= 0 || box[3] <= 0) {
      const bounds = svg.getBoundingClientRect();
      if (!(bounds.width > 0 && bounds.height > 0)) throw new Error('SVG 缺少有效 viewBox 或可见尺寸。');
      box = [0, 0, bounds.width, bounds.height];
    }
    clone.setAttributeNS('http://www.w3.org/2000/xmlns/', 'xmlns', NS);
    clone.setAttribute('viewBox', box.join(' '));
    clone.setAttribute('width', String(box[2]));
    clone.setAttribute('height', String(box[3]));
    clone.style.width = box[2] + 'px';
    clone.style.height = box[3] + 'px';
    if (options.transparent) {
      clone.style.background = 'none';
      clone.style.backgroundColor = 'transparent';
    }
    // 背景是图面自身的一部分，透明导出只省略此矩形。
    if (!options.transparent) {
      const background = doc.createElementNS(NS, 'rect');
      ['x', 'y', 'width', 'height'].forEach((key, i) => background.setAttribute(key, String(box[i])));
      background.setAttribute('fill', '#FAF8F4');
      background.setAttribute('aria-hidden', 'true');
      clone.insertBefore(background, clone.firstChild);
    }
    if (fontFaces.length) {
      const defs = doc.createElementNS(NS, 'defs');
      const style = doc.createElementNS(NS, 'style');
      style.textContent = [...new Set(fontFaces)].join('\n');
      defs.appendChild(style);
      clone.insertBefore(defs, clone.firstChild);
    }
    if (licenseTexts.length) {
      const metadata = doc.createElementNS(NS, 'metadata');
      metadata.textContent = licenseTexts.join('\n\n');
      clone.insertBefore(metadata, clone.firstChild);
    }
    const source = new win.XMLSerializer().serializeToString(clone);
    const blob = new win.Blob([source], { type: 'image/svg+xml;charset=utf-8' });
    const objectURL = win.URL.createObjectURL(blob);
    const link = doc.createElement('a');
    const safeName = String(filename).replace(/[\\/<>:"|?*\u0000-\u001F]/g, '-').replace(/\.svg$/i, '') + '.svg';
    link.href = objectURL;
    link.download = safeName;
    link.hidden = true;
    doc.body.appendChild(link);
    try { link.click(); } finally {
      link.remove();
      // 下载开始后再释放；返回值只表示已发起下载，不能证明文件保存成功。
      win.setTimeout(() => win.URL.revokeObjectURL(objectURL), 30000);
    }
    return { filename: safeName, width: box[2], height: box[3], transparent: Boolean(options.transparent) };
  }
  global.HNFigure = Object.assign(global.HNFigure || {}, { exportSVG });
})(window);
