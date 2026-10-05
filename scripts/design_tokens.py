"""读取 HaosuNaki 轻量 token 单源；仅使用标准库，不读业务材料、不写文件。

内部格式为 haosunaki.tokens.v1，不声称完整兼容 DTCG。
数值与单位分开：dimension 使用数字和 unit="px"，opacity / number 保持数字，
fontFamily 使用字体名称列表。别名仅使用完整值 "{语义名}"，不拼接表达式。
状态 confirmed / implementation / legacy 随原文保留，不参与值解析。

示例：
    token("surface.node")                         # "#FFFFFF"
    resolve_tokens()["type.component.body.size"]  # 15
    render_css()                                  # 页面变量及窄屏覆盖
    render_css(scope="svg.hn-chart", include_modes=False,
               names=["surface.node", "type.chart.label.size"])

JSON 中 tokens.<语义名>.css 是唯一的 CSS 映射表。命令行 --mapping 可只读查看。
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import re


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "assets" / "design-tokens.json"
_NAME = re.compile(r"[a-z][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)*")
_ALIAS = re.compile(r"\{([a-z][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)*)\}")
_CSS_NAME = re.compile(r"--[a-z][a-z0-9-]*")
_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
_MEDIA = re.compile(r"\((?:max|min)-width:\s*[0-9]+(?:\.[0-9]+)?px\)")
_TYPES = {"color", "dimension", "number", "opacity", "fontFamily"}
_GENERIC_FONTS = {"serif", "sans-serif", "monospace", "cursive", "fantasy",
                  "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace"}
_CATEGORY_NAMES = ("cobalt", "coral", "berry", "lake", "lavender", "tea")


def _unique_object(pairs):
    """在 JSON 变为字典前拒绝重复键，包括任意层级的模式覆盖。"""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON 存在重复键：{key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"JSON 不允许非有限数值：{value}")


def load_tokens(path=None) -> dict:
    """读取并校验 JSON 原文结构，保留别名、类型、状态、来源，不就地改写。"""
    document = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    validate_tokens(document)
    return document


def _value_valid(name, definition, value):
    kind = definition["type"]
    if kind == "color":
        if not isinstance(value, str) or not _COLOR.fullmatch(value):
            raise ValueError(f"{name}：颜色必须是六位十六进制 #RRGGBB")
    elif kind in {"dimension", "number", "opacity"}:
        if type(value) not in (int, float):
            raise ValueError(f"{name}：必须使用有限数字，不能使用布尔或带单位字符串")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError(f"{name}：数值必须有限")
        if kind == "dimension" and value < 0:
            raise ValueError(f"{name}：尺寸不能为负")
        if kind == "opacity" and not 0 <= value <= 1:
            raise ValueError(f"{name}：透明度必须位于 0 到 1")
    elif kind == "fontFamily":
        if not isinstance(value, list) or not value or any(
            not isinstance(font, str) or not font.strip()
            or any(ord(char) < 32 or char in "{};<>" for char in font)
            for font in value
        ):
            raise ValueError(f"{name}：字体栈必须是非空字体名称列表")


def _resolved(definitions, overrides=None):
    """按整份文档解析依赖；模式覆盖仍能传递到引用该值的语义 token。"""
    overrides = overrides or {}
    result, active = {}, []

    def visit(name):
        if name not in definitions:
            raise ValueError(f"未知 token 别名：{name}")
        if name in result:
            return result[name]
        if name in active:
            raise ValueError("循环 token 引用：" + " → ".join(active + [name]))
        definition = definitions[name]
        active.append(name)
        value = overrides.get(name, definition["value"])
        match = _ALIAS.fullmatch(value) if isinstance(value, str) else None
        if match:
            target = match.group(1)
            if target not in definitions:
                raise ValueError(f"{name} 引用了未知 token：{target}")
            other = definitions[target]
            if definition["type"] != other["type"] or definition.get("unit") != other.get("unit"):
                raise ValueError(f"{name} 与别名目标 {target} 的类型或单位不一致")
            value = visit(target)
        _value_valid(name, definition, value)
        result[name] = copy.deepcopy(value)
        active.pop()
        return result[name]

    for name in definitions:
        visit(name)
    return {name: result[name] for name in definitions}


def validate_tokens(document) -> None:
    """校验结构、CSS 唯一映射、值与全部模式；失败抛出 ValueError。"""
    if not isinstance(document, dict) or document.get("schema") != "haosunaki.tokens.v1":
        raise ValueError("文档 schema 必须是 haosunaki.tokens.v1")
    definitions = document.get("tokens")
    if not isinstance(definitions, dict) or not definitions:
        raise ValueError("tokens 必须是非空对象")
    css_seen = set()
    for name, definition in definitions.items():
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError(f"非法 token 名称：{name!r}")
        if not isinstance(definition, dict) or "value" not in definition:
            raise ValueError(f"{name}：token 必须有 value")
        kind = definition.get("type")
        if not isinstance(kind, str) or kind not in _TYPES:
            raise ValueError(f"{name}：不支持的 token 类型")
        status = definition.get("status")
        if not isinstance(status, str) or status not in {"confirmed", "implementation", "legacy"}:
            raise ValueError(f"{name}：缺少有效确认状态")
        if not isinstance(definition.get("description"), str) or not definition["description"].strip():
            raise ValueError(f"{name}：缺少中文用途说明")
        if kind == "dimension" and definition.get("unit") != "px":
            raise ValueError(f"{name}：dimension 的 unit 必须为 px")
        if kind != "dimension" and "unit" in definition:
            raise ValueError(f"{name}：此类型不能附加尺寸单位")
        if "css" in definition:
            css = definition["css"]
            if not isinstance(css, str) or not _CSS_NAME.fullmatch(css):
                raise ValueError(f"{name}：非法 CSS 变量名")
            if css in css_seen:
                raise ValueError(f"重复 CSS 变量映射：{css}")
            css_seen.add(css)
    _resolved(definitions)
    modes = document.get("modes", {})
    if not isinstance(modes, dict):
        raise ValueError("modes 必须是对象")
    for mode, settings in modes.items():
        if not isinstance(settings, dict):
            raise ValueError(f"模式 {mode} 必须是对象")
        media = settings.get("media")
        if not isinstance(media, str) or not _MEDIA.fullmatch(media):
            raise ValueError(f"模式 {mode} 需要有效的 min/max-width px 媒体条件")
        overrides = settings.get("overrides")
        if not isinstance(overrides, dict):
            raise ValueError(f"模式 {mode} 的 overrides 必须是对象")
        for name in overrides:
            if name not in definitions:
                raise ValueError(f"模式 {mode} 覆盖了不存在的 token：{name}")
        _resolved(definitions, overrides)


def _document(document):
    if document is None:
        return load_tokens()
    validate_tokens(document)
    return document


def resolve_tokens(document=None) -> dict:
    """返回桌面默认模式的扁平 name:value 字典；数值与字体列表保持原类型。"""
    return _resolved(_document(document)["tokens"])


def token(name):
    """从默认单源返回一个已解析值；未知名称抛出 KeyError。"""
    values = resolve_tokens()
    if name not in values:
        raise KeyError(f"未知 token：{name}")
    return values[name]


def palette() -> dict:
    """返回既有六个稳定分类色名到 hex；不把状态映射加入分类集合。"""
    values = resolve_tokens()
    return {name: values["category." + name] for name in _CATEGORY_NAMES}


def _css_value(definition, value):
    kind = definition["type"]
    if kind in {"dimension", "number", "opacity"}:
        result = format(value, ".12g")
        return result + "px" if kind == "dimension" else result
    if kind == "fontFamily":
        return ", ".join(font if font in _GENERIC_FONTS else json.dumps(font, ensure_ascii=False)
                         for font in value)
    return value


def render_css(document=None, scope=":root", include_modes=True, names=None) -> str:
    """输出带 css 映射的变量；按类型加 px、保留数值或生成字体栈。

    include_modes=False 用于几何固定的独立 SVG，避免随页面视口改字级。
    names 可给语义名白名单；只控制输出，不削弱整份文档校验或别名解析。
    未映射 css 的基础 token 永远不输出。模式仅输出与默认值不同的变量，
    包含因基础值覆盖而发生变化的语义引用。函数不写 CSS 文件。
    """
    if not isinstance(scope, str) or not scope.strip() or any(
        char in scope for char in "{};@<>\x00\n\r"
    ):
        raise ValueError("scope 必须是非空且不包含样式块或指令的 CSS 选择器")
    if not isinstance(include_modes, bool):
        raise ValueError("include_modes 必须是布尔值")
    document = _document(document)
    definitions = document["tokens"]
    selected = None
    if names is not None:
        if isinstance(names, str):
            raise ValueError("names 必须是 token 名称序列，不能是单一字符串")
        try:
            selected = set(names)
        except (TypeError, ValueError) as error:
            raise ValueError("names 必须是 token 名称序列") from error
        if any(not isinstance(name, str) or name not in definitions for name in selected):
            raise ValueError("names 含未知 token 名称")
    base = _resolved(definitions)

    def block(values, changed_only=False):
        lines = []
        for name, definition in definitions.items():
            if "css" not in definition or (selected is not None and name not in selected):
                continue
            if changed_only and values[name] == base[name]:
                continue
            lines.append(f"  {definition['css']}: {_css_value(definition, values[name])};")
        return scope + " {\n" + "\n".join(lines) + "\n}" if lines else ""

    sections = [block(base)]
    if include_modes:
        for settings in document.get("modes", {}).values():
            css = block(_resolved(definitions, settings["overrides"]), changed_only=True)
            if css:
                sections.append("@media " + settings["media"] + " {\n"
                                + "\n".join("  " + line for line in css.splitlines()) + "\n}")
    return "\n\n".join(section for section in sections if section) + ("\n" if any(sections) else "")


def _main():
    parser = argparse.ArgumentParser(description="只读校验或导出 HaosuNaki token。")
    parser.add_argument("--path", type=Path, help="替代 JSON 路径；默认使用相邻 assets 单源")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="校验全部值、别名和模式（默认）")
    action.add_argument("--css", action="store_true", help="向标准输出渲染 CSS")
    action.add_argument("--resolved", action="store_true", help="向标准输出解析后的值")
    action.add_argument("--mapping", action="store_true", help="向标准输出语义名到 CSS 的映射")
    parser.add_argument("--scope", default=":root")
    parser.add_argument("--no-modes", action="store_true")
    args = parser.parse_args()
    document = load_tokens(args.path)
    if args.css:
        print(render_css(document, args.scope, include_modes=not args.no_modes), end="")
    elif args.resolved:
        print(json.dumps(resolve_tokens(document), ensure_ascii=False, indent=2))
    elif args.mapping:
        print(json.dumps({name: item["css"] for name, item in document["tokens"].items()
                          if "css" in item}, ensure_ascii=False, indent=2))
    else:
        print(f"通过：{len(document['tokens'])} 个 token，{len(document.get('modes', {}))} 个模式。")


if __name__ == "__main__":
    _main()
