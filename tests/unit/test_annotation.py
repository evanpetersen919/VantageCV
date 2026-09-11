"""Unit tests for vantagecv.research_v2.annotation.

Every numeric expectation here traces to a direct read of annotation.py's
source during test-plan development (see PR description for the full
verified-ground-truth writeup). No value below was guessed.
"""

import json

import pytest

from vantagecv.research_v2.annotation import (
    VEHICLE_DIMENSIONS_3D,
    AnnotationGenerator,
    BoundingBox2D,
    FrameAnnotation,
    InstanceAnnotation,
)
from vantagecv.research_v2.config import VehicleClass


# ---------------------------------------------------------------------------
# BoundingBox2D
# ---------------------------------------------------------------------------

class TestBoundingBox2D:
    def test_area(self):
        bbox = BoundingBox2D(x=10, y=20, width=4, height=5)
        assert bbox.area == 20

    def test_x2_y2(self):
        bbox = BoundingBox2D(x=10, y=20, width=4, height=5)
        assert bbox.x2 == 14
        assert bbox.y2 == 25

    def test_to_coco(self):
        bbox = BoundingBox2D(x=10, y=20, width=4, height=5)
        assert bbox.to_coco() == [10, 20, 4, 5]

    def test_to_dict(self):
        bbox = BoundingBox2D(x=10, y=20, width=4, height=5)
        d = bbox.to_dict()
        assert d == {"x": 10, "y": 20, "width": 4, "height": 5, "area": 20}

    def test_clip_to_image_fully_inside_is_unchanged(self):
        bbox = BoundingBox2D(x=10, y=10, width=20, height=20)
        clipped = bbox.clip_to_image(img_width=100, img_height=100)
        assert (clipped.x, clipped.y, clipped.width, clipped.height) == (10, 10, 20, 20)

    def test_clip_to_image_does_not_mutate_original(self):
        bbox = BoundingBox2D(x=-5, y=-5, width=20, height=20)
        clipped = bbox.clip_to_image(img_width=100, img_height=100)
        assert clipped is not bbox
        assert bbox.x == -5 and bbox.y == -5  # original untouched

    def test_clip_to_image_left_edge(self):
        # x runs from -5 to 15; clipped x should become 0, width shrinks to 15
        bbox = BoundingBox2D(x=-5, y=0, width=20, height=10)
        clipped = bbox.clip_to_image(img_width=100, img_height=100)
        assert clipped.x == 0
        assert clipped.width == 15  # x2(15) - clipped_x(0)
        assert clipped.y == 0
        assert clipped.height == 10

    def test_clip_to_image_right_edge(self):
        # x runs from 90 to 110 in a 100-wide image; x2 clips to 100
        bbox = BoundingBox2D(x=90, y=0, width=20, height=10)
        clipped = bbox.clip_to_image(img_width=100, img_height=100)
        assert clipped.x == 90
        assert clipped.width == 10  # clipped_x2(100) - x(90)

    def test_clip_to_image_top_edge(self):
        bbox = BoundingBox2D(x=0, y=-5, width=10, height=20)
        clipped = bbox.clip_to_image(img_width=100, img_height=100)
        assert clipped.y == 0
        assert clipped.height == 15

    def test_clip_to_image_bottom_edge(self):
        bbox = BoundingBox2D(x=0, y=90, width=10, height=20)
        clipped = bbox.clip_to_image(img_width=100, img_height=100)
        assert clipped.y == 90
        assert clipped.height == 10

    def test_clip_to_image_fully_outside_collapses_to_zero_area(self):
        bbox = BoundingBox2D(x=200, y=200, width=10, height=10)
        clipped = bbox.clip_to_image(img_width=100, img_height=100)
        assert clipped.width == 0
        assert clipped.height == 0
        assert clipped.area == 0

    def test_clip_to_image_negative_region_collapses_to_zero(self):
        bbox = BoundingBox2D(x=-50, y=-50, width=10, height=10)
        clipped = bbox.clip_to_image(img_width=100, img_height=100)
        assert clipped.width == 0
        assert clipped.height == 0

    def test_compute_truncation_no_clipping_is_zero(self):
        original = BoundingBox2D(x=10, y=10, width=20, height=20)
        clipped = original.clip_to_image(img_width=100, img_height=100)
        assert clipped.compute_truncation(original) == pytest.approx(0.0)

    def test_compute_truncation_half_clipped(self):
        # Original spans x in [-10, 10] (width 20); clip to [0, 10] -> half area lost
        original = BoundingBox2D(x=-10, y=0, width=20, height=10)
        clipped = original.clip_to_image(img_width=100, img_height=100)
        # clipped width = 10, height = 10 -> area 100; original area = 200
        assert clipped.area == 100
        assert original.area == 200
        assert clipped.compute_truncation(original) == pytest.approx(0.5)

    def test_compute_truncation_fully_truncated_is_one(self):
        original = BoundingBox2D(x=200, y=200, width=10, height=10)
        clipped = original.clip_to_image(img_width=100, img_height=100)
        assert clipped.compute_truncation(original) == pytest.approx(1.0)

    def test_compute_truncation_zero_area_original_returns_one(self):
        # Guard clause: original.area <= 0 -> 1.0, regardless of self
        original = BoundingBox2D(x=5, y=5, width=0, height=0)
        clipped = original.clip_to_image(img_width=100, img_height=100)
        assert clipped.compute_truncation(original) == 1.0


