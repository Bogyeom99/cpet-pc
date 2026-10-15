import io
import unittest

from services.excel_parser import (
    is_allout,
    is_recovery,
    is_rest,
    parse_excel,
)
from services.input_template import (
    build_input_template,
    parse_lactate_sheet,
)
from services.xlsx_io import build_xlsx, read_xlsx


def _book(data_rows, lactate_rows=None):
    sheets = [("Data", data_rows)]
    if lactate_rows is not None:
        sheets.append(("Lactate", lactate_rows))
    return io.BytesIO(
        build_xlsx(
            sheets,
            header_rows={
                "Data": {1},
                "Lactate": {1},
            },
        )
    )


class ExcelParserTests(unittest.TestCase):
    def test_stage_normalization_and_allout(self):
        rows = [["Time", "VO2/kg", "Heart Rate", "Stage"]]
        for i in range(30):
            stage = 3 if i < 10 else 4.5 if i < 20 else 6
            rows.append([i, 10 + i * 0.5, 90 + i * 2, stage])

        _, segments, summary = parse_excel(
            _book(rows),
            stage_duration_min=5,
        )

        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0].duration, 300)
        self.assertEqual(segments[1].duration, 300)
        self.assertTrue(segments[2].is_allout)
        self.assertEqual(segments[2].load, 6.0)
        self.assertEqual(
            [row["Stage"] for row in summary],
            ["3", "4.5", "All-Out"],
        )

    def test_rest_duration(self):
        rows = [["Time", "VO2/kg", "Heart Rate", "Stage"]]
        stages = [4] * 8 + ["R"] * 5 + [5.5] * 8 + [7] * 3
        for i, stage in enumerate(stages):
            rows.append([i, 10 + i, 90 + i, stage])

        _, segments, _ = parse_excel(
            _book(rows),
            stage_duration_min=3,
            rest_duration_min=1.5,
        )

        rest = next(seg for seg in segments if seg.is_rest)
        self.assertEqual(rest.duration, 90.0)
        self.assertEqual(segments[0].duration, 180.0)
        self.assertTrue(segments[-1].is_allout)

    def test_legacy_speed_column(self):
        rows = [["Time", "VO2/kg", "Heart Rate", "Speed"]]
        for i, speed in enumerate([3, 3, 3, 4.5, 4.5, 4.5]):
            rows.append([i, 10 + i, 90 + i, speed])

        _, segments, _ = parse_excel(_book(rows))
        self.assertEqual(
            [seg.load for seg in segments],
            [3.0, 4.5],
        )

    def test_lactate_sheet(self):
        data = [
            ["Time", "VO2/kg", "Heart Rate", "Stage"],
            [0, 10, 90, 14],
            [1, 11, 95, 14],
            [2, 12, 100, 16],
            [3, 13, 105, 16],
        ]
        lactate = [
            ["Stage", "Lactate"],
            [14, 3.5],
            [16, 7.8],
            ["Recovery 1min", 6.2],
        ]

        rows = parse_lactate_sheet(_book(data, lactate))
        self.assertEqual(rows[1]["stage"], "16")
        self.assertEqual(rows[1]["lactate"], 7.8)

    def test_template_uses_stage_column(self):
        workbook = read_xlsx(build_input_template())
        self.assertIn("Data", workbook)
        self.assertEqual(
            workbook["Data"][0],
            ["Time", "VO2/kg", "Heart Rate", "Stage"],
        )

    def test_label_helpers(self):
        self.assertTrue(is_rest("R"))
        self.assertTrue(is_rest("rest"))
        self.assertTrue(is_allout("All-Out"))
        self.assertTrue(is_recovery("Recovery 5min"))


if __name__ == "__main__":
    unittest.main()
