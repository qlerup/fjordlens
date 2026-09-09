"""Template-only regressions; no database, AI workers or application startup needed.

Run: python -m unittest discover -s tests -p 'test_login_appearance_template.py'
Browser-bootstrap behavior: node --test tests/test_login_appearance.js
"""
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
import unittest

from jinja2 import Environment, FileSystemLoader, select_autoescape


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class LoginAppearanceTemplateTests(unittest.TestCase):
    def render(self, cookies=None):
        env = Environment(
            loader=FileSystemLoader(Path(__file__).resolve().parents[1] / "templates"),
            autoescape=select_autoescape(["html"]),
        )
        return env.get_template("base.html").render(
            request=SimpleNamespace(cookies=cookies or {}),
            app_build="appearance-test",
            ui_lang="da",
            url_for=lambda endpoint, **kwargs: "/static/" + kwargs["filename"],
        )

    def test_cookie_preferences_are_rendered_without_javascript(self):
        for design in ("classic", "fjord"):
            for theme in ("system", "light", "dark"):
                with self.subTest(design=design, theme=theme):
                    html = self.render({"fl_ui_design": design, "fl_theme_mode": theme})
                    tags = Tags(html).tags
                    root = next(attrs for tag, attrs in tags if tag == "html")
                    css = next(attrs for tag, attrs in tags if attrs.get("id") == "fjordDesignStylesheet")
                    self.assertEqual(root["data-ui-design"], design)
                    self.assertEqual(root.get("data-theme"), None if theme == "system" else theme)
                    self.assertEqual(css["media"], "all" if design == "fjord" else "not all")
                    self.assertNotIn("disabled", css)
                    self.assertEqual(css["href"], "/static/redesign.css")
                    colors = [attrs["content"] for tag, attrs in tags if attrs.get("name") == "theme-color"]
                    if theme != "system":
                        expected = {
                            ("classic", "dark"): "#0f1115",
                            ("classic", "light"): "#f5f6f8",
                            ("fjord", "dark"): "#08141a",
                            ("fjord", "light"): "#edf3f4",
                        }[design, theme]
                        self.assertEqual(colors, [expected] * 3)

    def test_new_browser_defaults_to_classic_and_system(self):
        html = self.render()
        root = next(attrs for tag, attrs in Tags(html).tags if tag == "html")
        self.assertEqual(root["data-ui-design"], "classic")
        self.assertNotIn("data-theme", root)

    def test_cookie_values_cannot_inject_markup(self):
        attack = '\"><script>alert("appearance")</script>'
        html = self.render({"fl_ui_design": attack, "fl_theme_mode": attack})
        self.assertNotIn(attack, html)
        root = next(attrs for tag, attrs in Tags(html).tags if tag == "html")
        self.assertEqual(root["data-ui-design"], "classic")
        self.assertNotIn("data-theme", root)

    def test_bootstrap_precedes_stylesheets_and_stylesheets_precede_body(self):
        html = self.render()
        self.assertLess(html.index("function restoreAppearance"), html.index('href="/static/styles.css"'))
        self.assertLess(html.index('href="/static/redesign.css"'), html.index("<body"))


if __name__ == "__main__":
    unittest.main()