# ---------------------------------------------------------------------------
# InstanceAnnotation / FrameAnnotation
# ---------------------------------------------------------------------------

class TestInstanceAnnotation:
    def _make(self, **overrides):
        defaults = dict(
            instance_id="v1",
            category_id=1,
            category_name="car",
            bbox=BoundingBox2D(x=1, y=2, width=3, height=4),
            area=12,
            truncation=0.1,
            is_occluded=False,
            is_valid=True,
            validation_issues=[],
        )
        defaults.update(overrides)
        return InstanceAnnotation(**defaults)

    def test_to_coco_annotation_shape(self):
        inst = self._make()
        coco = inst.to_coco_annotation(annotation_id=7, image_id=3)
        assert coco == {
            "id": 7,
            "image_id": 3,
            "category_id": 1,
            "bbox": [1, 2, 3, 4],
            "area": 12,
            "iscrowd": 0,
            "instance_id": "v1",
            "truncation": 0.1,
            "is_occluded": False,
        }

    def test_to_coco_annotation_excludes_validation_fields(self):
        inst = self._make(is_valid=False, validation_issues=["bad"])
        coco = inst.to_coco_annotation(annotation_id=1, image_id=1)
        assert "is_valid" not in coco
        assert "validation_issues" not in coco

    def test_iscrowd_is_always_zero(self):
        inst = self._make()
        assert inst.to_coco_annotation(annotation_id=1, image_id=1)["iscrowd"] == 0

    def test_to_dict_includes_everything(self):
        inst = self._make(is_valid=False, validation_issues=["x", "y"])
        d = inst.to_dict()
        assert d["is_valid"] is False
        assert d["validation_issues"] == ["x", "y"]
        assert d["bbox"] == {"x": 1, "y": 2, "width": 3, "height": 4, "area": 12}


