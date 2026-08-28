from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

PROJECT_SCHEMA_VERSION = 1
MAX_PAGE_INDEX = 100_000
MAX_PAGE_COORDINATE = 100_000_000.0
MAX_REAL_MEASUREMENT_INCHES = 10_000_000.0
MAX_FURNITURE_INCHES = 1_000_000.0
MAX_POINTS_PER_INCH = 1_000_000.0
MAX_SCENE_SHAPE_POINTS = 100_000_000.0
MAX_FURNITURE_ITEMS = 50_000

UNIT_LABELS: dict[str, str] = {
    "ft": "Feet",
    "in": "Inches",
    "cm": "Centimeters",
    "m": "Meters",
}

_INCHES_PER_UNIT: dict[str, float] = {
    "ft": 12.0,
    "in": 1.0,
    "cm": 1.0 / 2.54,
    "m": 100.0 / 2.54,
}


class ValidationError(ValueError):
    """Raised when project or geometry data is not usable."""


def _finite_number(
    value: float, label: str, *, absolute_limit: float | None = None
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{label} must be a number.")
    canonical = float(value)
    if not math.isfinite(canonical):
        raise ValidationError(f"{label} must be a finite number.")
    if absolute_limit is not None and abs(canonical) > absolute_limit:
        raise ValidationError(f"{label} is outside the supported range.")
    return canonical


def _positive_number(
    value: float, label: str, *, maximum: float | None = None
) -> float:
    canonical = _finite_number(value, label)
    if canonical <= 0:
        raise ValidationError(f"{label} must be greater than zero.")
    if maximum is not None and canonical > maximum:
        raise ValidationError(f"{label} is outside the supported range.")
    return canonical


def _nonnegative_integer(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{label} must be a whole number.")
    if value < 0 or value > MAX_PAGE_INDEX:
        raise ValidationError(f"{label} is outside the supported range.")
    return value


def to_inches(value: float, unit: str) -> float:
    if not isinstance(unit, str) or unit not in _INCHES_PER_UNIT:
        raise ValidationError(f"Unsupported unit: {unit}")
    result = _positive_number(value, "Measurement") * _INCHES_PER_UNIT[unit]
    if not math.isfinite(result):
        raise ValidationError("Measurement is outside the supported range.")
    return result


def from_inches(value: float, unit: str) -> float:
    if not isinstance(unit, str) or unit not in _INCHES_PER_UNIT:
        raise ValidationError(f"Unsupported unit: {unit}")
    return _finite_number(value, "Measurement") / _INCHES_PER_UNIT[unit]


def _friendly_number(value: float) -> str:
    if abs(value - round(value)) < 1e-8:
        return str(round(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def format_measurement(inches: float, unit: str) -> str:
    """Format a canonical inch value in the project's preferred unit."""
    if unit == "ft":
        feet = math.floor(max(0.0, inches) / 12.0 + 1e-9)
        remainder = max(0.0, inches) - feet * 12.0
        if abs(remainder - 12.0) < 0.005:
            feet += 1
            remainder = 0.0
        if remainder < 0.005:
            return f"{feet} ft"
        return f"{feet} ft {_friendly_number(remainder)} in"
    suffix = {"in": "in", "cm": "cm", "m": "m"}.get(unit)
    if suffix is None:
        raise ValidationError(f"Unsupported unit: {unit}")
    return f"{_friendly_number(from_inches(inches, unit))} {suffix}"


@dataclass
class Calibration:
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    real_inches: float

    def validate(self) -> None:
        self.start_x = _finite_number(
            self.start_x, "Calibration start X", absolute_limit=MAX_PAGE_COORDINATE
        )
        self.start_y = _finite_number(
            self.start_y, "Calibration start Y", absolute_limit=MAX_PAGE_COORDINATE
        )
        self.end_x = _finite_number(
            self.end_x, "Calibration end X", absolute_limit=MAX_PAGE_COORDINATE
        )
        self.end_y = _finite_number(
            self.end_y, "Calibration end Y", absolute_limit=MAX_PAGE_COORDINATE
        )
        self.real_inches = _positive_number(
            self.real_inches,
            "Calibration distance",
            maximum=MAX_REAL_MEASUREMENT_INCHES,
        )
        page_distance = self.page_distance
        if not math.isfinite(page_distance) or page_distance <= 1e-6:
            raise ValidationError("Draw a longer calibration line.")
        points_per_inch = page_distance / self.real_inches
        if (
            not math.isfinite(points_per_inch)
            or points_per_inch <= 0
            or points_per_inch > MAX_POINTS_PER_INCH
        ):
            raise ValidationError(
                "The resulting plan scale is outside the supported range."
            )

    @property
    def page_distance(self) -> float:
        return math.hypot(self.end_x - self.start_x, self.end_y - self.start_y)

    @property
    def points_per_inch(self) -> float:
        self.validate()
        return self.page_distance / self.real_inches

    def to_dict(self) -> dict[str, float]:
        self.validate()
        return {
            "start_x": self.start_x,
            "start_y": self.start_y,
            "end_x": self.end_x,
            "end_y": self.end_y,
            "real_inches": self.real_inches,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Calibration:
        if not isinstance(data, dict):
            raise ValidationError("Invalid calibration data.")
        try:
            calibration = cls(
                start_x=data["start_x"],
                start_y=data["start_y"],
                end_x=data["end_x"],
                end_y=data["end_y"],
                real_inches=data["real_inches"],
            )
        except KeyError as exc:
            raise ValidationError("Invalid calibration data.") from exc
        calibration.validate()
        return calibration


@dataclass
class ShapeSpec:
    kind: str
    width_in: float
    depth_in: float
    section_depth_in: float | None = None
    chaise_width_in: float | None = None
    chaise_side: str = "right"

    def validate(self) -> None:
        if not isinstance(self.kind, str):
            raise ValidationError("Furniture shape type is invalid.")
        if self.kind not in {"rectangle", "l_shape"}:
            raise ValidationError(f"Unsupported furniture shape: {self.kind}")
        width = _positive_number(self.width_in, "Width", maximum=MAX_FURNITURE_INCHES)
        depth = _positive_number(self.depth_in, "Depth", maximum=MAX_FURNITURE_INCHES)
        self.width_in = width
        self.depth_in = depth
        if self.kind == "l_shape":
            section_depth = _positive_number(
                self.section_depth_in if self.section_depth_in is not None else 0,
                "Main section depth",
                maximum=MAX_FURNITURE_INCHES,
            )
            chaise_width = _positive_number(
                self.chaise_width_in if self.chaise_width_in is not None else 0,
                "Chaise width",
                maximum=MAX_FURNITURE_INCHES,
            )
            if section_depth >= depth:
                raise ValidationError(
                    "Main section depth must be less than overall depth."
                )
            if chaise_width >= width:
                raise ValidationError("Chaise width must be less than overall width.")
            if not isinstance(self.chaise_side, str) or self.chaise_side not in {
                "left",
                "right",
            }:
                raise ValidationError("Chaise side must be left or right.")
            self.section_depth_in = section_depth
            self.chaise_width_in = chaise_width
        else:
            self.section_depth_in = None
            self.chaise_width_in = None
            self.chaise_side = "right"

    def polygon_inches(self) -> list[tuple[float, float]]:
        """Return clockwise local points centered on the overall bounding box."""
        self.validate()
        width = self.width_in
        depth = self.depth_in
        if self.kind == "rectangle":
            points = [(0.0, 0.0), (width, 0.0), (width, depth), (0.0, depth)]
        elif self.chaise_side == "right":
            assert self.section_depth_in is not None
            assert self.chaise_width_in is not None
            points = [
                (0.0, 0.0),
                (width, 0.0),
                (width, depth),
                (width - self.chaise_width_in, depth),
                (width - self.chaise_width_in, self.section_depth_in),
                (0.0, self.section_depth_in),
            ]
        else:
            assert self.section_depth_in is not None
            assert self.chaise_width_in is not None
            points = [
                (0.0, 0.0),
                (width, 0.0),
                (width, self.section_depth_in),
                (self.chaise_width_in, self.section_depth_in),
                (self.chaise_width_in, depth),
                (0.0, depth),
            ]
        return [(x - width / 2.0, y - depth / 2.0) for x, y in points]

    @property
    def area_square_inches(self) -> float:
        self.validate()
        if self.kind == "rectangle":
            return self.width_in * self.depth_in
        assert self.section_depth_in is not None
        assert self.chaise_width_in is not None
        return self.width_in * self.section_depth_in + self.chaise_width_in * (
            self.depth_in - self.section_depth_in
        )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "kind": self.kind,
            "width_in": self.width_in,
            "depth_in": self.depth_in,
            "section_depth_in": self.section_depth_in,
            "chaise_width_in": self.chaise_width_in,
            "chaise_side": self.chaise_side,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShapeSpec:
        if not isinstance(data, dict):
            raise ValidationError("Invalid furniture shape data.")
        try:
            shape = cls(
                kind=data["kind"],
                width_in=data["width_in"],
                depth_in=data["depth_in"],
                section_depth_in=data.get("section_depth_in"),
                chaise_width_in=data.get("chaise_width_in"),
                chaise_side=data.get("chaise_side", "right"),
            )
        except KeyError as exc:
            raise ValidationError("Invalid furniture shape data.") from exc
        shape.validate()
        return shape


@dataclass
class Furniture:
    name: str
    shape: ShapeSpec
    page: int
    x: float
    y: float
    rotation: float = 0.0
    color: str = "#2F80ED"
    locked: bool = False
    item_id: str = field(default_factory=lambda: str(uuid4()))

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError("Furniture needs a name.")
        self.name = self.name.strip()
        if len(self.name) > 200 or any(ord(character) < 32 for character in self.name):
            raise ValidationError("Furniture name is invalid or too long.")
        if not isinstance(self.item_id, str) or not (1 <= len(self.item_id) <= 128):
            raise ValidationError("Furniture ID is invalid.")
        if not isinstance(self.shape, ShapeSpec):
            raise ValidationError("Furniture shape is invalid.")
        self.shape.validate()
        self.page = _nonnegative_integer(self.page, "Furniture page")
        self.x = _finite_number(
            self.x, "Furniture X position", absolute_limit=MAX_PAGE_COORDINATE
        )
        self.y = _finite_number(
            self.y, "Furniture Y position", absolute_limit=MAX_PAGE_COORDINATE
        )
        self.rotation = _finite_number(self.rotation, "Furniture rotation") % 360.0
        if not isinstance(self.locked, bool):
            raise ValidationError("Furniture lock state is invalid.")
        if (
            not isinstance(self.color, str)
            or re.fullmatch(r"#[0-9A-Fa-f]{6}", self.color) is None
        ):
            raise ValidationError("Furniture color is invalid.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "id": self.item_id,
            "name": self.name,
            "shape": self.shape.to_dict(),
            "page": self.page,
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
            "color": self.color,
            "locked": self.locked,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Furniture:
        if not isinstance(data, dict):
            raise ValidationError("Invalid furniture data.")
        try:
            item = cls(
                item_id=data["id"],
                name=data["name"],
                shape=ShapeSpec.from_dict(data["shape"]),
                page=data["page"],
                x=data["x"],
                y=data["y"],
                rotation=data.get("rotation", 0.0),
                color=data.get("color", "#2F80ED"),
                locked=data.get("locked", False),
            )
        except KeyError as exc:
            raise ValidationError("Invalid furniture data.") from exc
        item.validate()
        return item


@dataclass
class Project:
    pdf_name: str = "floor-plan.pdf"
    current_page: int = 0
    display_unit: str = "ft"
    calibrations: dict[int, Calibration] = field(default_factory=dict)
    furniture: list[Furniture] = field(default_factory=list)

    def validate(self) -> None:
        if not isinstance(self.pdf_name, str) or not self.pdf_name.strip():
            raise ValidationError("Project PDF name is invalid.")
        self.pdf_name = self.pdf_name.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not self.pdf_name or any(ord(character) < 32 for character in self.pdf_name):
            raise ValidationError("Project PDF name is invalid.")
        if len(self.pdf_name) > 512:
            raise ValidationError("Project PDF name is too long.")
        self.current_page = _nonnegative_integer(self.current_page, "Current page")
        if (
            not isinstance(self.display_unit, str)
            or self.display_unit not in UNIT_LABELS
        ):
            raise ValidationError("Project display unit is unsupported.")
        if not isinstance(self.calibrations, dict):
            raise ValidationError("Project calibrations are malformed.")
        for page, calibration in self.calibrations.items():
            _nonnegative_integer(page, "Calibration page")
            if not isinstance(calibration, Calibration):
                raise ValidationError("Project calibration is malformed.")
            calibration.validate()
        if not isinstance(self.furniture, list):
            raise ValidationError("Project furniture is malformed.")
        if len(self.furniture) > MAX_FURNITURE_ITEMS:
            raise ValidationError("This project contains too many furniture pieces.")
        seen_ids: set[str] = set()
        for item in self.furniture:
            if not isinstance(item, Furniture):
                raise ValidationError("Project furniture is malformed.")
            item.validate()
            if item.page not in self.calibrations:
                raise ValidationError(
                    f'Furniture "{item.name}" is on a page without a scale calibration.'
                )
            scale = self.calibrations[item.page].points_per_inch
            if (
                max(item.shape.width_in, item.shape.depth_in) * scale
                > MAX_SCENE_SHAPE_POINTS
            ):
                raise ValidationError(
                    f'Furniture "{item.name}" is too large for the calibrated plan scale.'
                )
            if item.item_id in seen_ids:
                raise ValidationError("Furniture IDs must be unique.")
            seen_ids.add(item.item_id)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": PROJECT_SCHEMA_VERSION,
            "pdf_name": self.pdf_name,
            "current_page": self.current_page,
            "display_unit": self.display_unit,
            "calibrations": {
                str(page): calibration.to_dict()
                for page, calibration in sorted(self.calibrations.items())
            },
            "furniture": [item.to_dict() for item in self.furniture],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        if not isinstance(data, dict):
            raise ValidationError("The project data is malformed.")
        version = data.get("schema_version")
        if isinstance(version, bool) or not isinstance(version, int):
            raise ValidationError("This project is missing a valid schema version.")
        if version != PROJECT_SCHEMA_VERSION:
            raise ValidationError(
                f"Project version {version} is not supported by this version of Floor Planner."
            )
        raw_calibrations = data.get("calibrations", {})
        if not isinstance(raw_calibrations, dict):
            raise ValidationError("Project calibrations are malformed.")
        calibrations: dict[int, Calibration] = {}
        for page, value in raw_calibrations.items():
            if (
                not isinstance(page, str)
                or re.fullmatch(r"0|[1-9][0-9]*", page) is None
            ):
                raise ValidationError("A calibration page number is invalid.")
            page_number = int(page)
            _nonnegative_integer(page_number, "Calibration page")
            calibrations[page_number] = Calibration.from_dict(value)

        raw_furniture = data.get("furniture", [])
        if not isinstance(raw_furniture, list):
            raise ValidationError("Project furniture is malformed.")
        project = cls(
            pdf_name=data.get("pdf_name", "floor-plan.pdf"),
            current_page=data.get("current_page", 0),
            display_unit=data.get("display_unit", "ft"),
            calibrations=calibrations,
            furniture=[Furniture.from_dict(value) for value in raw_furniture],
        )
        project.validate()
        return project


def clone_furniture(items: Iterable[Furniture]) -> list[Furniture]:
    return [Furniture.from_dict(item.to_dict()) for item in items]
