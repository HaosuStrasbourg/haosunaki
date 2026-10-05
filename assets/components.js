/* HaosuNaki 已确认阅读组件：仅增强代码复制和任务完成反馈，不改变业务状态。 */
(function () {
  'use strict';
  function element(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  async function copyCode(source, status) {
    let copied = false;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(source);
        copied = true;
      }
    } catch (_) {}
    if (!copied) {
      const scratch = element('textarea');
      scratch.value = source;
      scratch.setAttribute('aria-label', '手动复制代码');
      scratch.style.cssText = 'position:fixed;left:-10000px;top:0';
      document.body.append(scratch);
      scratch.select();
      try { copied = document.execCommand('copy'); } catch (_) {}
      scratch.remove();
    }
    status.replaceChildren();
    if (copied) { status.textContent = '已复制原始代码'; return; }
    status.textContent = '浏览器未允许复制。代码已选中，请按 ⌘C / Ctrl+C：';
    const manual = element('textarea', 'hn-manual-copy');
    manual.value = source;
    manual.rows = 4;
    manual.readOnly = true;
    manual.setAttribute('aria-label', '手动复制原始代码');
    status.append(manual);
    manual.focus();
    manual.select();
  }
  function codeBlock(block) {
    if (block.dataset.hnCodeReady === 'true') return;
    const original = block.querySelector('pre code');
    if (!original) return;
    const source = original.textContent;
    const lines = source === '' ? [] : source.split(/\r\n|\n|\r/);
    // 文件末尾换行不是额外代码行；中间及末尾空白行保留，复制仍使用未改写源码。
    if (/(?:\r\n|\n|\r)$/.test(source)) lines.pop();
    const head = element('div', 'hn-code-head');
    const name = [block.dataset.filename, block.dataset.language].filter(Boolean).join(' · ') || '代码';
    head.append(element('span', '', name + ' · ' + lines.length + ' 行'));
    const button = element('button', '', '复制');
    button.type = 'button';
    button.setAttribute('aria-label', '复制 ' + name + ' 原始代码');
    head.append(button);
    const scroll = element('div', 'hn-code-scroll');
    scroll.tabIndex = 0;
    scroll.setAttribute('role', 'region');
    scroll.setAttribute('aria-label', name + '，长行可左右滚动');
    const pre = element('pre');
    const code = element('code');
    lines.forEach((line, index) => {
      const row = element('span', 'hn-code-line');
      const number = element('span', 'hn-code-line-number', String(index + 1));
      number.setAttribute('aria-hidden', 'true');
      row.append(number, element('span', 'hn-code-text', line));
      code.append(row);
    });
    pre.append(code); scroll.append(pre);
    const status = element('div', 'hn-copy-status');
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    button.addEventListener('click', () => copyCode(source, status));
    original.closest('pre').replaceWith(scroll);
    block.prepend(head); block.append(status);
    block.dataset.hnCodeReady = 'true';
  }
  function init(root) {
    const scope = root || document;
    scope.querySelectorAll('.hn-code').forEach(codeBlock);
    scope.querySelectorAll('.hn-action input[type="checkbox"]').forEach(input => {
      if (input.dataset.hnActionReady === 'true') return;
      const action = input.closest('.hn-action');
      const update = () => action.classList.toggle('is-complete', input.checked);
      input.addEventListener('change', update);
      update(); input.dataset.hnActionReady = 'true';
    });
  }
  window.HaosuNakiComponents = Object.freeze({ init });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init());
  else init();
})();
