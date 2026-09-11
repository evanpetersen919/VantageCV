"""Unit tests for vantagecv.research_v2.vehicle_spacing.

All geometry here is 100% pure (no network I/O). can_place_vehicle /
get_vehicle_bounds are made network-free by pre-populating
checker.boundary_offsets directly, bypassing _cache_boundary_offsets
(the only method that makes HTTP calls) via its cache-hit check
`if vehicle_name not in self.boundary_offsets`.
"""

import math

import pytest


class TestTransformOffset:
    def test_yaw_zero_is_pure_translation(self, spacing_checker_factory):
        checker = spacing_checker_factory()
        result = checker._transform_offset(
            {"X": 2.0, "Y": 1.0, "Z": 0.0}, {"X": 10.0, "Y": 5.0, "Z": 0.0}, {"Yaw": 0.0}
        )
        assert result == {"X": 12.0, "Y": 6.0, "Z": 0.0}

    def test_yaw_90_degrees_rotates_x_onto_y(self, spacing_checker_factory):
        checker = spacing_checker_factory()
        # cos(90)=0, sin(90)=1 -> world_dx = X*0 - Y*1 = -Y; world_dy = X*1 + Y*0 = X
        result = checker._transform_offset(
            {"X": 2.0, "Y": 0.0, "Z": 0.0}, {"X": 0.0, "Y": 0.0, "Z": 0.0}, {"Yaw": 90.0}
        )
        assert result["X"] == pytest.approx(0.0, abs=1e-9)
        assert result["Y"] == pytest.approx(2.0)

    def test_yaw_180_degrees_flips_offset(self, spacing_checker_factory):
        checker = spacing_checker_factory()
        result = checker._transform_offset(
            {"X": 2.0, "Y": 1.0, "Z": 0.0}, {"X": 0.0, "Y": 0.0, "Z": 0.0}, {"Yaw": 180.0}
        )
        assert result["X"] == pytest.approx(-2.0)
        assert result["Y"] == pytest.approx(-1.0)

    def test_yaw_270_degrees_rotates_x_onto_negative_y(self, spacing_checker_factory):
        checker = spacing_checker_factory()
        # cos(270)=0, sin(270)=-1 -> world_dx = X*0 - Y*(-1) = Y; world_dy = X*(-1)+Y*0 = -X
        result = checker._transform_offset(
            {"X": 2.0, "Y": 0.0, "Z": 0.0}, {"X": 0.0, "Y": 0.0, "Z": 0.0}, {"Yaw": 270.0}
        )
        assert result["X"] == pytest.approx(0.0, abs=1e-9)
        assert result["Y"] == pytest.approx(-2.0)

    def test_z_is_unaffected_by_rotation(self, spacing_checker_factory):
        checker = spacing_checker_factory()
        result = checker._transform_offset(
            {"X": 1.0, "Y": 1.0, "Z": 5.0}, {"X": 0.0, "Y": 0.0, "Z": 10.0}, {"Yaw": 45.0}
        )
        assert result["Z"] == 15.0


