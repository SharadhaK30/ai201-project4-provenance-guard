from __future__ import annotations

import unittest

from detector import classify_content
from home_repair import assess_home_repair_question
from multimodal import analyze_image_metadata


AI_STYLE_TEXT = """
Furthermore, it is important to note that a robust and seamless platform can leverage modern workflows.
Moreover, the solution provides a structured approach for teams seeking consistent outcomes.
Additionally, the process can be adapted across contexts while maintaining clarity and efficiency.
In conclusion, this comprehensive method supports scalable collaboration and measurable improvements.
"""

HUMAN_STYLE_TEXT = """
Honestly, I am not sure the first draft was any good. I wrote it after class, crossed out two paragraphs,
and kept the part about my grandmother's kitchen because that was the only section that sounded like me.
I remember spilling tea on the notes, which is probably why the last page has a weird gap in the middle.
The ending still needs work, but my draft is trying to explain why small routines matter.
"""


class DetectorTests(unittest.TestCase):
    def test_ai_style_text_returns_ai_or_uncertain_with_signals(self) -> None:
        result = classify_content(AI_STYLE_TEXT)

        self.assertIn(result.classification, {"likely_ai_generated", "uncertain"})
        self.assertGreaterEqual(len(result.signals), 5)
        self.assertGreater(result.ai_likelihood, 0.45)
        self.assertTrue(result.transparency_label)

    def test_human_markers_reduce_ai_likelihood(self) -> None:
        ai_result = classify_content(AI_STYLE_TEXT)
        human_result = classify_content(HUMAN_STYLE_TEXT)

        self.assertLess(human_result.ai_likelihood, ai_result.ai_likelihood)
        self.assertIn(human_result.classification, {"likely_human_written", "uncertain"})

    def test_short_text_surfaces_uncertainty_warning(self) -> None:
        result = classify_content("Nice caption.")

        self.assertIn("Short submissions are harder to classify reliably.", result.warnings)
        self.assertEqual(result.classification, "uncertain")


class HomeRepairGuardrailTests(unittest.TestCase):
    def test_refuses_electrical_panel_question(self) -> None:
        result = assess_home_repair_question("How do I replace a breaker in my electrical panel?")

        self.assertFalse(result.should_answer)
        self.assertEqual(result.safety_label, "refer_to_professional")
        self.assertIn("electrical_panel", result.matched_topics)

    def test_allows_low_risk_maintenance_question(self) -> None:
        result = assess_home_repair_question("How do I stop a leaky faucet from dripping?")

        self.assertTrue(result.should_answer)
        self.assertEqual(result.safety_label, "answer_with_basic_precautions")


class MetadataAnalysisTests(unittest.TestCase):
    def test_generated_image_metadata_scores_ai_like(self) -> None:
        result = analyze_image_metadata(
            {
                "tool": "Midjourney",
                "prompt": "cinematic portrait, studio lighting",
                "exif_present": False,
            }
        )

        self.assertIn(result.classification, {"likely_ai_generated", "uncertain"})
        self.assertGreater(result.ai_likelihood, 0.5)
        self.assertEqual(result.content_type, "image_metadata")

    def test_source_evidence_lowers_metadata_likelihood(self) -> None:
        generated = analyze_image_metadata({"tool": "Stable Diffusion", "prompt": "fantasy scene"})
        sourced = analyze_image_metadata(
            {
                "tool": "camera",
                "source_file_type": "raw",
                "exif_present": True,
                "edit_history_present": True,
            }
        )

        self.assertLess(sourced.ai_likelihood, generated.ai_likelihood)


if __name__ == "__main__":
    unittest.main()
