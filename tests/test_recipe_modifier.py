import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from llm_pipeline.models import ModificationEdit  # noqa: E402
from llm_pipeline.recipe_modifier import RecipeModifier  # noqa: E402


class TestRecipeModifierReplace(unittest.TestCase):
    def setUp(self):
        self.modifier = RecipeModifier(similarity_threshold=0.6)

    def test_replace_uses_fuzzy_substring_when_exact_not_found(self):
        content = ["Preheat the oven to 350 degrees F (175 degrees C)"]
        edit = ModificationEdit(
            target="instructions",
            operation="replace",
            find="Preheat oven to 350 degree F (175 degree C)",
            replace="Preheat oven to 375 degree F (190 degree C)",
        )

        updated, records = self.modifier.apply_edit(edit, content)

        self.assertEqual(
            updated[0],
            "Preheat oven to 375 degree F (190 degree C)",
        )
        self.assertEqual(len(records), 1)
        self.assertNotEqual(records[0].from_text, records[0].to_text)

    def test_replace_does_not_record_noop_change(self):
        content = ["Preheat the oven to 350 degrees F (175 degrees C)"]
        edit = ModificationEdit(
            target="instructions",
            operation="replace",
            find="Preheat oven to 350 degree F (175 degree C)",
            replace="Preheat the oven to 350 degrees F (175 degrees C)",
        )

        updated, records = self.modifier.apply_edit(edit, content)

        self.assertEqual(
            updated[0],
            "Preheat the oven to 350 degrees F (175 degrees C)",
        )
        self.assertEqual(len(records), 0)

    def test_replace_skips_when_no_reasonable_substring_match(self):
        content = ["1 cup packed brown sugar"]
        edit = ModificationEdit(
            target="ingredients",
            operation="replace",
            find="add more butter",
            replace="add a little butter",
        )

        updated, records = self.modifier.apply_edit(edit, content)

        self.assertEqual(updated, content)
        self.assertEqual(len(records), 0)


if __name__ == "__main__":
    unittest.main()
