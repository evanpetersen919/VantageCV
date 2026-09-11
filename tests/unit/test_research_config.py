"""Unit tests for vantagecv.research_v2.config (ResearchConfig and friends)."""

import math
from pathlib import Path

import pytest

from vantagecv.research_v2.config import (
    AnnotationConfig,
    CameraConfig,
    OutputConfig,
    ResearchConfig,
    SceneConfig,
    TimeOfDay,
    VehicleClass,
    create_default_config,
    load_or_create_config,
)


class TestVehicleClassIdMapping:
    @pytest.mark.parametrize(
        "vehicle_class,expected_id",
        [
            (VehicleClass.CAR, 1),
            (VehicleClass.TRUCK, 2),
            (VehicleClass.BUS, 3),
            (VehicleClass.MOTORCYCLE, 4),
            (VehicleClass.BICYCLE, 5),
        ],
    )
    def test_get_id(self, vehicle_class, expected_id):
        assert VehicleClass.get_id(vehicle_class) == expected_id

    @pytest.mark.parametrize(
        "category_id,expected_class",
        [
            (1, VehicleClass.CAR),
            (2, VehicleClass.TRUCK),
            (3, VehicleClass.BUS),
            (4, VehicleClass.MOTORCYCLE),
            (5, VehicleClass.BICYCLE),
        ],
    )
    def test_from_id_round_trip(self, category_id, expected_class):
        assert VehicleClass.from_id(category_id) == expected_class
        assert VehicleClass.get_id(expected_class) == category_id

    def test_from_id_zero_wraps_to_bicycle(self):
        """KNOWN QUIRK: from_id(0) computes list(cls)[0-1] = list(cls)[-1],
        Python's negative-index wraparound, silently returning BICYCLE
        instead of raising. Documenting current behavior, not endorsing it.
        """
        assert VehicleClass.from_id(0) == VehicleClass.BICYCLE

    def test_from_id_six_raises_index_error(self):
        with pytest.raises(IndexError):
            VehicleClass.from_id(6)

    def test_all_classes_matches_declaration_order(self):
        assert VehicleClass.all_classes() == ["car", "truck", "bus", "motorcycle", "bicycle"]


class TestSceneConfigPostInit:
    def test_default_lane_positions_unchanged(self):
        cfg = SceneConfig()
        assert cfg.lane_positions == [-4.0, 0.0, 4.0]

    @pytest.mark.parametrize(
        "num_lanes,lane_width,expected",
        [
            (2, 4.0, [(0 - 1) * 4.0, (1 - 1) * 4.0]),  # num_lanes//2 = 1
            (4, 4.0, [(0 - 2) * 4.0, (1 - 2) * 4.0, (2 - 2) * 4.0, (3 - 2) * 4.0]),  # //2=2
            (5, 2.0, [(i - 2) * 2.0 for i in range(5)]),  # //2=2
            (1, 4.0, [(0 - 0) * 4.0]),  # //2=0
        ],
    )
    def test_mismatched_lane_positions_recomputed(self, num_lanes, lane_width, expected):
        cfg = SceneConfig(num_lanes=num_lanes, lane_width=lane_width, lane_positions=[])
        assert cfg.lane_positions == expected
        assert len(cfg.lane_positions) == num_lanes

    def test_time_of_day_default(self):
        assert SceneConfig().time_of_day == TimeOfDay.DAY


class TestCameraConfigIntrinsics:
    def test_default_focal_length(self):
        cfg = CameraConfig()  # width=1920, fov=90
        expected = 1920 / (2 * math.tan(math.radians(45.0)))
        assert cfg.focal_length_px == pytest.approx(expected)
        assert cfg.focal_length_px == pytest.approx(960.0)

    def test_intrinsics_dict_default(self):
        cfg = CameraConfig()
        intr = cfg.intrinsics
        assert intr["fx"] == pytest.approx(960.0)
        assert intr["fy"] == pytest.approx(960.0)
        assert intr["cx"] == pytest.approx(960.0)
        assert intr["cy"] == pytest.approx(540.0)
        assert intr["width"] == 1920
        assert intr["height"] == 1080

    def test_intrinsics_custom_fov_and_resolution(self):
        cfg = CameraConfig(fov=60.0, width=800, height_px=600)
        expected_fx = 800 / (2 * math.tan(math.radians(30.0)))
        assert cfg.intrinsics["fx"] == pytest.approx(expected_fx)
        assert cfg.intrinsics["cx"] == 400.0
        assert cfg.intrinsics["cy"] == 300.0


class TestResearchConfigPostInit:
    def test_default_base_dir_rewritten_to_experiment_name(self):
        cfg = ResearchConfig(experiment_name="my_experiment")
        assert cfg.output.base_dir == Path("data/my_experiment")

    def test_custom_base_dir_is_preserved(self):
        cfg = ResearchConfig(
            experiment_name="my_experiment",
            output=OutputConfig(base_dir=Path("somewhere/else")),
        )
        assert cfg.output.base_dir == Path("somewhere/else")

    def test_explicit_default_literal_path_still_gets_overwritten(self):
        """KNOWN QUIRK: __post_init__ compares output.base_dir by VALUE against
        the literal default Path("data/research_v2"), not by whether the
        caller explicitly set it. So passing that exact path alongside a
        custom experiment_name still gets silently overwritten.
        """
        cfg = ResearchConfig(
            experiment_name="custom_name",
            output=OutputConfig(base_dir=Path("data/research_v2")),
        )
        assert cfg.output.base_dir == Path("data/custom_name")
        assert cfg.output.base_dir != Path("data/research_v2")