class TestFrameAnnotation:
    def _instance(self, is_valid):
        return InstanceAnnotation(
            instance_id="v",
            category_id=1,
            category_name="car",
            bbox=BoundingBox2D(0, 0, 1, 1),
            area=1,
            truncation=0.0,
            is_occluded=False,
            is_valid=is_valid,
        )

    def test_valid_instances_filters_invalid(self):
        frame = FrameAnnotation(
            frame_index=0,
            image_id=0,
            image_filename="f.png",
            image_width=100,
            image_height=100,
            instances=[self._instance(True), self._instance(False), self._instance(True)],
        )
        assert frame.num_valid == 2
        assert len(frame.valid_instances) == 2
        assert all(i.is_valid for i in frame.valid_instances)

    def test_to_coco_image(self):
        frame = FrameAnnotation(
            frame_index=0, image_id=5, image_filename="f.png",
            image_width=200, image_height=150,
        )
        assert frame.to_coco_image() == {
            "id": 5, "file_name": "f.png", "width": 200, "height": 150,
        }

    def test_to_dict_includes_image_size_tuple(self):
        frame = FrameAnnotation(
            frame_index=0, image_id=0, image_filename="f.png",
            image_width=200, image_height=150,
        )
        d = frame.to_dict()
        assert d["image_size"] == (200, 150)
        assert d["num_instances"] == 0
        assert d["num_valid"] == 0


# ---------------------------------------------------------------------------
# AnnotationGenerator._validate_bbox
# ---------------------------------------------------------------------------

class TestValidateBbox:
    """AnnotationConfig defaults: min_bbox_area=100, min_bbox_dimension=10,
    max_truncation=0.8. CameraConfig used here: width=100, height_px=100
    (via camera_config_factory) so the "outside image" checks are easy to
    hit with small numbers.
    """

    def _gen(self, annotation_config_factory, camera_system_factory):
        cam = camera_system_factory()
        return AnnotationGenerator(config=annotation_config_factory(), camera_config=cam.config)

    def test_valid_bbox_passes_all_checks(self, annotation_config_factory, camera_system_factory):
        gen = self._gen(annotation_config_factory, camera_system_factory)
        bbox = BoundingBox2D(x=10, y=10, width=20, height=20)  # area=400, dims=20
        is_valid, issues = gen._validate_bbox(bbox, truncation=0.0)
        assert is_valid is True
        assert issues == []

    def test_area_below_minimum(self, annotation_config_factory, camera_system_factory):
        gen = self._gen(annotation_config_factory, camera_system_factory)
        # width=11, height=11 -> area=121 >= min_dim(10) each way but area(121) >= 100 too;
        # use a bbox with area strictly below 100 but dims still >= 10 is impossible
        # (10*10=100 is the boundary) so pick width=9,height=9 -> area=81 < 100, dims<10 too
        bbox = BoundingBox2D(x=10, y=10, width=9, height=9)
        is_valid, issues = gen._validate_bbox(bbox, truncation=0.0)
        assert is_valid is False
        assert any("Area" in i for i in issues)

    def test_area_exactly_at_minimum_is_not_flagged(self, annotation_config_factory, camera_system_factory):
        gen = self._gen(annotation_config_factory, camera_system_factory)
        bbox = BoundingBox2D(x=10, y=10, width=10, height=10)  # area=100, dims=10
        is_valid, issues = gen._validate_bbox(bbox, truncation=0.0)
        assert not any("Area" in i for i in issues)
        assert not any("Width" in i for i in issues)
        assert not any("Height" in i for i in issues)
        assert is_valid is True

    def test_width_below_minimum_dimension(self, annotation_config_factory, camera_system_factory):
        gen = self._gen(annotation_config_factory, camera_system_factory)
        bbox = BoundingBox2D(x=10, y=10, width=9, height=20)  # width<10, area=180>=100
        is_valid, issues = gen._validate_bbox(bbox, truncation=0.0)
        assert is_valid is False
        assert any("Width" in i for i in issues)
        assert not any("Height" in i for i in issues)

    def test_height_below_minimum_dimension(self, annotation_config_factory, camera_system_factory):
        gen = self._gen(annotation_config_factory, camera_system_factory)
        bbox = BoundingBox2D(x=10, y=10, width=20, height=9)
        is_valid, issues = gen._validate_bbox(bbox, truncation=0.0)
        assert is_valid is False
        assert any("Height" in i for i in issues)

    def test_truncation_above_maximum(self, annotation_config_factory, camera_system_factory):
        gen = self._gen(annotation_config_factory, camera_system_factory)
        bbox = BoundingBox2D(x=10, y=10, width=20, height=20)
        is_valid, issues = gen._validate_bbox(bbox, truncation=0.81)
        assert is_valid is False
        assert any("Truncation" in i for i in issues)

    def test_truncation_exactly_at_maximum_is_not_flagged(self, annotation_config_factory, camera_system_factory):
        gen = self._gen(annotation_config_factory, camera_system_factory)
        bbox = BoundingBox2D(x=10, y=10, width=20, height=20)
        is_valid, issues = gen._validate_bbox(bbox, truncation=0.8)
        assert not any("Truncation" in i for i in issues)

    def test_bbox_starting_beyond_right_edge(self, annotation_config_factory, camera_system_factory):
        gen = self._gen(annotation_config_factory, camera_system_factory)
        # camera width=100 -> bbox.x >= 100 triggers "completely outside" (check 5)
        bbox = BoundingBox2D(x=100, y=10, width=20, height=20)
        is_valid, issues = gen._validate_bbox(bbox, truncation=0.0)
        assert is_valid is False
        assert any("completely outside" in i for i in issues)

    def test_bbox_starting_beyond_bottom_edge(self, annotation_config_factory, camera_system_factory):
        gen = self._gen(annotation_config_factory, camera_system_factory)
        bbox = BoundingBox2D(x=10, y=100, width=20, height=20)
        is_valid, issues = gen._validate_bbox(bbox, truncation=0.0)
        assert is_valid is False
        assert any("completely outside" in i for i in issues)

    def test_bbox_ending_at_or_before_zero_x(self, annotation_config_factory, camera_system_factory):
        gen = self._gen(annotation_config_factory, camera_system_factory)
        # x + width <= 0 -> "completely outside (negative)" (check 6)
        bbox = BoundingBox2D(x=-20, y=10, width=20, height=20)
        is_valid, issues = gen._validate_bbox(bbox, truncation=0.0)
        assert is_valid is False
        assert any("negative" in i for i in issues)

    def test_multiple_issues_all_reported_together(self, annotation_config_factory, camera_system_factory):
        gen = self._gen(annotation_config_factory, camera_system_factory)
        # tiny bbox AND heavily truncated
        bbox = BoundingBox2D(x=10, y=10, width=5, height=5)
        is_valid, issues = gen._validate_bbox(bbox, truncation=0.9)
        assert is_valid is False
        assert len(issues) >= 3  # area, width, height, truncation all fire


