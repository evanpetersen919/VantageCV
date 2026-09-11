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
  - A pytester-based test proving conftest.py's autouse
    _isolate_global_random_state fixture actually prevents global seeding
    from leaking into a subsequent, unrelated test, run in a genuinely
    isolated inner pytest session rather than relying on outer-suite
    execution order.
"""

import random
from pathlib import Path

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
    actually prevents cross-test pollution.

    This runs the check in a genuinely isolated INNER pytest session (via
    the built-in `pytester` fixture), rather than as a same-suite ordered
    pair of tests relying on the outer suite's collection order. An
    earlier version of this test WAS an ordered pair sharing a class
    attribute -- correct under this repo's current plugin set (no
    pytest-randomly/pytest-xdist installed), but fragile: a reordering
    plugin could split or shuffle the pair and turn a real isolation
    failure into a confusing, unrelated-looking assertion error instead of
    a clean pass/fail on the actual behavior. The inner session approach
    is order-proof by construction: its two test functions' relative
    order is fixed by the file this test itself writes, independent of
    whatever plugins are active in the outer session running this test.
    """

    def test_fixture_isolates_pollution_in_an_isolated_inner_session(self, pytester):
        project_root = Path(__file__).resolve().parents[2]
        pytester.syspathinsert(project_root)

        pytester.makeconftest(
            """
            from tests.conftest import _isolate_global_random_state
            """
        )
        pytester.makepyfile(
            """
            import random

            _state_before_pollution = None

            def test_1_pollutes_global_random_state():
                global _state_before_pollution
                _state_before_pollution = random.getstate()
                random.seed(31337)
                draw = random.random()
                assert random.getstate() != _state_before_pollution  # sanity: really changed
                assert isinstance(draw, float)

            def test_2_next_test_does_not_see_the_pollution():
                assert _state_before_pollution is not None
                assert random.getstate() == _state_before_pollution
            """
        )

        result = pytester.runpytest("-p", "no:randomly")
        result.assert_outcomes(passed=2)

    def test_isolation_is_load_bearing_not_a_tautology(self, pytester):
        """Companion test: with the real fixture NOT applied (a plain
        no-op replacement in its place), the same two-test pattern must
        FAIL -- proving the pass above is actually caused by the fixture,
        not by some other coincidence (e.g. random.random() happening to
        reset itself, or the test bodies being wrong)."""
        project_root = Path(__file__).resolve().parents[2]
        pytester.syspathinsert(project_root)

        pytester.makeconftest(
            """
            import pytest

            @pytest.fixture(autouse=True)
            def _no_isolation_at_all():
                yield  # deliberately does NOT save/restore random state
            """
        )
        pytester.makepyfile(
            """
            import random

            _state_before_pollution = None

            def test_1_pollutes_global_random_state():
                global _state_before_pollution
                _state_before_pollution = random.getstate()
                random.seed(31337)
                random.random()

            def test_2_next_test_does_not_see_the_pollution():
                assert random.getstate() == _state_before_pollution
            """
        )

        result = pytester.runpytest("-p", "no:randomly")
        result.assert_outcomes(passed=1, failed=1)
