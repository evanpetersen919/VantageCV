"""Unit tests for vantagecv.research_v2.camera_system.

All numeric expectations are hand-derived from the exact source (no
rotation matrix exists in this implementation -- see the
test_pitch_yaw_roll_have_no_effect characterization test below, which
locks in a real, verified limitation rather than assuming standard
camera-rotation behavior).
"""

import math

import pytest


class TestIntrinsics:
    def test_default_worked_example_fov90_100x100(self, camera_system_factory):
        cam = camera_system_factory()
        intr = cam.intrinsics
        assert intr.fx == pytest.approx(50.0)
        assert intr.fy == pytest.approx(50.0)
        assert intr.cx == pytest.approx(50.0)
        assert intr.cy == pytest.approx(50.0)

    def test_fy_equals_fx_ignoring_height(self, camera_system_factory):
        """KNOWN QUIRK: fy is computed as fx (reusing the horizontal-FOV-derived
        focal length), not from a separate vertical FOV or aspect ratio --
        even with a non-square resolution.
        """
        cam = camera_system_factory(width=200, height_px=50, fov=90.0)
        intr = cam.intrinsics
        expected_fx = 200 / (2 * math.tan(math.radians(90.0) / 2))
        assert intr.fx == pytest.approx(expected_fx)
        assert intr.fy == pytest.approx(expected_fx)  # same as fx, not derived from height
        assert intr.cx == pytest.approx(100.0)
        assert intr.cy == pytest.approx(25.0)

    def test_narrower_fov_gives_larger_focal_length(self, camera_system_factory):
        cam_wide = camera_system_factory(fov=120.0)
        cam_narrow = camera_system_factory(fov=30.0)
        assert cam_narrow.intrinsics.fx > cam_wide.intrinsics.fx


class TestProjectPoint3dTo2d:
    def test_worked_example_point_in_front(self, camera_system_factory):
        cam = camera_system_factory()
        u, v, depth = cam.project_point_3d_to_2d(10, 0, 0)
        assert (u, v, depth) == (50.0, 50.0, 10.0)

    def test_worked_example_point_behind_camera(self, camera_system_factory):
        cam = camera_system_factory()
        u, v, depth = cam.project_point_3d_to_2d(-5, 0, 0)
        assert (u, v, depth) == (-1, -1, -5)

    def test_depth_exactly_zero_is_treated_as_behind(self, camera_system_factory):
        """Boundary of the `if depth <= 0` check: depth==0 must also return
        the behind-camera sentinel, not attempt a divide-by-zero projection.
        """
        cam = camera_system_factory()
        u, v, depth = cam.project_point_3d_to_2d(0, 0, 0)
        assert (u, v, depth) == (-1, -1, 0)

    def test_lateral_offset_shifts_u(self, camera_system_factory):
        cam = camera_system_factory()
        # cam_x=10, cam_y=-5 -> u = 50*(5/10)+50 = 25+50 = 75.0
        u, v, depth = cam.project_point_3d_to_2d(10, -5, 0)
        assert u == pytest.approx(75.0)
        assert v == pytest.approx(50.0)
        assert depth == pytest.approx(10.0)

    def test_vertical_offset_shifts_v(self, camera_system_factory):
        cam = camera_system_factory()
        # cam_x=10, cam_z=5 -> v = 50*(-5/10)+50 = -25+50 = 25.0
        u, v, depth = cam.project_point_3d_to_2d(10, 0, 5)
        assert u == pytest.approx(50.0)
        assert v == pytest.approx(25.0)

    def test_camera_position_offset_is_translation_only(self, camera_system_factory):
        # Moving the camera to x_position=5 should shift depth by -5
        cam = camera_system_factory(x_position=5.0)
        u, v, depth = cam.project_point_3d_to_2d(10, 0, 0)
        assert depth == pytest.approx(5.0)
        assert u == pytest.approx(50.0)