# ---------------------------------------------------------------------------
# AnnotationGenerator._annotate_vehicle
# ---------------------------------------------------------------------------

class _StubCamera:
    """Minimal stand-in for CameraSystem that returns a fixed projection result."""

    def __init__(self, bbox_result):
        self._bbox_result = bbox_result

    def project_bbox_3d_to_2d(self, **kwargs):
        return self._bbox_result


class TestAnnotateVehicle:
    def test_projection_failure_marks_instance_invalid(
        self, annotation_config_factory, camera_config_factory, spawned_vehicle_factory
    ):
        cam_config = camera_config_factory()
        gen = AnnotationGenerator(config=annotation_config_factory(), camera_config=cam_config)
        vehicle = spawned_vehicle_factory(vehicle_class=VehicleClass.CAR)
        stub_camera = _StubCamera(bbox_result=None)

        instance = gen._annotate_vehicle(vehicle, stub_camera)

        assert instance.is_valid is False
        assert instance.validation_issues == ["Projection failed - vehicle not visible"]
        assert (instance.bbox.x, instance.bbox.y, instance.bbox.width, instance.bbox.height) == (0, 0, 0, 0)
        assert instance.area == 0
        assert instance.truncation == 1.0
        assert instance.is_occluded is False
        assert gen._projection_failures == 1

    def test_projection_failure_uses_correct_category_id(
        self, annotation_config_factory, camera_config_factory, spawned_vehicle_factory
    ):
        gen = AnnotationGenerator(config=annotation_config_factory(), camera_config=camera_config_factory())
        vehicle = spawned_vehicle_factory(vehicle_class=VehicleClass.BUS)
        instance = gen._annotate_vehicle(vehicle, _StubCamera(bbox_result=None))
        assert instance.category_id == VehicleClass.get_id(VehicleClass.BUS)
        assert instance.category_name == "bus"

    def test_successful_projection_uses_real_camera_math(
        self, annotation_config_factory, camera_system_factory, spawned_vehicle_factory
    ):
        """End-to-end: real CameraSystem, worked-example numbers.

        Camera: fov=90, 100x100 -> fx=fy=cx=cy=50.0.
        Vehicle: center x=10,y=0,z=0 (z=bottom per code), length=4,width=2,height=1.
        Hand-derived expected bbox (see plan / PR description for full derivation):
        (43.75, 43.75, 12.5, 6.25).
        """
        cam = camera_system_factory()
        gen = AnnotationGenerator(config=annotation_config_factory(), camera_config=cam.config)
        vehicle = spawned_vehicle_factory(x=10.0, y=0.0, z=0.0, length=4.0, width=2.0, height=1.0)

        instance = gen._annotate_vehicle(vehicle, cam)

        assert instance.bbox.x == pytest.approx(43.75)
        assert instance.bbox.y == pytest.approx(43.75)
        assert instance.bbox.width == pytest.approx(12.5)
        assert instance.bbox.height == pytest.approx(6.25)
        assert gen._projection_failures == 0
        # Note: this bbox (area=78.125, height=6.25) is BELOW AnnotationConfig's
        # defaults (min_bbox_area=100, min_bbox_dimension=10), so it is correctly
        # marked invalid by _validate_bbox -- that logic is covered separately in
        # TestValidateBbox. This test only pins the projection geometry itself.
        assert instance.is_valid is False
        assert instance.validation_issues == [
            "Area 78.1 below minimum 100",
            "Height 6.2 below minimum 10",
        ]

    def test_successful_projection_that_also_passes_validation(
        self, annotation_config_factory, camera_system_factory, spawned_vehicle_factory
    ):
        """Second worked example, closer/taller vehicle so the resulting bbox
        clears AnnotationConfig's defaults (area>=100, dims>=10) and is_valid
        ends up True -- covers the "everything succeeds" path end-to-end.

        Camera: fov=90, 100x100 -> fx=fy=cx=cy=50.0 (same as above).
        Vehicle: center x=5,y=0,z=0, length=4,width=2,height=2.
        Corners' cam_x in {3,7}; by hand:
          cam_x=3: u in {50/3, 200/3} = {16.667, 66.667}... (cam_y=+-1 -> u=50*(-cam_y/3)+50)
          cam_y=-1 -> u=50*(1/3)+50=200/3; cam_y=+1 -> u=50*(-1/3)+50=100/3
          cam_z=0 -> v=50; cam_z=2 -> v=50*(-2/3)+50=50/3
          cam_x=7: cam_y=-1 -> u=50*(1/7)+50=400/7; cam_y=+1 -> u=50*(-1/7)+50=300/7
          cam_z=0 -> v=50; cam_z=2 -> v=50*(-2/7)+50=250/7
        us = {100/3, 200/3, 300/7, 400/7} -> min=100/3, max=200/3 -> width=100/3
        vs = {50, 50/3, 250/7} -> min=50/3, max=50 -> height=50-50/3=100/3
        Expected bbox: (100/3, 50/3, 100/3, 100/3) ~= (33.333, 16.667, 33.333, 33.333)
        area ~= 1111.1, well above min_bbox_area=100 and min_bbox_dimension=10.
        """
        cam = camera_system_factory()
        gen = AnnotationGenerator(config=annotation_config_factory(), camera_config=cam.config)
        vehicle = spawned_vehicle_factory(x=5.0, y=0.0, z=0.0, length=4.0, width=2.0, height=2.0)

        instance = gen._annotate_vehicle(vehicle, cam)

        assert instance.bbox.x == pytest.approx(100 / 3)
        assert instance.bbox.y == pytest.approx(50 / 3)
        assert instance.bbox.width == pytest.approx(100 / 3)
        assert instance.bbox.height == pytest.approx(100 / 3)
        assert instance.is_valid is True
        assert instance.validation_issues == []
        assert gen._projection_failures == 0