class TestGetVehicleCorners:
    def test_car_uses_half_width_default_when_no_left_right(self, vehicle_bounds_factory):
        from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker

        checker = VehicleSpacingChecker()
        # front/back 10 units apart along X (forward axis = +X), no left/right
        bounds = vehicle_bounds_factory(
            category="car",
            front_boundary={"X": 5.0, "Y": 0.0, "Z": 0.0},
            back_boundary={"X": -5.0, "Y": 0.0, "Z": 0.0},
        )
        corners = checker._get_vehicle_corners(bounds)
        assert corners is not None
        # HALF_WIDTHS["car"] = 110.0; perpendicular to +X forward is +Y (px,py = -dy,dx = 0,1)
        assert set(corners) == {
            (5.0, 110.0), (5.0, -110.0), (-5.0, 110.0), (-5.0, -110.0),
        }

    def test_truck_default_half_width(self, vehicle_bounds_factory):
        from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker

        checker = VehicleSpacingChecker()
        bounds = vehicle_bounds_factory(
            category="truck",
            front_boundary={"X": 5.0, "Y": 0.0, "Z": 0.0},
            back_boundary={"X": -5.0, "Y": 0.0, "Z": 0.0},
        )
        corners = checker._get_vehicle_corners(bounds)
        assert set(corners) == {
            (5.0, 140.0), (5.0, -140.0), (-5.0, 140.0), (-5.0, -140.0),
        }

    def test_unknown_category_falls_back_to_110(self, vehicle_bounds_factory):
        from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker

        checker = VehicleSpacingChecker()
        bounds = vehicle_bounds_factory(
            category="totally_unknown",
            front_boundary={"X": 5.0, "Y": 0.0, "Z": 0.0},
            back_boundary={"X": -5.0, "Y": 0.0, "Z": 0.0},
        )
        corners = checker._get_vehicle_corners(bounds)
        assert set(corners) == {
            (5.0, 110.0), (5.0, -110.0), (-5.0, 110.0), (-5.0, -110.0),
        }

    def test_car_uses_actual_left_right_when_present(self, vehicle_bounds_factory):
        from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker

        checker = VehicleSpacingChecker()
        bounds = vehicle_bounds_factory(
            category="car",
            front_boundary={"X": 5.0, "Y": 0.0, "Z": 0.0},
            back_boundary={"X": -5.0, "Y": 0.0, "Z": 0.0},
            left_boundary={"X": 0.0, "Y": -95.0, "Z": 0.0},
            right_boundary={"X": 0.0, "Y": 95.0, "Z": 0.0},
        )
        corners = checker._get_vehicle_corners(bounds)
        # center=(0,0); half_width_l = dist((0,-95),(0,0)) = 95; half_width_r = 95;
        # max(95, 95, 90.0) = 95.0 (the actual measured value wins over the 90.0 floor)
        assert set(corners) == {
            (5.0, 95.0), (5.0, -95.0), (-5.0, 95.0), (-5.0, -95.0),
        }

    def test_car_floor_of_90_wins_when_measured_width_is_smaller(self, vehicle_bounds_factory):
        from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker

        checker = VehicleSpacingChecker()
        bounds = vehicle_bounds_factory(
            category="car",
            front_boundary={"X": 5.0, "Y": 0.0, "Z": 0.0},
            back_boundary={"X": -5.0, "Y": 0.0, "Z": 0.0},
            left_boundary={"X": 0.0, "Y": -20.0, "Z": 0.0},
            right_boundary={"X": 0.0, "Y": 20.0, "Z": 0.0},
        )
        corners = checker._get_vehicle_corners(bounds)
        # measured half-width=20 < floor 90.0 -> floor wins
        assert set(corners) == {
            (5.0, 90.0), (5.0, -90.0), (-5.0, 90.0), (-5.0, -90.0),
        }

    def test_degenerate_front_equals_back_returns_none(self, vehicle_bounds_factory):
        from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker

        checker = VehicleSpacingChecker()
        bounds = vehicle_bounds_factory(
            category="car",
            front_boundary={"X": 1.0, "Y": 1.0, "Z": 0.0},
            back_boundary={"X": 1.0, "Y": 1.0, "Z": 0.0},  # length ~0 -> < 0.01 threshold
        )
        assert checker._get_vehicle_corners(bounds) is None

    def test_missing_front_or_back_returns_none(self, vehicle_bounds_factory):
        from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker

        checker = VehicleSpacingChecker()
        bounds = vehicle_bounds_factory(category="car", front_boundary={"X": 5.0, "Y": 0.0, "Z": 0.0})
        assert checker._get_vehicle_corners(bounds) is None

    def test_bicycle_with_all_four_boundaries(self, vehicle_bounds_factory):
        from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker

        checker = VehicleSpacingChecker()
        bounds = vehicle_bounds_factory(
            category="bicycle",
            front_boundary={"X": 3.0, "Y": 0.0, "Z": 0.0},
            back_boundary={"X": -3.0, "Y": 0.0, "Z": 0.0},
            left_boundary={"X": 0.0, "Y": -25.0, "Z": 0.0},
            right_boundary={"X": 0.0, "Y": 25.0, "Z": 0.0},
        )
        corners = checker._get_vehicle_corners(bounds)
        # half_width = max(25, 25, 40.0 floor) = 40.0 (bike floor wins here)
        assert set(corners) == {
            (3.0, 40.0), (3.0, -40.0), (-3.0, 40.0), (-3.0, -40.0),
        }

    def test_bicycle_missing_left_right_falls_through_to_car_style_branch(self, vehicle_bounds_factory):
        """KNOWN QUIRK: if category is "bicycle"/"motorcycle" but left/right
        boundaries are incomplete, the code has no `else: return None` after
        the bike branch's `if all([...])` -- it falls through to the
        car/truck/bus branch below, which uses HALF_WIDTHS.get(category, 110.0).
        Since "bicycle" isn't a key in HALF_WIDTHS, this silently uses the
        110.0 default meant for unknown categories, not the bike-specific
        40.0 floor.
        """
        from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker

        checker = VehicleSpacingChecker()
        bounds = vehicle_bounds_factory(
            category="bicycle",
            front_boundary={"X": 3.0, "Y": 0.0, "Z": 0.0},
            back_boundary={"X": -3.0, "Y": 0.0, "Z": 0.0},
            # left/right omitted -> `all([...])` is False -> falls through
        )
        corners = checker._get_vehicle_corners(bounds)
        assert set(corners) == {
            (3.0, 110.0), (3.0, -110.0), (-3.0, 110.0), (-3.0, -110.0),
        }


