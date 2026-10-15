import unittest


class ImportContractTests(unittest.TestCase):
    def test_core_modules_are_standard_library_compatible(self):
        from services import athlete_store
        from services import excel_parser
        from services import graph_service
        from services import input_template
        from services import lt_analysis
        from services import workflow
        from services import xlsx_io

        self.assertTrue(athlete_store.is_configured())
        self.assertTrue(hasattr(excel_parser, "parse_excel"))
        self.assertTrue(hasattr(graph_service, "make_hr_vo2_graph"))
        self.assertTrue(hasattr(input_template, "build_input_template"))
        self.assertTrue(hasattr(lt_analysis, "estimate_lt"))
        self.assertTrue(hasattr(workflow, "analyze"))
        self.assertTrue(hasattr(xlsx_io, "read_xlsx"))


if __name__ == "__main__":
    unittest.main()
