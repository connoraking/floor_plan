import math
import unittest

from floor_planner.core import (
    Calibration,
    Furniture,
    Project,
    ShapeSpec,
    ValidationError,
    format_measurement,
    from_inches,
    to_inches,
)


class UnitConversionTests(unittest.TestCase):
    def test_supported_units_round_trip(self) -> None:
        for unit, value in (("ft", 7.5), ("in", 90.0), ("cm", 228.6), ("m", 2.286)):
            with self.subTest(unit=unit):
                self.assertAlmostEqual(from_inches(to_inches(value, unit), unit), value)

    def test_friendly_feet_format(self) -> None:
        self.assertEqual(format_measurement(90.0, "ft"), "7 ft 6 in")
        self.assertEqual(format_measurement(84.0, "ft"), "7 ft")

    def test_invalid_measurement_is_rejected(self) -> None:
        for value in (0, -1, math.inf, math.nan):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                to_inches(value, "in")


class CalibrationTests(unittest.TestCase):
    def test_diagonal_scale(self) -> None:
        calibration = Calibration(0, 0, 300, 400, 100)
        self.assertEqual(calibration.page_distance, 500)
        self.assertEqual(calibration.points_per_inch, 5)

    def test_zero_length_line_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Calibration(10, 10, 10, 10, 12).validate()

    def test_non_finite_derived_scale_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Calibration(0, 0, 1, 0, 5e-324).validate()

    def test_numeric_strings_are_not_accepted(self) -> None:
        with self.assertRaises(ValidationError):
            Calibration.from_dict(
                {
                    "start_x": 0,
                    "start_y": 0,
                    "end_x": 100,
                    "end_y": 0,
                    "real_inches": "120",
                }
            )


class ShapeTests(unittest.TestCase):
    def test_rectangle_bounds_and_area(self) -> None:
        shape = ShapeSpec("rectangle", 84, 36)
        points = shape.polygon_inches()
        self.assertEqual(points[0], (-42, -18))
        self.assertEqual(points[2], (42, 18))
        self.assertEqual(shape.area_square_inches, 3024)

    def test_right_l_shape_geometry_and_area(self) -> None:
        shape = ShapeSpec(
            "l_shape",
            120,
            72,
            section_depth_in=36,
            chaise_width_in=36,
            chaise_side="right",
        )
        self.assertEqual(
            shape.polygon_inches(),
            [(-60, -36), (60, -36), (60, 36), (24, 36), (24, 0), (-60, 0)],
        )
        self.assertEqual(shape.area_square_inches, 120 * 36 + 36 * 36)

    def test_left_l_shape_mirrors_notch(self) -> None:
        shape = ShapeSpec(
            "l_shape",
            120,
            72,
            section_depth_in=36,
            chaise_width_in=30,
            chaise_side="left",
        )
        self.assertEqual(shape.polygon_inches()[3], (-30, 0))
        self.assertEqual(shape.polygon_inches()[4], (-30, 36))

    def test_impossible_l_shape_is_rejected(self) -> None:
        invalid_shapes = [
            ShapeSpec("l_shape", 100, 40, section_depth_in=40, chaise_width_in=20),
            ShapeSpec("l_shape", 100, 40, section_depth_in=20, chaise_width_in=100),
            ShapeSpec(
                "l_shape",
                100,
                40,
                section_depth_in=20,
                chaise_width_in=20,
                chaise_side="up",
            ),
        ]
        for shape in invalid_shapes:
            with self.subTest(shape=shape), self.assertRaises(ValidationError):
                shape.validate()

    def test_shape_validation_establishes_numeric_invariants(self) -> None:
        with self.assertRaises(ValidationError):
            ShapeSpec("rectangle", "84", "36").validate()  # type: ignore[arg-type]


class SerializationTests(unittest.TestCase):
    def test_project_round_trip(self) -> None:
        calibration = Calibration(12.5, 20.25, 312.5, 20.25, 144)
        furniture = Furniture(
            name="Élodie's couch",
            shape=ShapeSpec(
                "l_shape",
                120,
                72,
                section_depth_in=36,
                chaise_width_in=42,
                chaise_side="left",
            ),
            page=0,
            x=100.5,
            y=220.25,
            rotation=15,
            color="#9B51E0",
            locked=True,
        )
        project = Project(
            pdf_name="plan with spaces.pdf",
            current_page=0,
            display_unit="cm",
            calibrations={0: calibration},
            furniture=[furniture],
        )
        restored = Project.from_dict(project.to_dict())
        self.assertEqual(restored.to_dict(), project.to_dict())

    def test_unknown_schema_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Project.from_dict({"schema_version": 99})

    def test_fractional_schema_and_pages_are_rejected(self) -> None:
        for data in (
            {"schema_version": 1.9},
            {"schema_version": 1, "current_page": 0.5},
            {
                "schema_version": 1,
                "calibrations": {"01": Calibration(0, 0, 100, 0, 120).to_dict()},
            },
        ):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                Project.from_dict(data)

    def test_string_lock_and_invalid_color_are_rejected(self) -> None:
        item = Furniture(
            "Sofa", ShapeSpec("rectangle", 84, 36), 0, 10, 10, color="#2F80ED"
        ).to_dict()
        item["locked"] = "false"
        with self.assertRaises(ValidationError):
            Furniture.from_dict(item)
        item["locked"] = False
        item["color"] = "#; background: red"
        with self.assertRaises(ValidationError):
            Furniture.from_dict(item)

    def test_furniture_requires_a_page_calibration(self) -> None:
        project = Project(
            furniture=[Furniture("Sofa", ShapeSpec("rectangle", 84, 36), 0, 10, 10)]
        )
        with self.assertRaises(ValidationError):
            project.validate()


if __name__ == "__main__":
    unittest.main()
