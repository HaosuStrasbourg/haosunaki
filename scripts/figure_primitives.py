"""小型静态 SVG 工具：bar、line、显式坐标 flow；Python 标准库，无网络。

颜色、输入和单位由调用方提供。返回完整 SVG 字符串，不读业务文件、不写文件。
默认嵌入同 skill 的已许可字体；Georgia/中文字体仅引用本机。详见接口文档。
"""
from pathlib import Path
from numbers import Real
import html
import math
import re
import unicodedata
import uuid

# 按本脚本位置加载同包参数，兼容直接 importlib 导入和命令行调用。
import importlib.util
_token_spec = importlib.util.spec_from_file_location('_hn_design_tokens', Path(__file__).with_name('design_tokens.py'))
_tokens = importlib.util.module_from_spec(_token_spec)
_token_spec.loader.exec_module(_tokens)

_STYLE = _tokens.resolve_tokens()
THEME = {k: _STYLE[v] for k,v in {
    'paper':'surface.figure', 'ink':'text.primary', 'muted':'text.secondary',
    'border':'border.default', 'emphasis':'surface.emphasis', 'focus':'accent.primary',
    **{c:'category.'+c for c in ('cobalt','coral','berry','lake','lavender','tea')}
}.items()}
CATEGORY_PALETTE = tuple(THEME[k] for k in ('cobalt', 'coral', 'lake', 'berry', 'tea', 'lavender'))
BLUE_SEQUENCE = tuple(_STYLE['scale.sequential.'+str(i)] for i in range(1,6))
LABEL_SIZE = _STYLE['type.chart.label.size']
LABEL_LINE = _STYLE['type.chart.label.line']
TITLE_SIZE = _STYLE['type.chart.title.size']
TITLE_LINE = _STYLE['type.chart.title.line']
NOTE_SIZE = _STYLE['type.chart.note.size']
NOTE_LINE = _STYLE['type.chart.note.line']
INLINE_NOTE_LINE = _STYLE['type.chart.note.inline-line']
NUMBER_SIZE = _STYLE['type.chart.number.size']

def _chart_tokens_css():
    wanted = [k for k in _STYLE if k.startswith(('surface.','text.','border.','font.component.','type.chart.','stroke.')) or k in ('font.number','accent.primary')]
    return _tokens.render_css(scope='svg.hn-chart', include_modes=False, names=wanted)

_ASSETS = Path(__file__).resolve().parents[1] / 'assets'


def _number(v, name='value'):
    if isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v):
        raise ValueError(f'{name} must be a finite number; use None for missing values')
    return float(v)


def _fmt(v):
    return f'{v:.12g}'


def _escape(v):
    return html.escape(str(v), quote=True)