class TestProjectBbox3dTo2d:
    def test_worked_example(self, camera_system_factory):
        """Camera fov=90, 100x100 -> fx=fy=cx=cy=50.
        Vehicle center x=10,y=0,z=0 (z=bottom per the code -- NOT center,
        despite the method's own docstring), length=4,width=2,height=1.
        8 corners at x in {8,12}, y in {-1,1}, z in {0,1}.
        Hand-derived (see PR description for full derivation):
        expected = (43.75, 43.75, 12.5, 6.25), all exact in float64.
        """
        cam = camera_system_factory()
        result = cam.project_bbox_3d_to_2d(x=10, y=0, z=0, length=4, width=2, height=1)
        assert result == pytest.approx((43.75, 43.75, 12.5, 6.25))

    def test_fully_behind_camera_returns_none(self, camera_system_factory):
        cam = camera_system_factory()
        # x=-10, length=2 -> all 8 corners have world-x in {-11,-9}, all cam_x<0
        result = cam.project_bbox_3d_to_2d(x=-10, y=0, z=0, length=2, width=2, height=2)
        assert result is None

    def test_far_off_axis_bbox_is_not_clipped_or_rejected(self, camera_system_factory):
        """project_bbox_3d_to_2d does NOT check the result against the image
        frame at all -- a bbox entirely outside [0,width]x[0,height] but with
        depth>0 and non-negative u/v is still returned as-is (clip_to_image /
        _validate_bbox are separate, downstream steps in annotation.py).
        """
        cam = camera_system_factory()
        # y=-50 (large negative y -> large positive u, far outside width=100).
        # Hand-derived: corners' cam_x in {9,11}, cam_y in {-51,-49}, cam_z in {0,2}.
        # min_u = 50*(49/11)+50 = 3000/11, max_u = 50*(51/9)+50 = 1000/3,
        # min_v = 50*(-2/9)+50 = 350/9, max_v = 50.0 (dz=0 corners).
        result = cam.project_bbox_3d_to_2d(x=10, y=-50, z=0, length=2, width=2, height=2)
        assert result == pytest.approx((3000 / 11, 350 / 9, 1000 / 3 - 3000 / 11, 100 / 9))
        x, _, _, _ = result
        assert x > 100  # entirely to the right of a 100px-wide frame -- not clipped/rejected

    def test_z_is_box_bottom_not_center(self, camera_system_factory):
        """Confirms the docstring/code discrepancy: passing z=0 with height=8
        produces corners at world-z in {0, 8} ("bottom" hypothesis), not
        {-4, 4} ("center" hypothesis, per the method's own docstring which
        says "z: Center of 3D bbox"). Using length=0, width=0 collapses all
        8 corners to the same (x,y) so cam_x is exactly 10 for every corner
        and v is driven purely by z.

        Bottom hypothesis (actual code): z in {0,8} -> v in {50, 10} -> min_v=10
        Center hypothesis (docstring):    z in {-4,4} -> v in {70, 30} -> min_v=30
        (height=8 chosen, rather than a rounder number, specifically to land
        both candidate v values away from the v>=0 filter's floating-point
        boundary -- see the initial height=10 attempt, which hit that
        boundary exactly and was excluded by the filter instead of measured.)
        """
        cam = camera_system_factory()
        result = cam.project_bbox_3d_to_2d(x=10, y=0, z=0, length=0.0, width=0.0, height=8)
        assert result is not None
        _, min_v, _, height_px = result
        assert min_v == pytest.approx(10.0)  # confirms bottom hypothesis, not center (30.0)
        assert height_px == pytest.approx(40.0)  # 50.0 (z=0) - 10.0 (z=8)

    def test_partial_visibility_mixed_front_and_behind_corners(self, camera_system_factory):
        """A vehicle straddling the camera plane (some corners behind, some
        in front) is a realistic case for anything very close to the camera.
        Vehicle center x=1, length=4 -> back corners at world-x=-1 (behind,
        depth<=0 -> sentinel (-1,-1), filtered out entirely), front corners
        at world-x=3 (in front, real u/v computed). The final bbox must be
        built ONLY from the 4 front corners, not all 8.

        Front corners (y in {-1,1}, z in {0,2}), cam_x=3:
          u = 50*(-y/3)+50 -> y=-1: 200/3; y=1: 100/3
          v = 50*(-z/3)+50 -> z=0: 50;      z=2: 50/3
        Expected: (min_u, min_v, w, h) = (100/3, 50/3, 100/3, 100/3).
        """
        cam = camera_system_factory()
        result = cam.project_bbox_3d_to_2d(x=1, y=0, z=0, length=4, width=2, height=2)
        assert result == pytest.approx((100 / 3, 50 / 3, 100 / 3, 100 / 3))


class TestIsPointInFrame:
    def test_point_inside_frame(self, camera_system_factory):
        cam = camera_system_factory()  # width=100, height_px=100
        assert cam.is_point_in_frame(50.0, 50.0) is True

    def test_lower_bound_zero_is_inside(self, camera_system_factory):
        cam = camera_system_factory()
        assert cam.is_point_in_frame(0.0, 0.0) is True

    def test_negative_is_outside(self, camera_system_factory):
        cam = camera_system_factory()
        assert cam.is_point_in_frame(-0.01, 50.0) is False
        assert cam.is_point_in_frame(50.0, -0.01) is False

    def test_upper_bound_is_half_open_exclusive(self, camera_system_factory):
        """Boundary is `u < width` / `v < height_px` (strict), so u==width
        exactly is OUTSIDE, not inside."""
        cam = camera_system_factory()  # width=100, height_px=100
        assert cam.is_point_in_frame(100.0, 50.0) is False
        assert cam.is_point_in_frame(99.999, 50.0) is True
        assert cam.is_point_in_frame(50.0, 100.0) is False


