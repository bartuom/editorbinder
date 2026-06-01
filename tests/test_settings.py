from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from unreal_utility_tool.settings import AppSettings, AppSettingsStore


class SettingsTests(unittest.TestCase):
    def test_missing_settings_load_defaults(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = AppSettingsStore(Path(temp_dir) / "settings.json")

            settings = store.load()

        self.assertEqual(settings.geometry, "")
        self.assertEqual(settings.always_top, False)
        self.assertEqual(settings.param_values, {})
        self.assertEqual(settings.details_panel_width, 360)
        self.assertEqual(settings.details_panel_height, 520)
        self.assertEqual(settings.collapsed_detail_sections, ["Source", "Tool"])
        self.assertEqual(settings.outliner_column_widths, {})
        self.assertEqual(settings.ai_provider, "Custom OpenAI-Compatible")
        self.assertEqual(settings.ai_base_url, "")
        self.assertEqual(settings.ai_model, "")
        self.assertEqual(settings.ai_api_key_env, "EDITORBINDER_API_KEY")
        self.assertEqual(settings.ai_timeout_seconds, 45)
        self.assertEqual(settings.ai_temperature, 0.2)
        self.assertEqual(settings.ai_max_tokens, 3000)

    def test_save_and_load_settings(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = AppSettingsStore(Path(temp_dir) / "settings.json")
            store.save(
                AppSettings(
                    geometry="420x480+100+200",
                    always_top=True,
                    favorite_ids=["a"],
                    recent_ids=["b"],
                    param_values={"tool-a": {"amount": "3"}},
                    details_panel_width=420,
                    details_panel_height=360,
                    collapsed_detail_sections=["Source", "Advanced"],
                    outliner_column_widths={"Item Label": 220},
                    ai_provider="DeepSeek",
                    ai_base_url="https://api.deepseek.com",
                    ai_model="deepseek-v4-flash",
                    ai_api_key_env="DEEPSEEK_API_KEY",
                    ai_timeout_seconds=30,
                    ai_temperature=0.1,
                    ai_max_tokens=2000,
                )
            )

            settings = store.load()

        self.assertEqual(settings.geometry, "420x480+100+200")
        self.assertEqual(settings.always_top, True)
        self.assertEqual(settings.favorite_ids, ["a"])
        self.assertEqual(settings.recent_ids, ["b"])
        self.assertEqual(settings.param_values, {"tool-a": {"amount": "3"}})
        self.assertEqual(settings.details_panel_width, 420)
        self.assertEqual(settings.details_panel_height, 360)
        self.assertEqual(settings.collapsed_detail_sections, ["Source", "Advanced"])
        self.assertEqual(settings.outliner_column_widths, {"Item Label": 220})
        self.assertEqual(settings.ai_provider, "DeepSeek")
        self.assertEqual(settings.ai_base_url, "https://api.deepseek.com")
        self.assertEqual(settings.ai_model, "deepseek-v4-flash")
        self.assertEqual(settings.ai_api_key_env, "DEEPSEEK_API_KEY")
        self.assertEqual(settings.ai_timeout_seconds, 30)
        self.assertEqual(settings.ai_temperature, 0.1)
        self.assertEqual(settings.ai_max_tokens, 2000)

    def test_old_settings_without_details_width_load_default(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text('{"geometry": "420x480+100+200", "always_top": true}', encoding="utf-8")
            store = AppSettingsStore(path)

            settings = store.load()

        self.assertEqual(settings.geometry, "420x480+100+200")
        self.assertEqual(settings.always_top, True)
        self.assertEqual(settings.details_panel_width, 360)
        self.assertEqual(settings.details_panel_height, 520)
        self.assertEqual(settings.collapsed_detail_sections, ["Source", "Tool"])
        self.assertEqual(settings.ai_api_key_env, "EDITORBINDER_API_KEY")


if __name__ == "__main__":
    unittest.main()
