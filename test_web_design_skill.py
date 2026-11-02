"""Static acceptance checks for the optional Tavi web-design skill package."""
from pathlib import Path
import unittest

ROOT = Path(__file__).parent / "skills" / "tavi-web-design"


class WebDesignSkillTests(unittest.TestCase):
    def test_skill_entry_and_references_exist(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: tavi-web-design\n"))
        for path in (
            "references/design-system.md",
            "references/motion-interactions.md",
            "references/quality-gates.md",
            "references/creative-brief.md",
            "references/inspiration.md",
            "examples/showcase.html",
            "examples/README.md",
        ):
            self.assertTrue((ROOT / path).is_file(), path)
            self.assertIn(path, skill)

    def test_accessibility_and_budget_requirements(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8").lower()
        for phrase in ("reduced-motion", "keyboard", "responsive", "performance", "without js", "animation"):
            self.assertIn(phrase, skill)

    def test_standalone_demo_has_real_controls_and_fallbacks(self):
        html = (ROOT / "examples/showcase.html").read_text(encoding="utf-8")
        for phrase in (
            "<!doctype html>", "<main", "<style>", "<script>",
            "prefers-reduced-motion", "kinetic-canvas", "IntersectionObserver",
            "aria-pressed", "clipboard", "menu-toggle"
        ):
            self.assertIn(phrase, html)

if __name__ == "__main__":
    unittest.main()
