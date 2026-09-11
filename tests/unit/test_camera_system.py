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
        # y=-50 (large negative y -> large positive u, far outside width=100)
        result = cam.project_bbox_3d_to_2d(x=10, y=-50, z=0, length=2, width=2, height=2)
        assert result is not None
        x, y, w, h = result
        assert x > 100  # entirely to the right of a 100px-wide frame

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
