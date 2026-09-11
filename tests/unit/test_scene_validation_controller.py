"""Unit tests for vantagecv.research_v2.scene_validation_controller.

Constructing SceneValidationController is network-free (it only builds a
requests.Session, doesn't use it) BUT its default config_path/vehicle_config_path
("configs/levels/automobileV2_anchors_detected.yaml" etc.) resolve to REAL
files that exist in this repo -- so every test here passes explicit
nonexistent paths (via tmp_path) to stay hermetic and avoid depending on
real repo config content that could change independently of this test file.

_validate_locked_background/_validate_zones/_validate_domain_randomization
all make live HTTP calls via self.session.put and are out of scope here
(would need requests-mock, covered separately if ever added as
@pytest.mark.live_ue5 integration tests). This file covers:
  - The pure ValidationStatus/ValidationResult/SceneValidationReport dataclasses.
  - _validate_vehicle_placement's pure underground/overlap math, reached by
    monkeypatching the instance's _get_visible_vehicles (no HTTP at all).
  - validate()'s FAIL-driven scene_valid aggregation, reached by monkeypatching
    all four _validate_* methods directly (also no HTTP).
"""

import pytest

from vantagecv.research_v2.scene_validation_controller import (
    SceneValidationController,
    SceneValidationReport,
    ValidationResult,
    ValidationStatus,
)


@pytest.fixture
def controller_factory(tmp_path):
    def _make(**overrides):
        defaults = dict(
            config_path=str(tmp_path / "no_such_anchors.yaml"),
            vehicle_config_path=str(tmp_path / "no_such_vehicles.yaml"),
        )
        defaults.update(overrides)
        return SceneValidationController(**defaults)

    return _make


class TestValidationStatusAndResult:
    def test_status_values(self):
        assert ValidationStatus.PASS.value == "PASS"
        assert ValidationStatus.FAIL.value == "FAIL"
        assert ValidationStatus.WARN.value == "WARN"
        assert ValidationStatus.SKIP.value == "SKIP"

    def test_result_optional_fields_default_to_none(self):
        result = ValidationResult(name="x", status=ValidationStatus.PASS, message="ok")
        assert result.actor_name is None
        assert result.category is None
        assert result.details is None


class TestSceneValidationReportCounts:
    def _result(self, status):
        return ValidationResult(name="x", status=status, message="m")

    def test_counts_on_empty_report(self):
        report = SceneValidationReport()
        assert report.pass_count == 0
        assert report.fail_count == 0
        assert report.warn_count == 0

    def test_counts_mixed_statuses(self):
        report = SceneValidationReport(
            results=[
                self._result(ValidationStatus.PASS),
                self._result(ValidationStatus.PASS),
                self._result(ValidationStatus.FAIL),
                self._result(ValidationStatus.WARN),
                self._result(ValidationStatus.WARN),
                self._result(ValidationStatus.WARN),
                self._result(ValidationStatus.SKIP),
            ]
        )
        assert report.pass_count == 2
        assert report.fail_count == 1
        assert report.warn_count == 3

    def test_defaults(self):
        report = SceneValidationReport()
        assert report.scene_valid is False
        assert report.failure_reason == ""
        assert report.seed == 0
        assert report.results == []


class TestValidateZonesNetworkFreePaths:
    """_validate_zones has two early-return branches reachable with zero
    HTTP calls, by setting anchor_config directly -- the rest of the
    method (anchor-existence checks) does need a live UE5 connection and
    stays out of scope, per this file's module docstring.
    """

    def test_no_anchor_config_fails(self, controller_factory):
        controller = controller_factory()
        assert controller.anchor_config is None  # confirmed by the hermetic tmp_path fixture

        result = controller._validate_zones()

        assert result.status == ValidationStatus.FAIL
        assert result.message == "No anchor configuration loaded"

    def test_anchor_config_with_zero_zones_fails(self, controller_factory):
        controller = controller_factory()
        # Must be truthy (an empty dict {} is falsy in Python and would
        # incorrectly hit the OTHER early return, "No anchor configuration
        # loaded" -- confirmed the hard way when this test first failed).
        controller.anchor_config = {"parking": {}, "lanes": {}, "sidewalks": {}}

        result = controller._validate_zones()

        assert result.status == ValidationStatus.FAIL
        assert result.message == "No zone anchors defined in config"