class TestProjectCorners:
    def test_axis_aligned_projection(self, spacing_checker_factory):
        checker = spacing_checker_factory()
        corners = [(0.0, 0.0), (10.0, 0.0), (0.0, 5.0), (10.0, 5.0)]
        min_p, max_p = checker._project_corners(corners, axis=(1.0, 0.0))
        assert (min_p, max_p) == (0.0, 10.0)

    def test_diagonal_axis_projection(self, spacing_checker_factory):
        checker = spacing_checker_factory()
        # projecting (3,4) onto unit axis (0.6,0.8): dot = 3*0.6+4*0.8 = 1.8+3.2 = 5.0
        corners = [(3.0, 4.0)]
        min_p, max_p = checker._project_corners(corners, axis=(0.6, 0.8))
        assert min_p == pytest.approx(5.0)
        assert max_p == pytest.approx(5.0)


class TestCheckCollision:
    def _bounds(self, vehicle_bounds_factory, x, y, front_x=None, back_x=None):
        front_x = x + 2.0 if front_x is None else front_x
        back_x = x - 2.0 if back_x is None else back_x
        return vehicle_bounds_factory(
            category="car",
            location={"X": x, "Y": y, "Z": 0.0},
            front_boundary={"X": front_x, "Y": y, "Z": 0.0},
            back_boundary={"X": back_x, "Y": y, "Z": 0.0},
        )

    def test_clearly_non_overlapping_boxes(self, spacing_checker_factory, vehicle_bounds_factory):
        checker = spacing_checker_factory()
        # Both cars 4m long (half-width 110cm each), 1000cm apart in X -> no overlap
        proposed = self._bounds(vehicle_bounds_factory, x=0.0, y=0.0)
        existing = self._bounds(vehicle_bounds_factory, x=1000.0, y=0.0)
        assert checker._check_collision(proposed, existing) is False

    def test_clearly_overlapping_boxes(self, spacing_checker_factory, vehicle_bounds_factory):
        checker = spacing_checker_factory()
        proposed = self._bounds(vehicle_bounds_factory, x=0.0, y=0.0)
        existing = self._bounds(vehicle_bounds_factory, x=1.0, y=0.0)  # nearly identical position
        assert checker._check_collision(proposed, existing) is True

    def test_margin_boundary_just_inside_still_collides(self, spacing_checker_factory, vehicle_bounds_factory):
        """Forward axis is +X (front-back), half-length=2 for each car (front/back
        at x+-2). With a 50cm MARGIN added only to the proposed box's projection,
        two cars whose forward-axis gap is smaller than the margin should still
        register a collision on that axis (though the perpendicular axis is also
        tested -- since Y offset is 0 here, only the forward axis matters).
        """
        checker = spacing_checker_factory()
        # proposed spans X in [-2,2]; existing spans X in [4.49, 8.49] (back=4.49)
        # gap between proposed.front(2) and existing.back(4.49) = 2.49 < MARGIN(50)
        proposed = self._bounds(vehicle_bounds_factory, x=0.0, y=0.0)
        existing = self._bounds(vehicle_bounds_factory, x=6.49, y=0.0)
        assert checker._check_collision(proposed, existing) is True

    def test_distance_fallback_used_when_corners_missing(self, spacing_checker_factory, vehicle_bounds_factory):
        checker = spacing_checker_factory()
        # No front/back boundaries on either side -> _get_vehicle_corners returns None
        # for both -> falls back to straight-line distance vs MIN_SAFE_DIST=500.0
        close = vehicle_bounds_factory(category="car", location={"X": 0.0, "Y": 0.0, "Z": 0.0})
        far = vehicle_bounds_factory(category="car", location={"X": 499.0, "Y": 0.0, "Z": 0.0})
        assert checker._check_collision(close, far) is True  # 499 < 500

        far_enough = vehicle_bounds_factory(category="car", location={"X": 501.0, "Y": 0.0, "Z": 0.0})
        assert checker._check_collision(close, far_enough) is False  # 501 >= 500

    def test_distance_fallback_exact_boundary_is_not_a_collision(
        self, spacing_checker_factory, vehicle_bounds_factory
    ):
        checker = spacing_checker_factory()
        close = vehicle_bounds_factory(category="car", location={"X": 0.0, "Y": 0.0, "Z": 0.0})
        exactly_500 = vehicle_bounds_factory(category="car", location={"X": 500.0, "Y": 0.0, "Z": 0.0})
        # condition is strict `dist < MIN_SAFE_DIST`, so exactly 500.0 is NOT a collision
        assert checker._check_collision(close, exactly_500) is False