# ---------------------------------------------------------------------------
# get_coco_categories / export_coco / get_statistics / reset
# ---------------------------------------------------------------------------

class TestGetCocoCategories:
    def test_ids_and_order_match_enum_declaration_order(
        self, annotation_config_factory, camera_config_factory
    ):
        gen = AnnotationGenerator(config=annotation_config_factory(), camera_config=camera_config_factory())
        categories = gen.get_coco_categories()
        assert [c["id"] for c in categories] == [1, 2, 3, 4, 5]
        assert [c["name"] for c in categories] == ["car", "truck", "bus", "motorcycle", "bicycle"]
        assert all(c["supercategory"] == "vehicle" for c in categories)


class TestExportCoco:
    def test_export_includes_only_valid_instances(
        self, annotation_config_factory, camera_config_factory, spawned_vehicle_factory, tmp_path
    ):
        gen = AnnotationGenerator(config=annotation_config_factory(), camera_config=camera_config_factory())
        valid_vehicle = spawned_vehicle_factory(instance_id="valid-1", x=10, y=0, z=0)
        gen.annotate_frame(
            frame_index=0, image_id=0, image_filename="f0.png",
            vehicles=[valid_vehicle], camera=_StubCamera(bbox_result=(10, 10, 20, 20)),
        )
        invalid_vehicle = spawned_vehicle_factory(instance_id="invalid-1")
        gen.annotate_frame(
            frame_index=1, image_id=1, image_filename="f1.png",
            vehicles=[invalid_vehicle], camera=_StubCamera(bbox_result=None),
        )

        out_path = gen.export_coco(tmp_path / "out" / "coco.json")
        data = json.loads(out_path.read_text(encoding="utf-8"))

        assert len(data["images"]) == 2
        assert len(data["annotations"]) == 1
        assert data["annotations"][0]["instance_id"] == "valid-1"

    def test_export_annotation_ids_increment_sequentially_across_frames(
        self, annotation_config_factory, camera_config_factory, spawned_vehicle_factory, tmp_path
    ):
        gen = AnnotationGenerator(config=annotation_config_factory(), camera_config=camera_config_factory())
        stub = _StubCamera(bbox_result=(10, 10, 20, 20))
        for frame_idx in range(3):
            v = spawned_vehicle_factory(instance_id=f"v{frame_idx}")
            gen.annotate_frame(
                frame_index=frame_idx, image_id=frame_idx, image_filename=f"f{frame_idx}.png",
                vehicles=[v], camera=stub,
            )
        out_path = gen.export_coco(tmp_path / "coco.json")
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert [a["id"] for a in data["annotations"]] == [1, 2, 3]

    def test_export_creates_parent_directories(
        self, annotation_config_factory, camera_config_factory, tmp_path
    ):
        gen = AnnotationGenerator(config=annotation_config_factory(), camera_config=camera_config_factory())
        nested = tmp_path / "a" / "b" / "c" / "coco.json"
        out_path = gen.export_coco(nested)
        assert out_path.exists()

    def test_annotation_id_counter_field_stays_zero(
        self, annotation_config_factory, camera_config_factory, spawned_vehicle_factory, tmp_path
    ):
        """KNOWN QUIRK: self._annotation_id_counter is never incremented anywhere
        in annotation.py -- export_coco uses a local counter variable instead.
        This test documents the current (dead-field) behavior; it is not
        asserting the field is useful, just that this is what happens today.
        """
        gen = AnnotationGenerator(config=annotation_config_factory(), camera_config=camera_config_factory())
        v = spawned_vehicle_factory()
        gen.annotate_frame(
            frame_index=0, image_id=0, image_filename="f.png",
            vehicles=[v], camera=_StubCamera(bbox_result=(10, 10, 20, 20)),
        )
        gen.export_coco(tmp_path / "coco.json")
        assert gen._annotation_id_counter == 0