class TestGetVehiclePool:
    """Pure, no I/O -- reads self.vehicle_config directly."""

    def test_no_vehicle_config_returns_empty_list(self, controller_factory):
        controller = controller_factory()
        assert controller.vehicle_config is None
        assert controller._get_vehicle_pool() == []

    def test_extracts_names_across_all_five_categories(self, controller_factory):
        controller = controller_factory()
        controller.vehicle_config = {
            "vehicles": {
                "car": [{"name": "Car_1"}, {"name": "Car_2"}],
                "truck": [{"name": "Truck_1"}],
                "bus": [{"name": "Bus_1"}],
                "motorcycle": [{"name": "Moto_1"}],
                "bicycle": [{"name": "Bike_1"}],
            }
        }
        # Iteration order is fixed in source as bicycle, bus, car, motorcycle, truck.
        assert controller._get_vehicle_pool() == [
            "Bike_1", "Bus_1", "Car_1", "Car_2", "Moto_1", "Truck_1",
        ]

    def test_missing_category_is_skipped_not_an_error(self, controller_factory):
        controller = controller_factory()
        controller.vehicle_config = {"vehicles": {"car": [{"name": "Car_1"}]}}
        assert controller._get_vehicle_pool() == ["Car_1"]

    def test_empty_vehicles_dict_returns_empty_list(self, controller_factory):
        controller = controller_factory()
        controller.vehicle_config = {"vehicles": {}}
        assert controller._get_vehicle_pool() == []


class TestValidateVehiclePlacement:
    def _vehicle(self, name, x=0.0, y=0.0, z=0.0):
        return {"name": name, "transform": {"location": {"X": x, "Y": y, "Z": z}}, "visible": True}

    def test_no_vehicles_gives_warn(self, controller_factory, mocker):
        controller = controller_factory()
        mocker.patch.object(controller, "_get_visible_vehicles", return_value=[])

        result = controller._validate_vehicle_placement()

        assert result.status == ValidationStatus.WARN
        assert result.message == "No visible vehicles found"

    def test_underground_vehicle_flagged(self, controller_factory, mocker):
        controller = controller_factory()
        vehicles = [self._vehicle("V1", z=-150.0)]
        mocker.patch.object(controller, "_get_visible_vehicles", return_value=vehicles)

        result = controller._validate_vehicle_placement()

        assert result.status == ValidationStatus.FAIL
        assert result.details["issues"] == ["V1 is underground (Z=-150.0)"]

    def test_underground_boundary_exactly_negative_100_is_not_flagged(self, controller_factory, mocker):
        """Condition is strict `z < -100`, so exactly -100.0 must NOT trigger."""
        controller = controller_factory()
        vehicles = [self._vehicle("V1", z=-100.0)]
        mocker.patch.object(controller, "_get_visible_vehicles", return_value=vehicles)

        result = controller._validate_vehicle_placement()

        assert result.status == ValidationStatus.PASS

    def test_underground_boundary_just_past_negative_100_is_flagged(self, controller_factory, mocker):
        controller = controller_factory()
        vehicles = [self._vehicle("V1", z=-100.01)]
        mocker.patch.object(controller, "_get_visible_vehicles", return_value=vehicles)

        result = controller._validate_vehicle_placement()

        assert result.status == ValidationStatus.FAIL

    def test_overlap_flagged_between_close_vehicles(self, controller_factory, mocker):
        controller = controller_factory()
        vehicles = [self._vehicle("A", x=0.0, y=0.0), self._vehicle("B", x=30.0, y=0.0)]  # dist=30
        mocker.patch.object(controller, "_get_visible_vehicles", return_value=vehicles)

        result = controller._validate_vehicle_placement()

        assert result.status == ValidationStatus.FAIL
        assert result.details["issues"] == ["A and B may be overlapping (dist=30.0cm)"]

    def test_overlap_boundary_exactly_50_is_not_flagged(self, controller_factory, mocker):
        """Condition is strict `dist < 50`, so exactly 50.0cm apart must NOT trigger."""
        controller = controller_factory()
        vehicles = [self._vehicle("A", x=0.0, y=0.0), self._vehicle("B", x=50.0, y=0.0)]
        mocker.patch.object(controller, "_get_visible_vehicles", return_value=vehicles)

        result = controller._validate_vehicle_placement()

        assert result.status == ValidationStatus.PASS

    def test_overlap_boundary_just_under_50_is_flagged(self, controller_factory, mocker):
        controller = controller_factory()
        vehicles = [self._vehicle("A", x=0.0, y=0.0), self._vehicle("B", x=49.99, y=0.0)]
        mocker.patch.object(controller, "_get_visible_vehicles", return_value=vehicles)

        result = controller._validate_vehicle_placement()

        assert result.status == ValidationStatus.FAIL

    def test_multiple_simultaneous_issues_all_counted(self, controller_factory, mocker):
        controller = controller_factory()
        vehicles = [
            self._vehicle("A", x=0.0, y=0.0, z=-200.0),  # underground
            self._vehicle("B", x=10.0, y=0.0, z=0.0),  # overlaps with A (dist=10) and C is far
            self._vehicle("C", x=1000.0, y=0.0, z=0.0),
        ]
        mocker.patch.object(controller, "_get_visible_vehicles", return_value=vehicles)

        result = controller._validate_vehicle_placement()

        assert result.status == ValidationStatus.FAIL
        assert result.message == "Found 2 placement issues"
        assert result.details["issues"] == [
            "A is underground (Z=-200.0)",
            "A and B may be overlapping (dist=10.0cm)",
        ]
        assert result.details["vehicle_count"] == 3

    def test_clean_scene_passes_with_correct_count(self, controller_factory, mocker):
        controller = controller_factory()
        vehicles = [self._vehicle("A", x=0.0, y=0.0), self._vehicle("B", x=1000.0, y=0.0)]
        mocker.patch.object(controller, "_get_visible_vehicles", return_value=vehicles)

        result = controller._validate_vehicle_placement()

        assert result.status == ValidationStatus.PASS
        assert result.message == "2 vehicles validated (no overlaps, not underground)"
        assert result.details == {"vehicle_count": 2}