class TestResearchConfigSerializationRoundTrip:
    def test_to_dict_converts_enums_and_paths(self):
        cfg = ResearchConfig()
        d = cfg.to_dict()
        assert d["scene"]["time_of_day"] == "day"  # Enum -> .value
        assert isinstance(d["output"]["base_dir"], str)  # Path -> str

    def test_save_and_load_round_trip_preserves_values(self, tmp_path):
        cfg = ResearchConfig(experiment_name="roundtrip_test", random_seed=123, num_images=42)
        path = tmp_path / "config.yaml"
        cfg.save(path)

        loaded = ResearchConfig.load(path)

        assert loaded.experiment_name == "roundtrip_test"
        assert loaded.random_seed == 123
        assert loaded.num_images == 42
        assert loaded.scene.time_of_day == cfg.scene.time_of_day
        assert loaded.scene.lane_positions == cfg.scene.lane_positions
        assert loaded.camera.fov == cfg.camera.fov
        assert loaded.vehicles.class_weights == cfg.vehicles.class_weights
        assert loaded.output.base_dir == cfg.output.base_dir
        assert loaded.ue5_host == cfg.ue5_host
        assert loaded.ue5_port == cfg.ue5_port

    def test_from_dict_unknown_key_raises_type_error(self):
        with pytest.raises(TypeError):
            ResearchConfig.from_dict({"camera": {"totally_unknown_key": 1}})

    def test_from_dict_missing_keys_use_dataclass_defaults(self):
        cfg = ResearchConfig.from_dict({})
        assert cfg.experiment_name == "research_v2"
        assert cfg.random_seed == 42
        assert cfg.num_images == 1000


class TestResearchConfigValidate:
    def test_valid_default_config_has_no_issues(self):
        assert create_default_config().validate() == []

    def test_num_lanes_below_one(self):
        cfg = ResearchConfig(scene=SceneConfig(num_lanes=0, lane_positions=[]))
        issues = cfg.validate()
        assert issues == ["Scene must have at least 1 lane"]

    def test_road_length_below_fifty(self):
        cfg = ResearchConfig(scene=SceneConfig(road_length=10.0))
        issues = cfg.validate()
        assert issues == ["Road length should be at least 50m for vehicle variety"]

    def test_class_weights_not_summing_to_one(self):
        from vantagecv.research_v2.config import VehicleSpawnerConfig

        cfg = ResearchConfig(
            vehicles=VehicleSpawnerConfig(class_weights={"car": 0.5, "truck": 0.6})
        )
        issues = cfg.validate()
        assert issues == ["Vehicle class weights must sum to 1.0, got 1.1"]

    def test_class_weights_within_tolerance_is_ok(self):
        from vantagecv.research_v2.config import VehicleSpawnerConfig

        # sums to 1.005, within the 0.01 tolerance
        cfg = ResearchConfig(
            vehicles=VehicleSpawnerConfig(class_weights={"car": 0.505, "truck": 0.5})
        )
        issues = cfg.validate()
        assert issues == []

    def test_fov_out_of_range_low(self):
        cfg = ResearchConfig(camera=CameraConfig(fov=10.0))
        issues = cfg.validate()
        assert issues == ["Camera FOV 10.0 is outside reasonable range [30, 150]"]

    def test_fov_out_of_range_high(self):
        cfg = ResearchConfig(camera=CameraConfig(fov=200.0))
        issues = cfg.validate()
        assert issues == ["Camera FOV 200.0 is outside reasonable range [30, 150]"]

    def test_fov_boundary_values_are_ok(self):
        assert not any(
            "outside reasonable range" in i for i in ResearchConfig(camera=CameraConfig(fov=30.0)).validate()
        )
        assert not any(
            "outside reasonable range" in i for i in ResearchConfig(camera=CameraConfig(fov=150.0)).validate()
        )

    def test_num_images_below_one(self):
        cfg = ResearchConfig(num_images=0)
        issues = cfg.validate()
        assert issues == ["Must generate at least 1 image"]

    def test_multiple_issues_all_reported(self):
        cfg = ResearchConfig(
            num_images=0,
            scene=SceneConfig(num_lanes=0, lane_positions=[]),
            camera=CameraConfig(fov=5.0),
        )
        issues = cfg.validate()
        assert issues == [
            "Scene must have at least 1 lane",
            "Camera FOV 5.0 is outside reasonable range [30, 150]",
            "Must generate at least 1 image",
        ]

    def test_validate_is_never_auto_invoked(self):
        """A deliberately-invalid config (built via from_dict) must not raise
        or self-correct until .validate() is called explicitly."""
        cfg = ResearchConfig.from_dict({"num_images": -5, "camera": {"fov": 999.0}})
        assert cfg.num_images == -5  # not clamped/rejected
        assert cfg.camera.fov == 999.0
        issues = cfg.validate()  # only now do the problems surface
        assert len(issues) >= 2


class TestLoadOrCreateConfig:
    def test_nonexistent_path_returns_default(self, tmp_path):
        cfg = load_or_create_config(tmp_path / "does_not_exist.yaml")
        assert cfg.experiment_name == "research_v2"

    def test_none_path_returns_default(self):
        cfg = load_or_create_config(None)
        assert cfg.experiment_name == "research_v2"

    def test_existing_path_loads_real_file(self, tmp_path):
        original = ResearchConfig(experiment_name="from_file")
        path = tmp_path / "config.yaml"
        original.save(path)

        cfg = load_or_create_config(path)

        assert cfg.experiment_name == "from_file"
