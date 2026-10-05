#!/usr/bin/env python3
"""用合成数据生成离线示例；仅重建 examples/ 下的本脚本产物。"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from figure_primitives import bar, line, flow, THEME, category_colors

OUT = Path(__file__).resolve().parent

def main():
    rows = [
        {'id': 'a', 'label': '方案 A', 'value': 68},
        {'id': 'b', 'label': '方案 B', 'value': 84},
        {'id': 'c', 'label': '方案 C', 'value': 75},
    ]
    colors = category_colors(['a', 'b', 'c'])
    shared = dict(desc='合成数据；各方案均为100次虚构任务中的成功次数。',
                  domain=(0, 100), ticks=[0, 20, 40, 60, 80, 100], unit='成功率（%） · 合成数据',
                  caption='共同分母：每组 100 次任务。示例没有统计推断。',
                  value_format=lambda v: f'{v:.0f}%')
    figures = [
        ('focus', '突出重点', '读者只需要关注方案 B 时，其余方案保持中性。颜色表达阅读重点，不表示显著性。',
         bar(rows, title='Focus · 方案 B 的位置', mode='focus', focus_id='b', prefix='demo-focus', **shared)),
        ('category', '平等比较', '三种方案需要同等识别时，采用稳定的类别色；调整排序也保留同一身份。',
         bar(rows, title='Compare · 三种方案同等比较', mode='category', color_map=colors, prefix='demo-category', **shared)),
        ('line', '变化与缺失', '线的位置表达数值，断口表达缺失。第三周没有记录，不能连接两端来暗示中间变化。',
         line([{'id': 'a', 'label': '方案 A', 'points': [(1, 52), (2, 64), (3, None), (4, 72), (5, 80)]}],
              title='Trend · 没有记录，就留下缺口', desc='合成数据。第三周未提供，保留断线。', mode='explicitsemantic',
              color_map={'a': THEME['cobalt']}, x_domain=(1, 5), y_domain=(0, 100),
              x_ticks=[1, 2, 3, 4, 5], y_ticks=[0, 20, 40, 60, 80, 100], x_label='周次', y_label='完成率（%）',
              caption='固定窗口下的虚构完成率，不代表真实产品。', prefix='demo-line')),
        ('flow', '条件与分支', '条件用菱形，两条出线写清楚含义。颜色只强调判断节点；实际步骤、起点和两个终点都保留。',
         flow([
             {'id': 'input', 'shape': 'terminal', 'terminal_kind': 'start', 'label': '放入初稿', 'x': 40, 'y': 124, 'width': 180},
             {'id': 'check', 'shape': 'decision', 'label': '材料完整？', 'x': 330, 'y': 100, 'width': 210, 'height': 112, 'emphasis': True},
             {'id': 'ready', 'shape': 'terminal', 'terminal_kind': 'end', 'label': '进入图文整理', 'x': 670, 'y': 124, 'width': 190},
             {'id': 'missing', 'shape': 'terminal', 'terminal_kind': 'end', 'label': '列出缺口，待补材料', 'x': 310, 'y': 325, 'width': 250}
         ], [
             {'source': 'input', 'target': 'check'},
             {'source': 'check', 'target': 'ready', 'label': '是'},
             {'source': 'check', 'target': 'missing', 'label': '否'}
         ], title='Flow · 先核对，再组织图文', desc='机制示意；每条箭头表示处理先后，起止为本段工作范围。',
              caption='本段结束不等于文档发布；待补项由作者处理，不自动编造材料。', prefix='demo-flow')),
    ]
    sections = []
    for i, (key, title, intro, svg) in enumerate(figures, 1):
        (OUT / f'{key}.svg').write_text(svg, encoding='utf-8')
        sections.append(f'''<section class="part" id="{key}"><p class="section-label">{i:02d} / {title}</p>
<h2>{title}</h2><p class="section-intro">{intro}</p>
<figure class="hn-figure"><div class="hn-figure-frame"><div class="hn-chart-scroll" tabindex="0" role="region" aria-label="{title}，窄屏可左右滚动">{svg}</div></div><div class="hn-tools"><button type="button" data-export="{key}">下载 SVG</button><span class="hn-export-status" aria-live="polite"></span></div></figure>
<p class="caption">窄屏可在图内横向滚动。图下工具导出当前 SVG；导出结果不包含本段正文。</p></section>''')
    body = '''<main><header class="hero"><p class="eyebrow">公开版示例 · 合成数据</p>
<h1>同一套方法，<br>不同的表达任务。</h1><section class="summary" aria-label="核心原则"><p class="conclusion">先决定读者要看什么，再决定怎样画。风格保持一致，数据含义和阅读重点各自说清。</p></section></header>'''
    body += ''.join(sections)
    body += '''<section class="part"><h2>把自己的初稿放进来</h2><p>保留真实数据、来源和业务含义，再选择表达。不要把演示数字替换成看起来合理的业务结论。</p><p class="caption">更多用法见仓库中的使用说明；改变主题后重新生成本页。</p></section></main>'''
    body += '''<script>
for (const button of document.querySelectorAll('[data-export]')) {
  button.addEventListener('click', async () => {
    const section = button.closest('section');
    const status = section.querySelector('.hn-export-status');
    try { await HNFigure.exportSVG(section.querySelector('svg'), button.dataset.export + '.svg');
      status.textContent = '已发起下载，请检查保存的文件。';
    } catch (error) { status.textContent = '导出失败：' + error.message; }
  });
}
</script>'''
    (OUT / 'demo-body.html').write_text(body, encoding='utf-8')
    subprocess.run([sys.executable, str(ROOT / 'scripts/build_html.py'), '--body', str(OUT / 'demo-body.html'),
                    '--title', 'HaosuNaki · 方法与图形示例', '--output', str(OUT / 'demo.html'), '--force'], check=True)
    print('Created examples/demo.html and four SVG files (synthetic data).')

if __name__ == '__main__':
    main()
