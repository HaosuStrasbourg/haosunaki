"""核心接口的行为测试；仅标准库，不联网，不依赖示例或原机路径。"""
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


figures = load_script("figure_primitives")
tokens = load_script("design_tokens")


def parse_svg(svg):
    return ET.fromstring(svg)


def path_points(path):
    """读取输出中的直线路径，不重算生成器的比例尺或端口算法。"""
    return [(float(x), float(y)) for x, y in re.findall(r"[ML]([^, ]+),([^ ]+)", path)]


class FigureTests(unittest.TestCase):
    def test_bar_preserves_negative_zero_and_missing_values(self):
        rows = [
            {"id": "negative", "value": -2},
            {"id": "positive", "value": 4},
            {"id": "zero", "value": 0},
            {"id": "missing", "value": None},
        ]
        colors = figures.category_colors([row["id"] for row in rows])
        for orientation in ("horizontal", "vertical"):
            with self.subTest(orientation=orientation):
                root = parse_svg(figures.bar(
                    rows, title="负数、零和缺失", desc="合成数据。", mode="category",
                    color_map=colors, orientation=orientation,
                    domain=(-4, 4), ticks=[-4, 0, 4], prefix="bar-values"))
                bars = {node.get("data-id"): node for node in root.findall("svg:rect", SVG_NS)
                        if node.get("data-id") is not None}
                self.assertEqual(set(bars), {"negative", "positive", "zero"})
                self.assertIn("未提供", "".join(root.itertext()))
                baseline = root.findall("svg:line[@class='hnc-baseline']", SVG_NS)[-1]
                negative, positive, zero = (bars[key] for key in ("negative", "positive", "zero"))
                if orientation == "horizontal":
                    origin = float(baseline.get("x1"))
                    self.assertLess(float(negative.get("x")), origin)
                    self.assertAlmostEqual(float(negative.get("x")) + float(negative.get("width")), origin)
                    self.assertAlmostEqual(float(positive.get("x")), origin)
                    size = "width"
                else:
                    origin = float(baseline.get("y1"))
                    self.assertAlmostEqual(float(negative.get("y")), origin)
                    self.assertLess(float(positive.get("y")), origin)
                    self.assertAlmostEqual(float(positive.get("y")) + float(positive.get("height")), origin)
                    size = "height"
                self.assertAlmostEqual(float(positive.get(size)), 2 * float(negative.get(size)))
                self.assertEqual(float(zero.get(size)), 0)
                self.assertEqual(zero.get("data-value"), "0")
                # 实零另有可见短线；缺失项没有柱形或零标记。
                markers = root.findall("svg:line[@stroke='" + colors["zero"] + "']", SVG_NS)
                self.assertEqual(len(markers), 1)
                self.assertNotEqual(markers[0].get("x1") + markers[0].get("y1"),
                                    markers[0].get("x2") + markers[0].get("y2"))

    def test_bar_rejects_nonfinite_and_non_numeric_values(self):
        for value in (float("nan"), float("inf"), -float("inf"), True, "2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                figures.bar([{"id": "a", "value": value}], title="校验", desc="合成数据。",
                            mode="focus", focus_id="a")

    def test_category_colors_follow_ids_after_reordering_and_filtering(self):
        colors = figures.category_colors(["a", "b", "c"])
        for ids in (["a", "b", "c"], ["c", "a", "b"], ["c", "a"]):
            with self.subTest(ids=ids):
                bar_root = parse_svg(figures.bar(
                    [{"id": key, "value": 2} for key in ids],
                    title="分类", desc="合成数据。", mode="category", color_map=colors))
                actual = {node.get("data-id"): node.get("fill")
                          for node in bar_root.findall("svg:rect", SVG_NS)
                          if node.get("data-id") is not None}
                self.assertEqual(actual, {key: colors[key] for key in ids})
                line_root = parse_svg(figures.line(
                    [{"id": key, "points": [(0, 1), (1, 2)]} for key in ids],
                    title="分类", desc="合成数据。", mode="category", color_map=colors))
                actual = {node.get("data-series"): node.get("stroke")
                          for node in line_root.findall("svg:path[@data-role='series-segment']", SVG_NS)}
                self.assertEqual(actual, {key: colors[key] for key in ids})

    def test_line_none_breaks_paths_and_keeps_isolated_point(self):
        root = parse_svg(figures.line(
            [{"id": "a", "points": [(0, 1), (1, 2), (2, None), (3, 3),
                                     (4, 4), (5, None), (6, 5)]}],
            title="缺失断段", desc="合成数据。", mode="focus", focus_id="a"))
        segments = root.findall("svg:path[@data-role='series-segment']", SVG_NS)
        points = root.findall("svg:circle[@data-role='series-point']", SVG_NS)
        self.assertEqual([node.get("data-points") for node in segments], ["2", "2", "1"])
        self.assertEqual([node.get("data-x") for node in points], ["0", "1", "3", "4", "6"])
        positions = {node.get("data-x"): (float(node.get("cx")), float(node.get("cy")))
                     for node in points}
        for segment, xs in zip(segments, [("0", "1"), ("3", "4"), ("6",)]):
            self.assertEqual(path_points(segment.get("d")), [positions[x] for x in xs])
        self.assertIn("缺失值不连线", "".join(root.itertext()))

    def test_line_rejects_invalid_coordinates(self):
        cases = [(None, 1), (float("nan"), 1), (0, float("nan")),
                 (float("inf"), 1), (0, -float("inf"))]
        for point in cases:
            with self.subTest(point=point), self.assertRaises(ValueError):
                figures.line([{"id": "a", "points": [point]}],
                             title="校验", desc="合成数据。", mode="focus", focus_id="a")

    @staticmethod
    def flow_nodes():
        return [
            {"id": "start", "shape": "terminal", "terminal_kind": "start",
             "label": "输入", "x": 40, "y": 110, "width": 180, "height": 80},
            {"id": "process", "label": "处理", "x": 350, "y": 110, "width": 180, "height": 80},
            {"id": "end", "shape": "terminal", "terminal_kind": "end",
             "label": "输出", "x": 660, "y": 110, "width": 180, "height": 80},
        ]

    def test_flow_start_end_and_boundary_ports(self):
        root = parse_svg(figures.flow(
            self.flow_nodes(), [{"source": "start", "target": "process"},
                                {"source": "process", "target": "end"}],
            title="流程", desc="合成流程。", prefix="flow-ports"))
        terminals = root.findall("svg:rect[@data-shape='terminal']", SVG_NS)
        self.assertEqual([node.get("data-terminal-kind") for node in terminals], ["start", "end"])
        self.assertEqual([node.text for node in root.findall("svg:text[@class='hnc-terminal-kind']", SVG_NS)],
                         ["起点", "终点"])
        edges = root.findall("svg:path[@class='hnc-edge']", SVG_NS)
        self.assertEqual([path_points(node.get("d")) for node in edges],
                         [[(220, 150), (350, 150)], [(530, 150), (660, 150)]])
        self.assertTrue(all(node.get("marker-end") == "url(#flow-ports-arrow)" for node in edges))

    def test_svg_styles_are_resolved_for_renderers_without_css_variables(self):
        nodes = self.flow_nodes()
        nodes[1]["emphasis"] = True
        outputs = {
            "flow": figures.flow(nodes, [{"source": "start", "target": "process"}],
                                 title="静态样式", desc="普通和强调节点。"),
            "bar": figures.bar([{"id": "a", "value": 2}], title="静态样式", desc="合成数据。",
                               mode="focus", focus_id="a"),
            "line": figures.line([{"id": "a", "points": [(0, 0), (1, 2)]}],
                                 title="静态样式", desc="合成数据。", mode="focus", focus_id="a"),
        }
        resolved = tokens.resolve_tokens()
        for kind, output in outputs.items():
            with self.subTest(kind=kind):
                root = parse_svg(output)
                style = "\n".join(node.text or "" for node in root.findall("svg:style", SVG_NS))
                self.assertTrue(style.strip())
                self.assertNotRegex(style, r"\bvar\s*\(")

                def rule(class_name):
                    match = re.search(r"\." + re.escape(class_name) + r"\s*\{([^}]+)\}", style)
                    self.assertIsNotNone(match, "缺少实际元素使用的样式：" + class_name)
                    return dict((name.strip(), value.strip()) for name, value in
                                (item.split(":", 1) for item in match.group(1).split(";") if ":" in item))

                if kind == "flow":
                    self.assertIn("hnc-node", root.find("svg:rect[@data-node='start']", SVG_NS).get("class"))
                    self.assertIn("hnc-emphasis", root.find("svg:rect[@data-node='process']", SVG_NS).get("class"))
                    self.assertEqual(rule("hnc-node")["fill"], resolved["surface.node"])
                    self.assertEqual(rule("hnc-emphasis")["fill"], resolved["surface.emphasis"])
                    self.assertIsNotNone(root.find("svg:path[@class='hnc-edge']", SVG_NS))
                    line_style = rule("hnc-edge")
                    self.assertEqual(line_style["stroke"], resolved["text.secondary"])
                else:
                    self.assertIsNotNone(root.find("svg:line[@class='hnc-baseline']", SVG_NS))
                    line_style = rule("hnc-baseline")
                    self.assertEqual(line_style["stroke"], resolved["text.primary"])
                self.assertRegex(line_style["stroke"], r"^#[0-9A-Fa-f]{6}$")
                self.assertGreater(float(line_style["stroke-width"].removesuffix("px")), 0)

    def test_flow_terminal_requires_valid_start_or_end_kind(self):
        for kind in (None, "middle"):
            nodes = self.flow_nodes()
            if kind is None:
                del nodes[0]["terminal_kind"]
            else:
                nodes[0]["terminal_kind"] = kind
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "terminal_kind"):
                figures.flow(nodes, [], title="流程", desc="合成流程。")

    def test_flow_rejects_edge_through_another_node(self):
        with self.assertRaisesRegex(ValueError, "crosses a node interior"):
            figures.flow(self.flow_nodes(), [{"source": "start", "target": "end"}],
                         title="流程", desc="合成流程。")