class TestGetUe5Commands:
    def test_command_shape_and_unit_conversion(self, camera_system_factory):
        """Location must be converted meters -> centimeters (*100); rotation
        stays in degrees unconverted."""
        cam = camera_system_factory(x_position=1.5, y_position=-2.0, height=0.75, pitch=1.0, yaw=2.0, roll=3.0)
        commands = cam.get_ue5_commands()
        assert commands == [
            {
                "type": "set_camera",
                "location": {"x": 150.0, "y": -200.0, "z": 75.0},
                "rotation": {"pitch": 1.0, "yaw": 2.0, "roll": 3.0},
                "fov": cam.config.fov,
                "resolution": {"width": cam.config.width, "height": cam.config.height_px},
            }
        ]

    def test_fov_uses_base_config_before_setup_frame(self, camera_system_factory):
        cam = camera_system_factory(fov=77.0)
        commands = cam.get_ue5_commands()
        assert commands[0]["fov"] == 77.0

    def test_fov_uses_current_state_after_setup_frame(self, camera_system_factory):
        """Once setup_frame() has run, get_ue5_commands must report the
        per-frame (possibly jittered) fov, not the static config fov."""
        cam = camera_system_factory(fov=77.0, fov_jitter=0.0)
        cam.setup_frame(frame_index=0, apply_jitter=False)
        commands = cam.get_ue5_commands()
        assert commands[0]["fov"] == 77.0  # jitter=0 so equal, but now sourced from _current_state


class TestValidate:
    """CameraConfig defaults used by camera_system_factory (height=0.0,
    fov=90.0, width=100, height_px=100) intentionally fail this validator's
    "unrealistic height" and "resolution too low" checks -- that's fine,
    these tests construct their own configs to isolate each check.
    """

    def test_realistic_config_is_valid(self, camera_config_factory):
        from vantagecv.research_v2.camera_system import CameraSystem

        cfg = camera_config_factory(height=1.5, fov=90.0, width=1920, height_px=1080)
        is_valid, issues = CameraSystem(cfg).validate()
        assert is_valid is True
        assert issues == []

    def test_fov_out_of_range(self, camera_config_factory):
        from vantagecv.research_v2.camera_system import CameraSystem

        cfg = camera_config_factory(height=1.5, fov=200.0, width=1920, height_px=1080)
        is_valid, issues = CameraSystem(cfg).validate()
        assert is_valid is False
        assert issues == ["FOV 200.0 outside reasonable range [30, 150]"]

    def test_fov_boundary_values_are_valid(self, camera_config_factory):
        from vantagecv.research_v2.camera_system import CameraSystem

        for fov in (30.0, 150.0):
            cfg = camera_config_factory(height=1.5, fov=fov, width=1920, height_px=1080)
            is_valid, issues = CameraSystem(cfg).validate()
            assert is_valid is True, f"fov={fov} should be valid, got issues={issues}"

    def test_resolution_too_low(self, camera_config_factory):
        from vantagecv.research_v2.camera_system import CameraSystem

        cfg = camera_config_factory(height=1.5, fov=90.0, width=320, height_px=240)
        is_valid, issues = CameraSystem(cfg).validate()
        assert is_valid is False
        assert issues == ["Resolution 320x240 too low"]

    def test_resolution_boundary_is_valid(self, camera_config_factory):
        from vantagecv.research_v2.camera_system import CameraSystem

        cfg = camera_config_factory(height=1.5, fov=90.0, width=640, height_px=480)
        is_valid, issues = CameraSystem(cfg).validate()
        assert is_valid is True

    def test_height_unrealistically_low(self, camera_config_factory):
        from vantagecv.research_v2.camera_system import CameraSystem

        cfg = camera_config_factory(height=0.1, fov=90.0, width=1920, height_px=1080)
        is_valid, issues = CameraSystem(cfg).validate()
        assert is_valid is False
        assert issues == ["Camera height 0.1m unrealistically low"]

    def test_height_boundary_is_valid(self, camera_config_factory):
        from vantagecv.research_v2.camera_system import CameraSystem

        cfg = camera_config_factory(height=0.5, fov=90.0, width=1920, height_px=1080)
        is_valid, issues = CameraSystem(cfg).validate()
        assert is_valid is True

    def test_multiple_issues_all_reported(self, camera_config_factory):
        from vantagecv.research_v2.camera_system import CameraSystem

        cfg = camera_config_factory(height=0.1, fov=200.0, width=320, height_px=240)
        is_valid, issues = CameraSystem(cfg).validate()
        assert is_valid is False
        assert issues == [
            "FOV 200.0 outside reasonable range [30, 150]",
            "Resolution 320x240 too low",
            "Camera height 0.1m unrealistically low",
        ]