class TestValidateOverallAggregation:
    """validate()'s scene_valid/failure_reason logic, reached by monkeypatching
    all four _validate_* methods directly so no HTTP call is ever attempted.
    """

    def _patch_validations(self, mocker, controller, *, background, zones, placement, domain_rand):
        mocker.patch.object(controller, "_validate_locked_background", return_value=background)
        mocker.patch.object(controller, "_validate_zones", return_value=zones)
        mocker.patch.object(controller, "_validate_vehicle_placement", return_value=placement)
        mocker.patch.object(controller, "_validate_domain_randomization", return_value=domain_rand)

    def _result(self, status, message="m", name="n"):
        return ValidationResult(name=name, status=status, message=message)

    def test_all_pass_gives_scene_valid_true(self, controller_factory, mocker):
        controller = controller_factory()
        self._patch_validations(
            mocker, controller,
            background=self._result(ValidationStatus.PASS),
            zones=self._result(ValidationStatus.PASS),
            placement=self._result(ValidationStatus.PASS),
            domain_rand=self._result(ValidationStatus.PASS),
        )
        report = controller.validate(seed=7)
        assert report.scene_valid is True
        assert report.failure_reason == ""
        assert report.seed == 7
        assert report.pass_count == 4

    def test_all_warn_still_gives_scene_valid_true(self, controller_factory, mocker):
        """WARN results must never flip scene_valid to False -- only FAIL does."""
        controller = controller_factory()
        self._patch_validations(
            mocker, controller,
            background=self._result(ValidationStatus.WARN),
            zones=self._result(ValidationStatus.WARN),
            placement=self._result(ValidationStatus.WARN),
            domain_rand=self._result(ValidationStatus.WARN),
        )
        report = controller.validate()
        assert report.scene_valid is True
        assert report.warn_count == 4

    def test_one_fail_among_others_flips_scene_valid_false(self, controller_factory, mocker):
        controller = controller_factory()
        self._patch_validations(
            mocker, controller,
            background=self._result(ValidationStatus.PASS),
            zones=self._result(ValidationStatus.FAIL, message="zones broke"),
            placement=self._result(ValidationStatus.WARN),
            domain_rand=self._result(ValidationStatus.PASS),
        )
        report = controller.validate()
        assert report.scene_valid is False
        assert report.failure_reason == "zones broke"

    def test_multiple_fails_join_failure_reason_with_semicolons(self, controller_factory, mocker):
        controller = controller_factory()
        self._patch_validations(
            mocker, controller,
            background=self._result(ValidationStatus.FAIL, message="bg broke"),
            zones=self._result(ValidationStatus.FAIL, message="zones broke"),
            placement=self._result(ValidationStatus.PASS),
            domain_rand=self._result(ValidationStatus.PASS),
        )
        report = controller.validate()
        assert report.scene_valid is False
        assert report.failure_reason == "bg broke; zones broke"

    def test_results_list_contains_all_four_in_order(self, controller_factory, mocker):
        controller = controller_factory()
        self._patch_validations(
            mocker, controller,
            background=self._result(ValidationStatus.PASS, name="Locked Background"),
            zones=self._result(ValidationStatus.PASS, name="Zone Anchors"),
            placement=self._result(ValidationStatus.PASS, name="Vehicle Placement"),
            domain_rand=self._result(ValidationStatus.PASS, name="Domain Randomization"),
        )
        report = controller.validate()
        assert [r.name for r in report.results] == [
            "Locked Background", "Zone Anchors", "Vehicle Placement", "Domain Randomization",
        ]
