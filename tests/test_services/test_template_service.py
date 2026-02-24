"""测试模板服务的纯函数（不需要数据库的部分）"""

import pytest

from app.services.template_service import render_preview, validate_template_syntax


class TestRenderPreview:
    def test_basic_render(self):
        subject, html, text = render_preview(
            "欢迎 {{ username }}",
            "<h1>你好 {{ username }}</h1>",
            "你好 {{ username }}",
            {"username": "张三"},
        )
        assert subject == "欢迎 张三"
        assert "<h1>你好 张三</h1>" in html
        assert text == "你好 张三"

    def test_render_without_text(self):
        subject, html, text = render_preview(
            "标题",
            "<p>内容</p>",
            None,
            {},
        )
        assert subject == "标题"
        assert html == "<p>内容</p>"
        assert text is None

    def test_render_with_multiple_variables(self):
        subject, html, _ = render_preview(
            "{{ app }} 通知",
            "<p>{{ user }}，你的订单 {{ order_id }} 已发货</p>",
            None,
            {"app": "MyApp", "user": "李四", "order_id": "ORD-001"},
        )
        assert subject == "MyApp 通知"
        assert "李四" in html
        assert "ORD-001" in html

    def test_render_html_escaping(self):
        """确保 autoescape 开启，防止 XSS"""
        _, html, _ = render_preview(
            "test",
            "<p>{{ content }}</p>",
            None,
            {"content": "<script>alert(1)</script>"},
        )
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_render_missing_variable_produces_empty(self):
        subject, _, _ = render_preview(
            "你好 {{ name }}",
            "<p>{{ content }}</p>",
            None,
            {},  # 不提供任何变量
        )
        assert subject == "你好 "

    def test_render_with_jinja2_control_flow(self):
        _, html, _ = render_preview(
            "test",
            "{% if vip %}VIP用户{% else %}普通用户{% endif %}",
            None,
            {"vip": True},
        )
        assert "VIP用户" in html


class TestValidateTemplateSyntax:
    def test_valid_syntax(self):
        ok, err = validate_template_syntax("{{ name }} 你好")
        assert ok is True
        assert err == ""

    def test_valid_with_control_flow(self):
        ok, _ = validate_template_syntax("{% for item in items %}{{ item }}{% endfor %}")
        assert ok is True

    def test_invalid_syntax(self):
        ok, err = validate_template_syntax("{{ unclosed")
        assert ok is False
        assert err != ""

    def test_invalid_block(self):
        ok, err = validate_template_syntax("{% for x in %}{% endfor %}")
        assert ok is False

    def test_empty_string_is_valid(self):
        ok, _ = validate_template_syntax("")
        assert ok is True

    def test_plain_text_is_valid(self):
        ok, _ = validate_template_syntax("纯文本内容，没有变量")
        assert ok is True