class TokenTests(unittest.TestCase):
    @staticmethod
    def document(values):
        return {"schema": "haosunaki.tokens.v1", "tokens": {
            name: {"type": "color", "value": value, "status": "implementation",
                   "description": "测试颜色"} for name, value in values.items()}}

    def test_alias_chain_resolves_without_mutating_input(self):
        document = self.document({"base": "#123456", "semantic": "{base}", "component": "{semantic}"})
        document["tokens"]["component"]["css"] = "--test-color"
        self.assertEqual(tokens.resolve_tokens(document)["component"], "#123456")
        self.assertIn("--test-color: #123456;", tokens.render_css(document))
        self.assertEqual(document["tokens"]["component"]["value"], "{semantic}")

    def test_missing_alias_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "未知 token"):
            tokens.resolve_tokens(self.document({"semantic": "{missing}"}))

    def test_cyclic_alias_is_rejected(self):
        for values in ({"a": "{a}"}, {"a": "{b}", "b": "{a}"}):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, "循环 token"):
                tokens.resolve_tokens(self.document(values))


class PortableBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="haosunaki-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.temp_root = Path(cls.temp.name)
        staged = cls.temp_root / "staged"
        # 只复制发布核心；不依赖 README、示例、测试或开发机器的目录结构。
        for name in ("scripts", "assets"):
            shutil.copytree(ROOT / name, staged / name, ignore=shutil.ignore_patterns("__pycache__"))
        cls.package = staged.rename(cls.temp_root / "moved package")
        cls.working_dir = cls.temp_root / "unrelated working directory"
        cls.working_dir.mkdir()

    def setUp(self):
        self.case = Path(tempfile.mkdtemp(dir=self.working_dir))
        self.body = self.case / "body.html"
        self.body.write_text('<main><h1>搬移构建</h1><div class="hn-figure">合成内容</div></main>',
                             encoding="utf-8")

    def build(self, output, *extra):
        return subprocess.run(
            [sys.executable, "-I", "-B", str(self.package / "scripts" / "build_html.py"),
             "--body", str(self.body), "--title", "Portable <demo>", "--output", str(output), *extra],
            cwd=self.working_dir, text=True, capture_output=True, timeout=30)

    def test_build_from_moved_package_and_unrelated_working_directory(self):
        output = self.case / "new directory" / "page.html"
        result = self.build(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        page = output.read_text(encoding="utf-8")
        self.assertIn("<title>Portable &lt;demo&gt;</title>", page)
        self.assertIn(self.body.read_text(encoding="utf-8"), page)
        self.assertIn("data:font/woff2;base64,", page)
        self.assertIn('<style id="design-styles">', page)
        self.assertIn("<script>", page)
        self.assertNotIn(str(ROOT), page)
        self.assertEqual(Path(result.stdout.strip()), output.resolve())

    def test_default_build_refuses_to_overwrite_existing_output(self):
        output = self.case / "existing.html"
        original = "existing user content\n"
        output.write_text(original, encoding="utf-8")
        result = self.build(output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("输出文件已存在", result.stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), original)

    def test_build_refuses_same_input_and_output_even_with_force(self):
        original = self.body.read_bytes()
        for extra in ((), ("--force",)):
            with self.subTest(extra=extra):
                result = self.build(self.body, *extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("不能是同一文件", result.stderr)
                self.assertEqual(self.body.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