class TestPitchYawRollHaveNoEffect:
    def test_yaw_does_not_change_projection(self, camera_system_factory):
        """KNOWN LIMITATION: pitch/yaw/roll are stored on CameraConfig but
        project_point_3d_to_2d / project_bbox_3d_to_2d never read them --
        the camera is hard-assumed to look down world +X. This test locks
        in that CURRENT behavior; it is not asserting this is desirable.
        """
        cam_level = camera_system_factory(yaw=0.0, pitch=0.0, roll=0.0)
        cam_rotated = camera_system_factory(yaw=45.0, pitch=30.0, roll=90.0)
        assert cam_level.project_point_3d_to_2d(10, 3, 2) == cam_rotated.project_point_3d_to_2d(10, 3, 2)
        assert cam_level.project_bbox_3d_to_2d(10, 0, 0, 4, 2, 1) == cam_rotated.project_bbox_3d_to_2d(
            10, 0, 0, 4, 2, 1
        )


class TestSetSeedFovJitter:
    def test_same_seed_gives_identical_jitter_sequence(self, camera_system_factory):
        cam = camera_system_factory(fov_jitter=10.0)
        cam.set_seed(42)
        first_run = [cam._rng.uniform(-10.0, 10.0) for _ in range(20)]
        cam.set_seed(42)
        second_run = [cam._rng.uniform(-10.0, 10.0) for _ in range(20)]
        assert first_run == second_run

    def test_different_seeds_give_different_jitter_sequences(self, camera_system_factory):
        cam = camera_system_factory(fov_jitter=10.0)
        cam.set_seed(1)
        run_a = [cam._rng.uniform(-10.0, 10.0) for _ in range(20)]
        cam.set_seed(2)
        run_b = [cam._rng.uniform(-10.0, 10.0) for _ in range(20)]
        assert run_a != run_b

    def test_setup_frame_without_jitter_uses_base_fov(self, camera_system_factory):
        cam = camera_system_factory(fov=90.0, fov_jitter=10.0)
        state = cam.setup_frame(frame_index=0, apply_jitter=False)
        assert state.fov == pytest.approx(90.0)

    def test_setup_frame_with_zero_jitter_config_uses_base_fov(self, camera_system_factory):
        cam = camera_system_factory(fov=90.0, fov_jitter=0.0)
        state = cam.setup_frame(frame_index=0, apply_jitter=True)
        assert state.fov == pytest.approx(90.0)

    def test_setup_frame_actually_applies_jitter_via_its_own_arithmetic(self, camera_system_factory):
        """The two tests above only exercise the "no jitter" branches.
        This one exercises setup_frame's own `self.config.fov + jitter`
        arithmetic (not just calling cam._rng.uniform directly, which
        bypasses setup_frame entirely) -- fov_jitter=10 with a fixed seed,
        checked against the exact value _rng.uniform would independently
        produce for that seed.
        """
        cam = camera_system_factory(fov=90.0, fov_jitter=10.0)
        cam.set_seed(42)
        state = cam.setup_frame(frame_index=0, apply_jitter=True)

        # Recompute the expected jitter independently with a fresh Random(42)
        # seeded the same way, to avoid relying on setup_frame's own value.
        import random as random_module

        expected_jitter = random_module.Random(42).uniform(-10.0, 10.0)
        assert state.fov == pytest.approx(90.0 + expected_jitter)
        assert state.fov != pytest.approx(90.0)  # confirms jitter was really applied, not skipped
        assert 80.0 <= state.fov <= 100.0  # within [fov-jitter, fov+jitter]

    def test_setup_frame_recomputes_intrinsics_for_jittered_fov(self, camera_system_factory):
        """state.intrinsics must be derived from the JITTERED fov, not the
        base config fov -- otherwise jitter would be cosmetic only."""
        cam = camera_system_factory(fov=90.0, fov_jitter=10.0, width=100)
        cam.set_seed(1)
        state = cam.setup_frame(frame_index=0, apply_jitter=True)

        import math

        expected_fx = 100 / (2 * math.tan(math.radians(state.fov) / 2))
        assert state.intrinsics.fx == pytest.approx(expected_fx)
        assert state.fov != pytest.approx(90.0)  # sanity: jitter actually changed fov for this seed
