"""Shared pytest fixtures for VantageCV's unit test suite.

All fixtures here are built from verified, pure-Python constructors with no
network/UE5 dependency (see docs in the PR description / plan for the
exploration that established this). Do not add a fixture that constructs
`UE5Bridge` directly without mocking `requests` first.
"""

import random

import pytest

pytest_plugins = ["pytester"]  # enables the `pytester` fixture, used to test
# the autouse fixture below in a genuinely isolated inner pytest session
# (see test_seed_determinism.py::TestAutouseFixtureIsolatesGlobalRandomState)


@pytest.fixture(autouse=True)
def _isolate_global_random_state():
    """Snapshot and restore global `random` state around every test.

    Several controllers in vantagecv/research_v2 (prop_zone_controller.py,
    vehicle_spawn_controller.py, time_augmentation_controller.py,
    weather_augmentation_controller.py) call the GLOBAL random.seed(...)
    directly rather than using an instance-local random.Random(). Without
    this fixture, a test that exercises one of those controllers would leak
    global RNG state into every test that runs after it, making failures
    order-dependent and hard to reproduce.
    """
    state = random.getstate()
    yield
    random.setstate(state)


@pytest.fixture
def camera_config_factory():
    """Factory for a minimal, deterministic CameraConfig.

    Defaults match the hand-verified worked example: camera at world
    origin, fov=90 deg, 100x100 resolution -> fx=fy=cx=cy=50.0.

    NOTE: these defaults (height=0.0, 100x100 resolution) are deliberately
    NOT production-realistic -- CameraSystem.validate() would reject this
    exact config (height < 0.5, resolution < 640x480). That's fine for the
    projection-math tests built on this factory, but means CameraSystem's
    own validate() needs its own dedicated tests with realistic configs
    (see test_camera_system.py::TestValidate) rather than incidentally
    relying on this fixture to exercise it.
    """
    from vantagecv.research_v2.config import CameraConfig

    def _make(**overrides):
        defaults = dict(
            height=0.0,
            x_position=0.0,
            y_position=0.0,
            pitch=0.0,
            yaw=0.0,
            roll=0.0,
            fov=90.0,
            fov_jitter=0.0,
            width=100,
            height_px=100,
        )
        defaults.update(overrides)
        return CameraConfig(**defaults)

    return _make


@pytest.fixture
def camera_system_factory(camera_config_factory):
    """Factory for a CameraSystem built on the deterministic CameraConfig above."""
    from vantagecv.research_v2.camera_system import CameraSystem

    def _make(**config_overrides):
        return CameraSystem(camera_config_factory(**config_overrides))

    return _make


@pytest.fixture
def annotation_config_factory():
    """Factory for AnnotationConfig using its real declared defaults."""
    from vantagecv.research_v2.config import AnnotationConfig

    def _make(**overrides):
        return AnnotationConfig(**overrides)

    return _make


@pytest.fixture
def spawned_vehicle_factory():
    """Factory for a SpawnedVehicle with plain, explicit field values.

    Importing vehicle_spawner.py emits a module-level DeprecationWarning
    (it says the module is superseded by anchor_spawn_controller.py); it's
    filtered globally in pyproject.toml's [tool.pytest.ini_options], not
    here -- by the time this fixture runs, research_v2/__init__.py has
    already imported vehicle_spawner once (module imports are cached), so
    a local catch_warnings() here would be a no-op.
    """
    from vantagecv.research_v2.vehicle_spawner import (
        SpawnedVehicle,
        VehicleDimensions,
        VehicleTransform,
    )
    from vantagecv.research_v2.config import VehicleClass

    def _make(
        instance_id="veh-0",
        vehicle_class=VehicleClass.CAR,
        actor_name="StaticMeshActor_0",
        x=10.0,
        y=0.0,
        z=0.0,
        yaw=0.0,
        pitch=0.0,
        roll=0.0,
        length=4.0,
        width=2.0,
        height=1.0,
        color=(255, 0, 0),
        lane_index=0,
    ):
        return SpawnedVehicle(
            instance_id=instance_id,
            vehicle_class=vehicle_class,
            actor_name=actor_name,
            transform=VehicleTransform(x=x, y=y, z=z, yaw=yaw, pitch=pitch, roll=roll),
            dimensions=VehicleDimensions(length=length, width=width, height=height),
            color=color,
            lane_index=lane_index,
        )

    return _make


@pytest.fixture
def spacing_checker_factory():
    """Factory for a VehicleSpacingChecker with NO network calls.

    Constructing VehicleSpacingChecker itself never touches the network
    (only requests.Session() is created, not used) -- it's the individual
    method calls that would hit HTTP. Tests should pre-populate
    `checker.boundary_offsets[name] = VehicleOffsets(...)` to bypass the
    only network-dependent code path (`_cache_boundary_offsets`).
    """
    from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker

    def _make(**overrides):
        return VehicleSpacingChecker(**overrides)

    return _make


@pytest.fixture
def vehicle_offsets_factory():
    from vantagecv.research_v2.vehicle_spacing import VehicleOffsets

    def _make(front=None, back=None, left=None, right=None):
        return VehicleOffsets(front=front, back=back, left=left, right=right)

    return _make


@pytest.fixture
def vehicle_bounds_factory():
    from vantagecv.research_v2.vehicle_spacing import VehicleBounds

    def _make(
        vehicle_name="veh",
        category="car",
        location=None,
        rotation=None,
        front_boundary=None,
        back_boundary=None,
        left_boundary=None,
        right_boundary=None,
        in_parking_spot=False,
    ):
        return VehicleBounds(
            vehicle_name=vehicle_name,
            category=category,
            location=location or {"X": 0.0, "Y": 0.0, "Z": 0.0},
            rotation=rotation or {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0},
            front_boundary=front_boundary,
            back_boundary=back_boundary,
            left_boundary=left_boundary,
            right_boundary=right_boundary,
            in_parking_spot=in_parking_spot,
        )

    return _make
