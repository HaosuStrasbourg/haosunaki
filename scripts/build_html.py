#!/usr/bin/env python3
"""把已写好的 <main> 内容与 HaosuNaki 样式、开源字体及许可合为离线 HTML。"""
import argparse
import html
import re
from html.parser import HTMLParser
from pathlib import Path
from string import Template

# 按本脚本位置加载同包参数，兼容直接 importlib 导入和命令行调用。
import importlib.util
_token_spec = importlib.util.spec_from_file_location('_hn_design_tokens', Path(__file__).with_name('design_tokens.py'))
_tokens = importlib.util.module_from_spec(_token_spec)
_token_spec.loader.exec_module(_tokens)



class ChartValidator(HTMLParser):
    """按实际父子元素验证逐图模式；普通元素上的 data 属性不参与判定。"""

    VOID_ELEMENTS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                     'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.charts = []
        self.errors = []
        self.explicit_colors = {}
        self.component_scripts_needed = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set((attributes.get('class') or '').split())
        if classes & {'hn-code', 'hn-action'}:
            self.component_scripts_needed = True
        parent = self.stack[-1] if self.stack else None
        node = {'tag': tag, 'chart': None}
        if 'chart' in classes:
            chart = {'mode': attributes.get('data-chart'), 'rows': [],
                     'line': self.getpos()[0]}
            self.charts.append(chart)
            node['chart'] = chart
        if 'chart-row' in classes:
            if parent is None or parent['chart'] is None:
                self.errors.append(f'第 {self.getpos()[0]} 行：.chart-row 必须是 .chart 的直接子元素。')
            else:
                parent['chart']['rows'].append({
                    'primary': 'primary' in classes,
                    'series': (attributes.get('data-series') or '').strip(),
                    'color': attributes.get('data-color'),
                })
        if tag not in self.VOID_ELEMENTS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        # 保留父层状态；未知结束标签不应把前面的图表误当成新图表的父元素。
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]['tag'] == tag:
                del self.stack[index:]
                break

    def validate(self):
        series_colors = {}
        palette = _tokens.palette()
        for chart in self.charts:
            label = f"第 {chart['line']} 行图表"
            rows = chart['rows']
            if chart['mode'] not in {'focus', 'category'}:
                self.errors.append(f'{label}：每个 .chart 必须单独设置 data-chart="focus" 或 "category"。')
                continue
            if chart['mode'] == 'focus':
                if len(rows) < 2 or sum(row['primary'] for row in rows) != 1:
                    self.errors.append(f'{label}：focus 至少需要两个直接子级 .chart-row，且恰好一行带 primary 类。')
                continue
            if not rows:
                self.errors.append(f'{label}：category 需要直接子级 .chart-row。')
            color_series = {}
            seen_series = set()
            for row in rows:
                series, token = row['series'], row['color']
                color = palette.get(token)
                if isinstance(token, str) and re.fullmatch(r'#[0-9A-Fa-f]{6}', token):
                    color = token.upper()
                if row['primary']:
                    self.errors.append(f'{label}：category 表达平等比较，不设置 primary；突出单一对象请用 focus。')
                if not series or color is None:
                    self.errors.append(f'{label}：category 每行须有非空 data-series，以及品牌色名或明确的 data-color="#RRGGBB"。领域语义优先；同类跨图保持同色。')
                    continue
                if series in seen_series:
                    self.errors.append(f'{label}：类别 {series!r} 重复出现，请检查类别身份与图表结构。')
                seen_series.add(series)
                if series in series_colors and series_colors[series] != color:
                    self.errors.append(f'{label}：类别 {series!r} 在同一报告中使用了不同颜色。')
                if color in color_series and color_series[color] != series:
                    self.errors.append(f'{label}：{color} 已用于类别 {color_series[color]!r}，不能在同一张图中再用于 {series!r}。请为平等类别指定可区分的颜色，或改用分面图／表格。')
                self.explicit_colors[token] = color
                series_colors.setdefault(series, color)
                color_series.setdefault(color, series)
        return self.errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body', required=True, type=Path, help='UTF-8 HTML 正文，包含一个 main 元素')
    parser.add_argument('--title', required=True, help='浏览器标题，自动转义')
    parser.add_argument('--output', required=True, type=Path, help='输出的独立 HTML 文件')
    parser.add_argument('--chart', help=argparse.SUPPRESS)
    parser.add_argument('--force', action='store_true', help='仅在已获覆盖该文件授权时使用')
    args = parser.parse_args()
    if args.chart is not None:
        parser.error('--chart 整篇模式已移除。请移除该参数，并在每个 .chart 元素设置 data-chart="focus" 或 "category"；分类行还须设置稳定的 data-series 与 data-color。')
    if args.output.resolve() == args.body.resolve():
        parser.error('输出与正文输入不能是同一文件。')
    if args.output.exists() and not args.force:
        parser.error('输出文件已存在；请换一个文件名，或在获得覆盖授权后使用 --force。')
    body = args.body.read_text(encoding='utf-8')
    if '<main' not in body or '</main>' not in body:
        parser.error('正文需要包含 <main>…</main>；不要传入整份 HTML 文档。')
    validator = ChartValidator()
    validator.feed(body)
    validator.close()
    errors = validator.validate()
    if errors:
        parser.error('\n'.join(errors))
    assets = Path(__file__).resolve().parent.parent / 'assets'
    # 图形资源只在正文实际使用对应组件时加入；普通阅读页保持原有体积。
    extensions = []
    if 'hn-figure' in body:
        extensions.append('figure-tools')
    if 'hn-visual' in body:
        extensions.append('visuals')
    if 'hn-diagram' in body:
        extensions.append('diagrams')
    style_files = [name + '.css' for name in extensions]
    if 'hn-figure' in body or 'hn-plot' in body:
        # 逐图主题在 figure-tools 之后；只追加样式，不改变现有模板 API。
        insert_at = style_files.index('figure-tools.css') + 1 if 'figure-tools.css' in style_files else 0
        style_files.insert(insert_at, 'chart-theme.css')
    visual_styles = '\n'.join((assets / name).read_text(encoding='utf-8') for name in style_files)
    # 构建时写入固定映射，离线或无 JS 时同样保持领域颜色；不按行序自动取色。
    color_styles = '\n'.join(
        '.chart[data-chart="category"]>.chart-row[data-color="' + token + '"]{--series:' + color + ';}'
        for token, color in sorted(validator.explicit_colors.items()))
    visual_styles += '\n' + color_styles
    script_files = [name + '.js' for name in extensions]
    if validator.component_scripts_needed:
        script_files.append('components.js')
    visual_scripts = '\n'.join((assets / name).read_text(encoding='utf-8') for name in script_files)
    page = Template((assets / 'template.html').read_text(encoding='utf-8')).substitute(
        title=html.escape(args.title), body=body,
        fonts=(assets / 'fonts.css').read_text(encoding='utf-8'),
        styles=_tokens.render_css() + '\n' + (assets / 'haosunaki.css').read_text(encoding='utf-8'),
        visual_styles=visual_styles,
        visual_scripts=('<script>' + visual_scripts + '</script>') if script_files else '',
        licenses=(assets / 'font-licenses.html').read_text(encoding='utf-8'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # x 模式保证默认流程不会覆盖生成期间新出现的文件。
    with args.output.open('w' if args.force else 'x', encoding='utf-8') as file:
        file.write(page)
    print(args.output.resolve())


if __name__ == '__main__':
    main()