def _color(v):
    if not isinstance(v, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', v):
        raise ValueError('Colors must be explicit six-digit hex values')
    return v


def _ids(rows):
    ids = [r['id'] for r in rows]
    if not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Each item needs a unique nonempty string id')
    return ids


def category_colors(domain, palette=CATEGORY_PALETTE):
    """只对完整稳定 domain 生成一次映射，随后跨图/筛选复用；不循环颜色。"""
    domain = list(domain)
    _ids([{'id': i} for i in domain])
    if len(domain) > len(palette):
        raise ValueError('Provide a distinct explicit palette for the full category domain')
    return dict(zip(domain, map(_color, palette)))


def _colors(ids, mode, color_map, focus_id):
    if mode == 'focus':
        if focus_id not in ids or color_map is not None:
            raise ValueError('focus needs one present focus_id and no color_map; use explicitsemantic for domain colors')
        return {i: THEME['focus'] if i == focus_id else THEME['muted'] for i in ids}
    if mode not in ('category', 'explicitsemantic'):
        raise ValueError('mode must be category, focus or explicitsemantic')
    if focus_id is not None or color_map is None or any(i not in color_map for i in ids):
        raise ValueError('Supply an explicit id→hex color_map covering all items; no focus_id')
    result = {i: _color(color_map[i]) for i in ids}
    if mode == 'category' and len(set(c.lower() for c in result.values())) != len(ids):
        raise ValueError('Equal categories need distinct colors; do not recycle a palette')
    return result


def text_width(text, size=LABEL_SIZE):
    """保守字宽估计，不是浏览器字体测量；英文按等宽，中文按全角。"""
    return sum(0 if unicodedata.combining(c) else size if unicodedata.east_asian_width(c) in 'WF' else size * .65 for c in str(text))


def wrap_label(text, max_width, size=LABEL_SIZE):
    """完整换行，不省略字符；保留显式换行，不把长词截成省略号。"""
    if max_width < size:
        raise ValueError('Label column too narrow for one glyph')
    output = []
    for paragraph in str(text).split('\n'):
        line = ''
        for char in paragraph:
            if line and text_width(line + char, size) > max_width:
                output.append(line); line = ''
            line += char
        output.append(line)
    return output


def linear_scale(domain, output):
    lo, hi = map(_number, domain); start, end = map(_number, output)
    if not lo < hi or not math.isfinite(hi-lo):
        raise ValueError('Scale domain must increase')
    return lambda v: start + (_number(v) - lo) / (hi - lo) * (end - start)


def nice_ticks(lo, hi, count=5):
    lo, hi = _number(lo), _number(hi)
    if not lo < hi or not math.isfinite(hi-lo) or count < 2:
        raise ValueError('Tick range must increase and count must be at least two')
    raw = (hi - lo) / (count - 1); power = 10 ** math.floor(math.log10(raw))
    step = next(m * power for m in (1, 2, 2.5, 5, 10) if m * power >= raw)
    a, b = math.floor(lo / step), math.ceil(hi / step)
    return [float(f'{i * step:.12g}') for i in range(a, b + 1)]


def _axis(values, domain=None, ticks=None, zero=False):
    values = list(values)
    if zero: values += [0]
    if domain is None:
        lo, hi = (min(values), max(values)) if values else (0, 1)
        if lo == hi:
            pad = abs(lo) * .1 or 1
            lo, hi = (0, pad) if zero and lo == 0 else (lo-pad, hi+pad)
        if ticks is None:
            ticks = nice_ticks(lo, hi); lo, hi = ticks[0], ticks[-1]
    else:
        lo, hi = map(_number, domain)
    if not lo < hi or any(v < lo or v > hi for v in values):
        raise ValueError('Domain must increase, contain all finite data, and include zero for bars')
    if ticks is None:
        ticks = [v for v in nice_ticks(lo, hi) if lo <= v <= hi]
    tick_pairs = [(_number(t[0]), str(t[1])) if isinstance(t, (tuple, list)) else (_number(t), _fmt(t)) for t in ticks]
    if not tick_pairs or any(not math.isfinite(v) or v < lo or v > hi for v, _ in tick_pairs):
        raise ValueError('Ticks must be finite and lie within the domain')
    if any(a[0] >= b[0] for a, b in zip(tick_pairs, tick_pairs[1:])):
        raise ValueError('Ticks must strictly increase')
    return (lo, hi), tick_pairs


class SVG:
    """共用纸白、五字体、grid/legend/caption；坐标由调用方明确给出。"""
    def __init__(self, width, height, title, desc, *, prefix=None, embed_fonts=True, flow_styles=False):
        self.width, self.height = _number(width), _number(height)
        if self.width <= 0 or self.height <= 0 or not title or not desc:
            raise ValueError('Positive dimensions, title and an equivalent desc are required')
        self.prefix = prefix or 'hnc-' + uuid.uuid4().hex
        if not re.fullmatch(r'[A-Za-z][\w-]*', self.prefix):
            raise ValueError('prefix must be an XML-safe unique identifier')
        p = self.prefix
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" class="hn-chart" width="{_fmt(self.width)}" height="{_fmt(self.height)}" viewBox="0 0 {_fmt(self.width)} {_fmt(self.height)}" role="img" aria-labelledby="{p}-title {p}-desc">', f'<title id="{p}-title">{_escape(title)}</title><desc id="{p}-desc">{_escape(desc)}</desc>']
        # 静态 SVG 在生成时固化参数，兼容不支持 CSS 变量的图片渲染器。
        # 页面仍使用动态 CSS 变量；更换主题后重新生成 SVG。
        variables = dict(re.findall(r'(--[\w-]+):\s*([^;]+);', _chart_tokens_css()))
        css = re.sub(r'var\((--[\w-]+)\)', lambda m: variables[m.group(1)],
                     (_ASSETS / 'chart-theme.css').read_text())
        if not flow_styles:
            css = css.split('/* HNC FLOW SHAPES:', 1)[0]
        if embed_fonts:
            font = (_ASSETS / 'fonts.css').read_text()
            css += '\n' + '\n'.join(b for b in re.findall(r'@font-face\s*\{[^}]+\}', font) if re.search(r'font-weight:\s*400\s*;', b))
            self.parts.append('<metadata>' + _escape((_ASSETS/'font-licenses.html').read_text()) + '</metadata>')
        self.parts.append('<style>' + css + '</style>')
        self.rect(0, 0, width, height, THEME['paper'])

    def text(self, x, y, text, *, role='label', max_width=None, anchor='start', line_height=None):
        if role not in ('title', 'label', 'note', 'number') or anchor not in ('start', 'middle', 'end'):
            raise ValueError('Unknown text role or anchor')
        if line_height is None:
            line_height = INLINE_NOTE_LINE if role == 'note' else LABEL_LINE
        lines = wrap_label(text, max_width, {'title':TITLE_SIZE,'label':LABEL_SIZE,'note':NOTE_SIZE,'number':NUMBER_SIZE}[role]) if max_width else str(text).split('\n')
        spans = ''.join(f'<tspan x="{_fmt(x)}" dy="{0 if i == 0 else line_height}">{_escape(t)}</tspan>' for i, t in enumerate(lines))
        self.parts.append(f'<text class="hnc-{role}" x="{_fmt(x)}" y="{_fmt(y)}" text-anchor="{anchor}" xml:space="preserve">{spans}</text>')
        return y + (len(lines) - 1) * line_height

    def rect(self, x, y, width, height, fill, *, stroke=None, attrs=''):
        if any(not math.isfinite(v) for v in (x,y,width,height)) or min(width,height) < 0:
            raise ValueError('Invalid rectangle geometry')
        self.parts.append(f'<rect x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(width)}" height="{_fmt(height)}" fill="{_color(fill)}"' + (f' stroke="{_color(stroke)}"' if stroke else '') + f' {attrs}/>')

    def segment(self, x1, y1, x2, y2, *, color=None, width=1, css=None):
        if any(not math.isfinite(v) for v in (x1,y1,x2,y2)):
            raise ValueError('Invalid line geometry')
        self.parts.append(f'<line x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(x2)}" y2="{_fmt(y2)}"' + (f' class="hnc-{css}"' if css else f' stroke="{_color(color or THEME["ink"])}" stroke-width="{width}"') + '/>')

    def grid(self, ticks, scale, start, end, *, vertical=False):
        """ticks 即显示刻度，不额外补密线；按显示顺序交替主次，实零更强。"""
        for i, (v, label) in enumerate(ticks):
            c = 'baseline' if v == 0 else 'major' if i % 2 == 0 else 'minor'
            q = scale(v)
            if vertical: self.segment(q, start, q, end, css=c)
            else: self.segment(start, q, end, q, css=c)
            axis='x' if vertical else 'y'
            self.parts[-1]=self.parts[-1].replace('<line ',f'<line data-role="grid-{axis}" data-value="{_fmt(v)}" ',1)

    def legend(self, items, x, y, max_width):
        """items=[(label,hex)]；紧凑逐项换行，返回下一段起始 y。"""
        cur, row_height = x, LABEL_LINE
        for label, color in items:
            w = min(max_width, text_width(label) + 42)
            lines = wrap_label(label, w - 34)
            if cur > x and cur + w > x + max_width:
                y += row_height + 8; cur = x; row_height = LABEL_LINE
            self.segment(cur, y-5, cur+22, y-5, color=color, width=2.4)
            self.text(cur+30, y, '\n'.join(lines))
            row_height = max(row_height, len(lines)*LABEL_LINE); cur += w + 16
        return y + row_height + 10

    def caption(self, text, x, y, max_width):
        return self.text(x, y, text, role='note', max_width=max_width, line_height=NOTE_LINE) + 16 if text else y

    def render(self):
        return '\n'.join(self.parts + ['</svg>'])


def _header(title, unit, width):
    lines = wrap_label(title, width-48, TITLE_SIZE)
    return 35 + (len(lines)-1)*TITLE_LINE + (29 if unit else 0) + 30


def _head(svg, title, unit):
    end = svg.text(24, 35, title, role='title', max_width=svg.width-48, line_height=TITLE_LINE)
    if unit: svg.text(24, end+29, unit, role='note')


def _foot_height(caption, width):
    return len(wrap_label(caption, width-48, NOTE_SIZE))*NOTE_LINE+24 if caption else 16


def _geometry(svg, kind, **values):
    # Public numeric metadata lets a caller update the existing geometry with the same scales.
    attrs={'chart-kind':kind, **{k.replace('_','-'):_fmt(v) for k,v in values.items()}}
    svg.parts[0]=svg.parts[0][:-1]+''.join(f' data-{k}="{_escape(v)}"' for k,v in attrs.items())+'>'


def _tick_data(svg, axis, value):
    svg.parts[-1]=svg.parts[-1].replace('<text ',f'<text data-role="axis-{axis}-tick" data-value="{_fmt(value)}" ',1)


def bar(rows, *, title, desc, mode, color_map=None, focus_id=None, orientation='horizontal',
        width=900, unit='', caption='', domain=None, ticks=None, value_format=None, prefix=None):
    """rows=[{id,label,value}]；value=None 显式缺失，零值不缺失。"""
    rows = list(rows); ids = _ids(rows)
    if not rows or orientation not in ('horizontal', 'vertical') or width < 480:
        raise ValueError('Need rows, horizontal/vertical orientation, and width>=480')
    colors = _colors(ids, mode, color_map, focus_id)
    values = [None if r['value'] is None else _number(r['value']) for r in rows]
    domain, ticks = _axis([v for v in values if v is not None], domain, ticks, zero=True)
    formatter = value_format or _fmt
    top = _header(title, unit, width)
    if orientation == 'horizontal':
        label_width = min(200, width*.25); left, right = label_width+40, width-115
        labels = [wrap_label(r.get('label',r['id']), label_width) for r in rows]
        heights = [max(44, len(t)*LABEL_LINE+12) for t in labels]; bottom = top+sum(heights)
        height = bottom+52+_foot_height(caption,width)
        svg = SVG(width,height,title,desc,prefix=prefix); _head(svg,title,unit)
        _geometry(svg,'bar-horizontal',value_min=domain[0],value_max=domain[1],plot_left=left,plot_top=top,plot_width=right-left,plot_height=bottom-top)
        scale = linear_scale(domain,(left,right)); svg.grid(ticks,scale,top,bottom,vertical=True)
        y = top
        for r,v,label,h in zip(rows,values,labels,heights):
            cy=y+h/2
            svg.text(left-18,cy+5-(len(label)-1)*LABEL_LINE/2,'\n'.join(label),anchor='end')
            if v is not None:
                a,b=sorted([scale(0),scale(v)])
                svg.rect(a,cy-10,b-a,20,colors[r['id']],attrs=f'data-id="{_escape(r["id"])}" data-value="{_fmt(v)}"')
                if v == 0: svg.segment(a,cy-8,a,cy+8,color=colors[r['id']],width=2)
            svg.text(width-24,cy+5,'未提供' if v is None else formatter(v),role='note' if v is None else 'number',anchor='end')
            y+=h
        svg.segment(scale(0),top,scale(0),bottom,css='baseline')
        for v,label in ticks: svg.text(scale(v),bottom+26,label,role='number',anchor='middle')
        svg.caption(caption,24,bottom+52,width-48)
    else:
        width=max(width,112+len(rows)*64); top=_header(title,unit,width)
        left,right,bottom=80,width-32,top+300; band=(right-left)/len(rows)
        labels=[wrap_label(r.get('label',r['id']),band-12) for r in rows]
        label_bottom=bottom+48+(max(map(len,labels))-1)*LABEL_LINE
        height=label_bottom+24+_foot_height(caption,width)
        svg=SVG(width,height,title,desc,prefix=prefix);_head(svg,title,unit)
        _geometry(svg,'bar-vertical',value_min=domain[0],value_max=domain[1],plot_left=left,plot_top=top,plot_width=right-left,plot_height=bottom-top)
        scale=linear_scale(domain,(bottom,top));svg.grid(ticks,scale,left,right)
        for v,label in ticks:svg.text(left-12,scale(v)+5,label,role='number',anchor='end')
        for i,(r,v,label) in enumerate(zip(rows,values,labels)):
            cx=left+(i+.5)*band
            if v is not None:
                a,b=sorted([scale(0),scale(v)]);bw=min(44,band*.65)
                svg.rect(cx-bw/2,a,bw,b-a,colors[r['id']],attrs=f'data-id="{_escape(r["id"])}" data-value="{_fmt(v)}"')
                if v == 0:svg.segment(cx-8,a,cx+8,a,color=colors[r['id']],width=2)
                svg.text(cx,scale(v)-9 if v>=0 else scale(v)+19,formatter(v),role='number',anchor='middle')
            else:svg.text(cx,top+150,'未提供',role='note',anchor='middle')
            svg.text(cx,bottom+48,'\n'.join(label),anchor='middle')
        svg.segment(left,scale(0),right,scale(0),css='baseline')
        svg.caption(caption,24,label_bottom+26,width-48)
    return svg.render()


def line(series, *, title, desc, mode, color_map=None, focus_id=None, width=900,
         x_label='', y_label='', caption='', x_domain=None, y_domain=None,
         x_ticks=None, y_ticks=None, prefix=None):
    """series=[{id,label,points:[(numeric_x,numeric_y_or_None),...]}]。
    x 必须严格递增；None 结束当前段。孤立有效点仍显示，不平滑、不补点。
    """
    series=list(series); ids=_ids(series)
    if not series or width<480:raise ValueError('Need series and width>=480')
    colors=_colors(ids,mode,color_map,focus_id);parsed=[]
    for s in series:
        points=[(_number(x,'x'),None if y is None else _number(y,'y')) for x,y in s['points']]
        if not points or any(a[0]>=b[0] for a,b in zip(points,points[1:])):
            raise ValueError('Each series needs points with strictly increasing numeric x; include explicit None gaps')
        parsed.append(points)
    xd,xt=_axis([x for p in parsed for x,y in p],x_domain,x_ticks)
    yd,yt=_axis([y for p in parsed for x,y in p if y is not None],y_domain,y_ticks)
    # Legend uses the same wrapping routine as final output; reserve its true height.
    top0=_header(title,'',width)
    probe=SVG(width,100,title,desc,embed_fonts=False)
    legend=[(s.get('label',s['id'])+('（全部缺失）' if all(y is None for x,y in p) else ''),colors[s['id']])for s,p in zip(series,parsed)]
    ylines=wrap_label(y_label,width-112,NOTE_SIZE)
    xlines=wrap_label(x_label,width-112)
    top=probe.legend(legend,80,top0,width-112)+max(INLINE_NOTE_LINE,len(ylines)*INLINE_NOTE_LINE)
    left,right,bottom=80,width-32,top+300
    note=caption
    if any(y is None for p in parsed for x,y in p):note+=('；'if note else '')+'缺失值不连线，未补值。'
    caption_y=bottom+79+(len(xlines)-1)*LABEL_LINE
    height=caption_y+_foot_height(note,width)
    svg=SVG(width,height,title,desc,prefix=prefix);_head(svg,title,'');svg.legend(legend,80,top0,width-112)
    _geometry(svg,'line',x_min=xd[0],x_max=xd[1],y_min=yd[0],y_max=yd[1],plot_left=left,plot_top=top,plot_width=right-left,plot_height=bottom-top)
    xs,ys=linear_scale(xd,(left,right)),linear_scale(yd,(bottom,top))
    svg.grid(yt,ys,left,right);svg.grid(xt,xs,top,bottom,vertical=True)
    for v,t in yt:
        svg.text(left-12,ys(v)+5,t,role='number',anchor='end');_tick_data(svg,'y',v)
    for v,t in xt:
        svg.text(xs(v),bottom+26,t,role='number',anchor='middle');_tick_data(svg,'x',v)
    svg.text(left,top-len(ylines)*INLINE_NOTE_LINE+10,'\n'.join(ylines),role='note')
    svg.text((left+right)/2,bottom+53,'\n'.join(xlines),role='label',anchor='middle')
    for s,points in zip(series,parsed):
        segment=[];segments=[]
        for x,y in points:
            if y is None:
                if segment:segments.append(segment);segment=[]
            else:segment.append((x,y))
        if segment:segments.append(segment)
        for segment_index,seg in enumerate(segments):
            path=' '.join(('M'if i==0 else'L')+_fmt(xs(x))+','+_fmt(ys(y))for i,(x,y)in enumerate(seg))
            svg.parts.append(f'<path d="{path}" fill="none" stroke="{colors[s["id"]]}" stroke-width="2" data-role="series-segment" data-series="{_escape(s["id"])}" data-segment-index="{segment_index}" data-points="{len(seg)}"/>')
        for x,y in points:
            if y is not None:svg.parts.append(f'<circle cx="{_fmt(xs(x))}" cy="{_fmt(ys(y))}" r="3" fill="{colors[s["id"]]}" data-role="series-point" data-series="{_escape(s["id"])}" data-x="{_fmt(x)}" data-y="{_fmt(y)}"/>')
    svg.caption(note,24,caption_y,width-48)
    return svg.render()


def _port(node, toward):
    x,y,w,h=node['x'],node['y'],node['width'],node['height'];cx,cy=x+w/2,y+h/2
    dx,dy=toward[0]-cx,toward[1]-cy
    if not dx and not dy:raise ValueError('Edge has no direction; provide route points')
    shape=node.get('shape','process')
    if shape=='decision':
        t=1/(abs(dx)/(w/2)+abs(dy)/(h/2))
    elif shape=='terminal':
        radius=h/2
        flat_t=radius/abs(dy) if dy else math.inf
        if math.isfinite(flat_t) and x+radius<=cx+dx*flat_t<=x+w-radius:
            t=flat_t
        else:
            offset=math.copysign((w-h)/2,dx)
            a=dx*dx+dy*dy;b=-2*dx*offset;c=offset*offset-radius*radius
            t=(-b+math.sqrt(max(0,b*b-4*a*c)))/(2*a)
    else:
        t=min(w/2/abs(dx)if dx else math.inf,h/2/abs(dy)if dy else math.inf)
    return cx+dx*t,cy+dy*t


def _crosses(a,b,n):
    shape=n.get('shape','process')
    if shape=='decision':
        # Clip against the four true diamond half-planes, not its empty bounding corners.
        cx,cy=n['x']+n['width']/2,n['y']+n['height']/2
        lo,hi=0.,1.
        for sx,sy in [(1,1),(1,-1),(-1,1),(-1,-1)]:
            v=sx*(a[0]-cx)/(n['width']/2)+sy*(a[1]-cy)/(n['height']/2)
            d=sx*(b[0]-a[0])/(n['width']/2)+sy*(b[1]-a[1])/(n['height']/2)
            bound=1-1e-9-v
            if not d:
                if bound<=0:return False
            elif d>0:hi=min(hi,bound/d)
            else:lo=max(lo,bound/d)
        return lo<hi and hi>0 and lo<1
    if shape=='terminal':
        r=n['height']/2;cy=n['y']+r
        middle=dict(n,x=n['x']+r,width=n['width']-2*r,shape='process')
        if middle['width']>0 and _crosses(a,b,middle):return True
        dx,dy=b[0]-a[0],b[1]-a[1];length2=dx*dx+dy*dy
        if not length2:return False
        for cx in [n['x']+r,n['x']+n['width']-r]:
            t=max(0,min(1,((cx-a[0])*dx+(cy-a[1])*dy)/length2))
            if (a[0]+t*dx-cx)**2+(a[1]+t*dy-cy)**2<(r-1e-7)**2:return True
        return False
    # Open interior slab intersection; touching a border is allowed.
    lo,hi=0.,1.
    for start,end,mn,mx in [(a[0],b[0],n['x']+1e-7,n['x']+n['width']-1e-7),(a[1],b[1],n['y']+1e-7,n['y']+n['height']-1e-7)]:
        d=end-start
        if not d:
            if not mn<start<mx:return False
        else:
            t1,t2=sorted(((mn-start)/d,(mx-start)/d));lo=max(lo,t1);hi=min(hi,t2)
    return lo<hi and hi>0 and lo<1


def flow(nodes, edges, *, title, desc, width=900, caption='', prefix=None, junctions=()):
    """显式绝对坐标机制图；node普通白底中性边，emphasis=True才浅蓝。
    shape: process(默认)、decision(真菱形)、terminal(胶囊，需terminal_kind=start/end)。
    terminal_label 可覆盖默认“起点/终点”，例如当前任务的“本轮开始/本轮结束”。
    terminal_fill/terminal_border 为可选显式角色色；不提供时仍中性。
    number 可选，放左上且不替换名称；有编号时自动保留编号区。
    edge points 为可选中间路点；首尾接实际形状边界。不自动推导布局或因果。
    决策文字限制于中央安全矩形；字宽仍为估计，需实际预览。
    junctions 为显式连接点坐标；至少两条边须经过该点，不推断交叉即连接。
    """
    nodes=[dict(n)for n in nodes];edges=list(edges);ids=_ids(nodes)
    if not nodes or width<480:raise ValueError('Need nodes and width>=480')
    header=_header(title,'',width)
    for n in nodes:
        for key in ['x','y','width']:n[key]=_number(n[key],key)
        if n['width']<64:raise ValueError('Node width must be at least64')
        shape=n.get('shape','process')
        if shape not in ('process','decision','terminal'):raise ValueError('Unknown flow node shape')
        number=n.get('number')
        if number is not None and (not str(number).strip() or text_width(str(number))>min(48,n['width']*.18)):
            raise ValueError('Node number must be a short nonempty label; keep its name separately')
        if shape=='terminal' and n.get('terminal_kind')not in ('start','end'):
            raise ValueError('terminal nodes require terminal_kind=start or end')
        if shape=='terminal':
            terminal_label=n.get('terminal_label','起点'if n['terminal_kind']=='start'else'终点')
            if not isinstance(terminal_label,str) or not terminal_label.strip() or '\n'in terminal_label or text_width(terminal_label)>n['width']-80:
                raise ValueError('terminal_label must be a short single-line label leaving room for the number')
            for field in ('terminal_fill','terminal_border'):
                if field in n:_color(n[field])
        elif 'terminal_fill'in n or 'terminal_border'in n:
            raise ValueError('Terminal role colors apply only to terminal shapes')
        text_width_limit=n['width']*.44 if shape=='decision' else n['width']-40 if shape=='terminal' else n['width']-24
        n['lines']=wrap_label(n.get('label',n['id']),text_width_limit)
        if shape=='decision':minimum=max(120 if number is not None else 80,len(n['lines'])*LABEL_LINE/.44+24)
        else:minimum=len(n['lines'])*LABEL_LINE+24+(20 if number is not None or shape=='terminal' else 0)
        n['height']=_number(n.get('height',minimum),'height')
        if shape=='terminal' and n['width']<n['height']:raise ValueError('Terminal capsule width must be at least its height')
        if n['height']<minimum or n['x']<16 or n['y']<header or n['x']+n['width']>width-16:
            raise ValueError('Node clips text/header/page; enlarge or move the explicit geometry')
    lookup={n['id']:n for n in nodes}
    for i,a in enumerate(nodes):
        for b in nodes[i+1:]:
            if a['x']<b['x']+b['width'] and b['x']<a['x']+a['width'] and a['y']<b['y']+b['height'] and b['y']<a['y']+a['height']:
                raise ValueError('Nodes overlap; provide separate explicit coordinates')
    routes=[];content_bottom=max(n['y']+n['height'] for n in nodes)
    for e in edges:
        if e['source']not in lookup or e['target']not in lookup:raise ValueError('Edge refers to an unknown node')
        a,b=lookup[e['source']],lookup[e['target']]
        middle=[(_number(x),_number(y))for x,y in e.get('points',[])]
        ac=(a['x']+a['width']/2,a['y']+a['height']/2);bc=(b['x']+b['width']/2,b['y']+b['height']/2)
        points=[_port(a,middle[0]if middle else bc)]+middle+[_port(b,middle[-1]if middle else ac)]
        if any(x<8 or x>width-8 or y<header for x,y in points):raise ValueError('Edge route leaves the drawable region')
        if any(_crosses(p,q,n)for p,q in zip(points,points[1:])for n in nodes):
            raise ValueError('Edge crosses a node interior; give explicit points around it')
        label=e.get('label','');label_lines=wrap_label(label,160,NOTE_SIZE)if label else[]
        mid=points[len(points)//2]if len(points)>2 else((points[0][0]+points[1][0])/2,(points[0][1]+points[1][1])/2)
        lx,ly=map(_number,e.get('label_position',(mid[0],mid[1]-12)))
        if label:
            lw=max(text_width(t,NOTE_SIZE)for t in label_lines)+12;lh=len(label_lines)*INLINE_NOTE_LINE
            box={'x':lx-lw/2,'y':ly-15,'width':lw,'height':lh}
            if box['x']<0 or box['x']+lw>width or box['y']<header:raise ValueError('Edge label leaves the drawable region')
            if any(box['x']<n['x']+n['width'] and n['x']<box['x']+lw and box['y']<n['y']+n['height'] and n['y']<box['y']+lh for n in nodes):
                raise ValueError('Edge label overlaps a node; set label_position')
            content_bottom=max(content_bottom,box['y']+lh)
        content_bottom=max(content_bottom,max(y for x,y in points));routes.append((e,points,label_lines,lx,ly))
    junctions=[(_number(x),_number(y))for x,y in junctions]
    if len(set(junctions))!=len(junctions):raise ValueError('Junction coordinates must be unique')
    for jx,jy in junctions:
        connected=0
        for e,points,label,lx,ly in routes:
            for (ax,ay),(bx,by) in zip(points,points[1:]):
                cross=(jx-ax)*(by-ay)-(jy-ay)*(bx-ax)
                if abs(cross)<1e-7 and min(ax,bx)-1e-7<=jx<=max(ax,bx)+1e-7 and min(ay,by)-1e-7<=jy<=max(ay,by)+1e-7:
                    connected+=1;break
        if connected<2 or any(n['x']-3<jx<n['x']+n['width']+3 and n['y']-3<jy<n['y']+n['height']+3 for n in nodes):
            raise ValueError('Junction must lie on at least two routes and outside node boundaries')
    bottom=content_bottom+28;height=bottom+_foot_height(caption,width)
    enhanced=bool(junctions) or any(n.get('shape','process')!='process' or n.get('number')is not None for n in nodes)
    svg=SVG(width,height,title,desc,prefix=prefix,flow_styles=enhanced);_head(svg,title,'')
    marker=svg.prefix+'-arrow'
    svg.parts.append(f'<defs><marker id="{marker}" viewBox="0 0 8 8" refX="8" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 Z" fill="{THEME["muted"]}"/></marker></defs>')
    for e,points,label,lx,ly in routes:
        path=' '.join(('M'if i==0 else'L')+_fmt(x)+','+_fmt(y)for i,(x,y)in enumerate(points))
        svg.parts.append(f'<path class="hnc-edge" d="{path}" marker-end="url(#{marker})" data-source="{_escape(e["source"])}" data-target="{_escape(e["target"])}"/>')
        if label:
            lw=max(text_width(t,NOTE_SIZE)for t in label)+12
            svg.rect(lx-lw/2,ly-15,lw,len(label)*INLINE_NOTE_LINE,THEME['paper']);svg.text(lx,ly,'\n'.join(label),anchor='middle',role='note')
    for x,y in junctions:
        svg.parts.append(f'<circle class="hnc-junction" cx="{_fmt(x)}" cy="{_fmt(y)}" r="3" data-junction="true"/>')
    for n in nodes:
        c='hnc-emphasis'if n.get('emphasis',False)else'hnc-node'
        x,y,w,h=n['x'],n['y'],n['width'],n['height'];shape=n.get('shape','process');number=n.get('number')
        if shape=='decision':
            vertices=[(x+w/2,y),(x+w,y+h/2),(x+w/2,y+h),(x,y+h/2)]
            svg.parts.append(f'<polygon class="{c}" points="'+ ' '.join(_fmt(px)+','+_fmt(py)for px,py in vertices)+f'" data-node="{_escape(n["id"])}" data-shape="decision"/>')
        elif shape=='terminal':
            kind=n['terminal_kind'];c+=' hnc-terminal-'+kind
            tone=[]
            if 'terminal_fill'in n:tone.append('fill:'+n['terminal_fill'])
            if 'terminal_border'in n:tone.append('stroke:'+n['terminal_border'])
            tone_attr=' style="'+';'.join(tone)+'"'if tone else''
            svg.parts.append(f'<rect class="{c}" x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(w)}" height="{_fmt(h)}" rx="{_fmt(h/2)}" data-node="{_escape(n["id"])}" data-shape="terminal" data-terminal-kind="{kind}"{tone_attr}/>')
        else:
            svg.parts.append(f'<rect class="{c}" x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(w)}" height="{_fmt(h)}" rx="6" data-node="{_escape(n["id"])}"/>')
        if number is not None:
            nx,ny=(x+w*.30,y+h*.32)if shape=='decision'else(x+max(16,h*.22),y+20)if shape=='terminal'else(x+12,y+20)
            svg.parts.append(f'<text class="hnc-node-number" x="{_fmt(nx)}" y="{_fmt(ny)}" data-number-for="{_escape(n["id"])}">{_escape(number)}</text>')
        if shape=='terminal':
            terminal_label=n.get('terminal_label','起点'if n['terminal_kind']=='start'else'终点')
            svg.parts.append(f'<text class="hnc-terminal-kind" x="{_fmt(x+w-max(16,h*.22))}" y="{_fmt(y+20)}" text-anchor="end">'+_escape(terminal_label)+'</text>')
        offset=20 if shape!='decision' and (number is not None or shape=='terminal') else 0
        svg.text(x+w/2,y+offset+(h-offset-len(n['lines'])*LABEL_LINE)/2+15,'\n'.join(n['lines']),anchor='middle')
    svg.caption(caption,24,bottom,width-48)
    return svg.render()
