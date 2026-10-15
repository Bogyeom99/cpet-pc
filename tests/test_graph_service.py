import unittest

from services.excel_parser import Segment
from services.graph_service import (
    LEFT_PAD_SEC,
    _lactate_x_for_stage,
    make_hr_vo2_graph,
    make_hr_vo2_lactate_graph,
)


class GraphServiceTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"_x": 0, "Heart Rate": 90, "VO2/kg": 15},
            {"_x": 90, "Heart Rate": 105, "VO2/kg": 20},
            {"_x": 180, "Heart Rate": 120, "VO2/kg": 25},
            {"_x": 270, "Heart Rate": 135, "VO2/kg": 32},
            {"_x": 360, "Heart Rate": 150, "VO2/kg": 40},
            {"_x": 390, "Heart Rate": 170, "VO2/kg": 48},
            {"_x": 420, "Heart Rate": 185, "VO2/kg": 55},
            {"_x": 450, "Heart Rate": 160, "VO2/kg": 35},
            {"_x": 480, "Heart Rate": 140, "VO2/kg": 25},
        ]
        self.segments = [
            Segment("100", [0, 1, 2], 0, 180, 90, 180, 100.0, False, False, False),
            Segment("150", [3, 4], 180, 360, 270, 180, 150.0, False, False, False),
            Segment("All-Out", [5, 6], 360, 420, 390, 60, 200.0, False, False, True),
            Segment("Recovery", [7, 8], 420, 480, 450, 60, None, False, True, False),
        ]

    def test_basic_graph_model_and_lt_hr(self):
        model, threshold_hr = make_hr_vo2_graph(
            self.rows,
            self.segments,
            hrmax=190,
            lt1_load=125,
            lt2_load=175,
        )
        self.assertEqual(model["kind"], "hr_vo2")
        self.assertIsNotNone(threshold_hr["LT1"])
        self.assertIsNotNone(threshold_hr["LT2"])

    def test_combined_graph_model(self):
        points = [
            {"label": "100", "load": 100.0, "lactate": 1.2},
            {"label": "150", "load": 150.0, "lactate": 2.1},
            {"label": "AO", "load": 200.0, "lactate": 7.5},
            {"label": "Recovery 1min", "load": None, "lactate": 5.4},
        ]
        model, _ = make_hr_vo2_lactate_graph(
            self.rows,
            self.segments,
            hrmax=190,
            lactate_points=points,
            lt1_load=125,
            lt2_load=175,
        )
        self.assertEqual(model["kind"], "combined")
        self.assertGreaterEqual(len(model["lactate_points"]), 3)

    def test_rest_lactate_before_zero(self):
        x = _lactate_x_for_stage(
            self.segments,
            "Rest",
            None,
        )
        self.assertEqual(x, -LEFT_PAD_SEC / 2)


if __name__ == "__main__":
    unittest.main()
