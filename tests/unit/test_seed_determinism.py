"""Seed-determinism and global-RNG-isolation regression tests.

CameraSystem.set_seed's determinism is already covered in
test_camera_system.py::TestSetSeedFovJitter -- not duplicated here.

This file covers:
  - SceneController.initialize() / VehicleSpawner.set_seed(), which each own
    an instance-level random.Random() (no cross-test pollution risk).
  - A real, network-free smoke test per controller that calls the GLOBAL
    random.seed(...) directly (prop_zone_controller.py,
    vehicle_spawn_controller.py, time_augmentation_controller.py,
    weather_augmentation_controller.py) -- each reached via an input that
    makes the method return early (no anchors/no matching state) right
    after the seed call, so no UE5 Remote Control network call happens.
  - A direct, ordered-pair test proving conftest.py's autouse
    _isolate_global_random_state fixture actually prevents that global
    seeding from leaking into a subsequent, unrelated test.
"""

import random

import pytest

from vantagecv.research_v2.config import SceneConfig, VehicleSpawnerConfig
from vantagecv.research_v2.scene_controller import SceneController


class TestSceneControllerDeterminism:
    def test_same_seed_gives_identical_lane_sequence(self):
        controller = SceneController(SceneConfig(num_lanes=3))
        controller.initialize(seed=42)
        first_run = [controller.sample_lane() for _ in range(20)]

        controller.initialize(seed=42)
        second_run = [controller.sample_lane() for _ in range(20)]

        assert first_run == second_run

    def test_different_seeds_give_different_lane_sequences(self):
        controller = SceneController(SceneConfig(num_lanes=3))
        controller.initialize(seed=1)
        run_a = [controller.sample_lane() for _ in range(20)]

        controller.initialize(seed=2)
        run_b = [controller.sample_lane() for _ in range(20)]

        assert run_a != run_b

    def test_scene_id_is_deterministic_from_seed(self):
        controller = SceneController(SceneConfig())
        controller.initialize(seed=42)
        assert controller._state.scene_id == "scene_00000042"


class TestVehicleSpawnerDeterminism:
    def test_same_seed_gives_identical_vehicle_count_sequence(self):
        from vantagecv.research_v2.vehicle_spawner import VehicleSpawner

        spawner = VehicleSpawner(VehicleSpawnerConfig(), SceneConfig())
        spawner.set_seed(42)
        first_run = [spawner.sample_vehicle_count() for _ in range(30)]

        spawner.set_seed(42)
        second_run = [spawner.sample_vehicle_count() for _ in range(30)]

        assert first_run == second_run

    def test_different_seeds_give_different_vehicle_count_sequences(self):
        from vantagecv.research_v2.vehicle_spawner import VehicleSpawner

        spawner = VehicleSpawner(VehicleSpawnerConfig(), SceneConfig())
        spawner.set_seed(1)
        run_a = [spawner.sample_vehicle_count() for _ in range(30)]

        spawner.set_seed(2)
        run_b = [spawner.sample_vehicle_count() for _ in range(30)]

        assert run_a != run_b


class TestGlobalRandomSeedSmokeTests:
    """Each of these controllers calls the GLOBAL random.seed(...) directly
    (confirmed via grep against the real source, not assumed). Each smoke
    test reaches that call with zero UE5/network I/O by choosing inputs
    that make the method return early immediately afterward.
    """

    def test_prop_zone_controller_spawn_barriers(self):
        from vantagecv.research_v2.prop_zone_controller import PropZoneController

        controller = PropZoneController()
        # detected_anchors["barrier"] defaults to [] -> `if not anchors` early-returns
        # right after `random.seed(seed)`, with zero network calls.
        result = controller.spawn_barriers(seed=999)
        assert result.success is True
        assert result.spawned_props == []

    def test_vehicle_spawn_controller_spawn_lane(self, tmp_path):
        from vantagecv.research_v2.vehicle_spawn_controller import VehicleSpawnController

        # Explicit nonexistent config paths: the real default paths resolve to
        # actual repo files (same hermeticity concern as scene_validation_controller).
        controller = VehicleSpawnController(
            anchor_config_path=str(tmp_path / "no_anchors.yaml"),
            vehicle_config_path=str(tmp_path / "no_vehicles.yaml"),
        )
        result = controller.spawn_lane(seed=999)
        assert result.success is False
        assert result.failure_reason == "No lane definitions configured"

    def test_time_augmentation_controller_randomize(self):
        from vantagecv.research_v2.time_augmentation_controller import TimeAugmentationController

        controller = TimeAugmentationController()
        result = controller.randomize(seed=999, allowed_states=["definitely_not_a_real_state"])
        assert result.success is False

    def test_weather_augmentation_controller_randomize(self):
        from vantagecv.research_v2.weather_augmentation_controller import WeatherAugmentationController

        controller = WeatherAugmentationController()
        result = controller.randomize(seed=999, allowed_states=["definitely_not_a_real_state"])
        assert result.success is False


class TestAutouseFixtureIsolatesGlobalRandomState:
    """Proves conftest.py's autouse _isolate_global_random_state fixture
    actually prevents cross-test pollution. This is inherently an
    order-dependent pair of tests (pytest's default collection order is
    file-then-top-to-bottom, which we rely on here) -- if a random-order
    test runner plugin is ever added, this specific pair would need
    `@pytest.mark.order` or similar to stay meaningful.
    """

    _state_before_pollution = None

    def test_1_pollutes_global_random_state(self):
        TestAutouseFixtureIsolatesGlobalRandomState._state_before_pollution = random.getstate()
        random.seed(31337)
        polluted_draw = random.random()
        # Sanity: seeding really did change state (not a no-op).
        assert random.getstate() != TestAutouseFixtureIsolatesGlobalRandomState._state_before_pollution
        assert isinstance(polluted_draw, float)

    def test_2_next_test_does_not_see_the_pollution(self):
        assert TestAutouseFixtureIsolatesGlobalRandomState._state_before_pollution is not None
        # If the autouse fixture works, global state was restored after
        # test_1 finished, so it should match what it was BEFORE test_1
        # polluted it -- not the seed(31337) state.
        assert random.getstate() == TestAutouseFixtureIsolatesGlobalRandomState._state_before_pollution