class TestGetStatistics:
    def test_zero_instances_gives_zero_validity_rate_not_crash(
        self, annotation_config_factory, camera_config_factory
    ):
        gen = AnnotationGenerator(config=annotation_config_factory(), camera_config=camera_config_factory())
        stats = gen.get_statistics()
        assert stats["total_instances"] == 0
        assert stats["validity_rate"] == 0.0

    def test_class_distribution_counts_only_valid_instances(
        self, annotation_config_factory, camera_config_factory, spawned_vehicle_factory
    ):
        gen = AnnotationGenerator(config=annotation_config_factory(), camera_config=camera_config_factory())
        valid_car = spawned_vehicle_factory(instance_id="c1", vehicle_class=VehicleClass.CAR)
        invalid_bus = spawned_vehicle_factory(instance_id="b1", vehicle_class=VehicleClass.BUS)
        gen.annotate_frame(
            frame_index=0, image_id=0, image_filename="f.png",
            vehicles=[valid_car], camera=_StubCamera(bbox_result=(10, 10, 20, 20)),
        )
        gen.annotate_frame(
            frame_index=1, image_id=1, image_filename="f2.png",
            vehicles=[invalid_bus], camera=_StubCamera(bbox_result=None),
        )
        stats = gen.get_statistics()
        assert stats["class_distribution"]["car"] == 1
        assert stats["class_distribution"]["bus"] == 0
        assert stats["projection_failures"] == 1
        assert stats["total_instances"] == 2
        assert stats["valid_instances"] == 1
        assert stats["validity_rate"] == pytest.approx(0.5)