class TestCanPlaceVehicle:
    def test_parking_spot_short_circuits_to_true(self, spacing_checker_factory):
        checker = spacing_checker_factory()
        result = checker.can_place_vehicle(
            "v1", "car", {"X": 0, "Y": 0, "Z": 0}, {"Yaw": 0, "Pitch": 0, "Roll": 0},
            existing_vehicles=[], in_parking_spot=True,
        )
        assert result is True

    def test_existing_vehicle_in_parking_spot_is_skipped(
        self, spacing_checker_factory, vehicle_offsets_factory, vehicle_bounds_factory
    ):
        checker = spacing_checker_factory()
        checker.boundary_offsets["v1"] = vehicle_offsets_factory(
            front={"X": 2.0, "Y": 0.0, "Z": 0.0}, back={"X": -2.0, "Y": 0.0, "Z": 0.0}
        )
        # existing vehicle occupies the EXACT same space but is in_parking_spot=True
        existing = vehicle_bounds_factory(
            category="car", location={"X": 0.0, "Y": 0.0, "Z": 0.0},
            front_boundary={"X": 2.0, "Y": 0.0, "Z": 0.0},
            back_boundary={"X": -2.0, "Y": 0.0, "Z": 0.0},
            in_parking_spot=True,
        )
        result = checker.can_place_vehicle(
            "v1", "car", {"X": 0.0, "Y": 0.0, "Z": 0.0}, {"Yaw": 0.0},
            existing_vehicles=[existing], in_parking_spot=False,
        )
        assert result is True  # would collide, but existing.in_parking_spot skips the check

    def test_unknown_category_rejected_for_safety(self, spacing_checker_factory, vehicle_offsets_factory):
        """get_vehicle_bounds returns None for an unrecognized category (falls
        into the `else: return None` branch), and can_place_vehicle's
        `if not proposed_bounds: return False` then rejects it -- confirmed by
        reading the exact source before writing this assertion, not assumed.
        """
        checker = spacing_checker_factory()
        checker.boundary_offsets["v1"] = vehicle_offsets_factory(
            front={"X": 2.0, "Y": 0.0, "Z": 0.0}, back={"X": -2.0, "Y": 0.0, "Z": 0.0}
        )
        result = checker.can_place_vehicle(
            "v1", "spaceship", {"X": 0.0, "Y": 0.0, "Z": 0.0}, {"Yaw": 0.0},
            existing_vehicles=[], in_parking_spot=False,
        )
        assert result is False

    def test_no_collision_with_far_away_existing_vehicle(
        self, spacing_checker_factory, vehicle_offsets_factory, vehicle_bounds_factory
    ):
        checker = spacing_checker_factory()
        checker.boundary_offsets["v1"] = vehicle_offsets_factory(
            front={"X": 2.0, "Y": 0.0, "Z": 0.0}, back={"X": -2.0, "Y": 0.0, "Z": 0.0}
        )
        existing = vehicle_bounds_factory(
            category="car", location={"X": 1000.0, "Y": 0.0, "Z": 0.0},
            front_boundary={"X": 1002.0, "Y": 0.0, "Z": 0.0},
            back_boundary={"X": 998.0, "Y": 0.0, "Z": 0.0},
        )
        result = checker.can_place_vehicle(
            "v1", "car", {"X": 0.0, "Y": 0.0, "Z": 0.0}, {"Yaw": 0.0},
            existing_vehicles=[existing], in_parking_spot=False,
        )
        assert result is True

    def test_collision_with_nearby_existing_vehicle(
        self, spacing_checker_factory, vehicle_offsets_factory, vehicle_bounds_factory
    ):
        checker = spacing_checker_factory()
        checker.boundary_offsets["v1"] = vehicle_offsets_factory(
            front={"X": 2.0, "Y": 0.0, "Z": 0.0}, back={"X": -2.0, "Y": 0.0, "Z": 0.0}
        )
        existing = vehicle_bounds_factory(
            category="car", location={"X": 1.0, "Y": 0.0, "Z": 0.0},
            front_boundary={"X": 3.0, "Y": 0.0, "Z": 0.0},
            back_boundary={"X": -1.0, "Y": 0.0, "Z": 0.0},
        )
        result = checker.can_place_vehicle(
            "v1", "car", {"X": 0.0, "Y": 0.0, "Z": 0.0}, {"Yaw": 0.0},
            existing_vehicles=[existing], in_parking_spot=False,
        )
        assert result is False

    def test_boundary_offsets_cache_is_reused_not_requeried(
        self, spacing_checker_factory, vehicle_offsets_factory
    ):
        """Confirms the cache-hit path: pre-populating boundary_offsets means
        get_vehicle_bounds never calls _cache_boundary_offsets (and therefore
        never touches the network) for a vehicle_name already in the dict."""
        checker = spacing_checker_factory()
        checker.boundary_offsets["v1"] = vehicle_offsets_factory(
            front={"X": 2.0, "Y": 0.0, "Z": 0.0}, back={"X": -2.0, "Y": 0.0, "Z": 0.0}
        )
        bounds = checker.get_vehicle_bounds(
            "v1", "car", {"X": 5.0, "Y": 5.0, "Z": 0.0}, {"Yaw": 0.0}
        )
        assert bounds is not None
        assert bounds.front_boundary == {"X": 7.0, "Y": 5.0, "Z": 0.0}
        assert bounds.back_boundary == {"X": 3.0, "Y": 5.0, "Z": 0.0}


