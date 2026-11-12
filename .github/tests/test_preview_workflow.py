"""Pin the reviewed PR build path scope without executing workflow code."""

import unittest
from pathlib import Path

BUILD_WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "preview-website.yml"


class PreviewWorkflowTests(unittest.TestCase):
    """Require the complete path list to contain only website and documentation."""

    def test_build_path_filters_are_exactly_website_and_docs(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("    paths:\n", workflow)
        path_block = workflow.split("    paths:\n", 1)[1].split("\npermissions:", 1)[0]
        self.assertEqual(
            [
                line.strip().removeprefix("- ").strip("\"'")
                for line in path_block.splitlines()
                if line.strip()
            ],
            ["website/**", "docs/**"],
        )


if __name__ == "__main__":
    unittest.main()
