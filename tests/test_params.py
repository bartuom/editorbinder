from __future__ import annotations

import unittest

from unreal_utility_tool.params import ParamRenderError, parse_tool_params, render_tool_code, validate_param_value


class ParamTests(unittest.TestCase):
    def test_parse_tool_params(self) -> None:
        params = parse_tool_params(
            """# Param: min_yaw | float | -15 | Min Yaw
# Param: enabled | bool | true | Enabled
# Param: mode | enum | selected | Mode | options=selected,all | step=1
import unreal
"""
        )

        self.assertEqual(len(params), 3)
        self.assertEqual(params[0].name, "min_yaw")
        self.assertEqual(params[0].kind, "float")
        self.assertEqual(params[0].default, "-15")
        self.assertEqual(params[0].label, "Min Yaw")
        self.assertEqual(params[1].kind, "bool")
        self.assertEqual(params[2].kind, "enum")
        self.assertEqual(params[2].options, ["selected", "all"])

    def test_parse_csv_path_param(self) -> None:
        params = parse_tool_params("# Param: csv_path | path | dcc_layout.csv | CSV Path\n")

        self.assertEqual(params[0].name, "csv_path")
        self.assertEqual(params[0].kind, "path")
        self.assertEqual(params[0].default, "dcc_layout.csv")

    def test_render_tool_code_formats_literals(self) -> None:
        code = (
            "# Param: prefix | str | SM_ | Prefix\n"
            "# Param: amount | int | 3 | Amount\n"
            "# Param: scale | float | 1.5 | Scale\n"
            "# Param: enabled | bool | true | Enabled\n"
            "prefix = {{prefix}}\n"
            "amount = {{amount}}\n"
            "scale = {{scale}}\n"
            "enabled = {{enabled}}\n"
        )

        rendered = render_tool_code(
            code,
            {
                "prefix": "BP_",
                "amount": "7",
                "scale": "2.25",
                "enabled": "false",
            },
        )

        self.assertIn("prefix = 'BP_'", rendered)
        self.assertIn("amount = 7", rendered)
        self.assertIn("scale = 2.25", rendered)
        self.assertIn("enabled = False", rendered)

    def test_render_tool_code_accepts_comma_decimal_float(self) -> None:
        code = "# Param: scale | float | 1.0 | Scale | min=0,5 | max=2,5\nscale = {{scale}}\n"

        validate_param_value(parse_tool_params(code)[0], "1,75")
        rendered = render_tool_code(code, {"scale": "1,75"})

        self.assertIn("scale = 1.75", rendered)

    def test_render_tool_code_rejects_invalid_int(self) -> None:
        code = "# Param: amount | int | 3 | Amount\namount = {{amount}}\n"

        with self.assertRaises(ParamRenderError):
            render_tool_code(code, {"amount": "abc"})

    def test_render_tool_code_rejects_out_of_range_float(self) -> None:
        code = "# Param: scale | float | 1.0 | Scale | min=0.1 | max=2.0\nscale = {{scale}}\n"

        with self.assertRaises(ParamRenderError):
            render_tool_code(code, {"scale": "3"})

    def test_render_tool_code_formats_enum(self) -> None:
        code = "# Param: mode | enum | selected | Mode | options=selected,all\nmode = {{mode}}\n"

        rendered = render_tool_code(code, {"mode": "all"})

        self.assertIn("mode = 'all'", rendered)

    def test_validate_param_value_reuses_param_rules(self) -> None:
        param = parse_tool_params("# Param: amount | int | 3 | Amount | min=1 | max=5\n")[0]

        validate_param_value(param, "4")

        with self.assertRaises(ParamRenderError):
            validate_param_value(param, "8")

    def test_render_tool_code_rewrites_first_literal_assignment_for_ai_output(self) -> None:
        code = (
            "# Param: use_selected_only | bool | True | Use Selected Actors Only\n"
            "# Param: min_scale | float | 1.0 | Min Random Scale\n"
            "use_selected_only = True\n"
            "min_scale = 1.0\n"
            "min_scale = min_scale + 1\n"
        )

        rendered = render_tool_code(code, {"use_selected_only": "false", "min_scale": "2.5"})

        self.assertIn("use_selected_only = False", rendered)
        self.assertIn("min_scale = 2.5", rendered)
        self.assertIn("min_scale = min_scale + 1", rendered)


if __name__ == "__main__":
    unittest.main()