class TestDefaultDimensionFallback:
    def test_cache_boundary_offsets_uses_defaults_when_no_cubes_found(self, spacing_checker_factory, mocker):
        """_cache_boundary_offsets falls back to DEFAULT_LENGTHS/DEFAULT_WIDTHS
        when _get_cube_component_offsets returns empty -- mock only that one
        network-touching helper, not requests itself.
        """
        checker = spacing_checker_factory()
        mocker.patch.object(checker, "_get_cube_component_offsets", return_value={})

        result = checker._cache_boundary_offsets("v1", "car")

        assert result is True
        offsets = checker.boundary_offsets["v1"]
        # DEFAULT_LENGTHS["car"]=450.0 -> half_length=225.0
        assert offsets.front == {"X": 225.0, "Y": 0.0, "Z": 0.0}
        assert offsets.back == {"X": -225.0, "Y": 0.0, "Z": 0.0}
        assert offsets.left is None  # only bikes get left/right in the fallback
        assert offsets.right is None

    def test_bicycle_default_includes_left_right(self, spacing_checker_factory, mocker):
        checker = spacing_checker_factory()
        mocker.patch.object(checker, "_get_cube_component_offsets", return_value={})

        checker._cache_boundary_offsets("bike1", "bicycle")

        offsets = checker.boundary_offsets["bike1"]
        # DEFAULT_WIDTHS["bicycle"]=60.0 -> half_width=30.0
        assert offsets.left == {"X": 0.0, "Y": -30.0, "Z": 0.0}
        assert offsets.right == {"X": 0.0, "Y": 30.0, "Z": 0.0}