class TestReset:
    def test_reset_clears_all_counters_and_frames(
        self, annotation_config_factory, camera_config_factory, spawned_vehicle_factory
    ):
        gen = AnnotationGenerator(config=annotation_config_factory(), camera_config=camera_config_factory())
        gen.annotate_frame(
            frame_index=0, image_id=0, image_filename="f.png",
            vehicles=[spawned_vehicle_factory()], camera=_StubCamera(bbox_result=(10, 10, 20, 20)),
        )
        assert gen._total_instances == 1

        gen.reset()

        assert gen._total_instances == 0
        assert gen._valid_instances == 0
        assert gen._projection_failures == 0
        assert gen._annotation_id_counter == 0
        assert gen._frame_annotations == []


# ---------------------------------------------------------------------------
# Dead-code characterization
# ---------------------------------------------------------------------------

class TestDeadConstants:
    def test_vehicle_dimensions_3d_values_are_correct_but_unused(self):
        """KNOWN QUIRK: VEHICLE_DIMENSIONS_3D is defined but never read by
        AnnotationGenerator (_annotate_vehicle uses vehicle.dimensions
        instead). This test just pins the literal values in case anything
        starts depending on them later.
        """
        assert VEHICLE_DIMENSIONS_3D[VehicleClass.CAR] == (4.5, 1.8, 1.5)
        assert VEHICLE_DIMENSIONS_3D[VehicleClass.TRUCK] == (6.0, 2.2, 2.5)
        assert VEHICLE_DIMENSIONS_3D[VehicleClass.BUS] == (12.0, 2.5, 3.0)
        assert VEHICLE_DIMENSIONS_3D[VehicleClass.MOTORCYCLE] == (2.2, 0.8, 1.2)
        assert VEHICLE_DIMENSIONS_3D[VehicleClass.BICYCLE] == (1.8, 0.6, 1.0)
