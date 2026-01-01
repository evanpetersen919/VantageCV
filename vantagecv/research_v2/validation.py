"""
Research v2 - MODULE 6: Validation & Sanity Checks

Responsibilities:
- Reject frames with:
  - Zero vehicles
  - Invalid bounding boxes
  - Boxes outside image
- Log rejection reasons clearly

Logging (REQUIRED):
- Validation result (PASS / FAIL)
- Failure reason (explicit)
- Affected instance_id(s)

FAIL-FAST PHILOSOPHY:
If any module fails:
- Abort the frame
- Log exact failure cause
- Continue to next frame
- Never silently skip
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .logging_utils import ResearchLogger
from .config import ValidationConfig
from .annotation import FrameAnnotation, InstanceAnnotation


class ValidationResult(Enum):
    """Result of validation check."""
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


@dataclass
class ValidationIssue:
    """Describes a validation issue."""
    severity: ValidationResult
    check_name: str
    message: str
    affected_instances: list[str] = field(default_factory=list)
    suggested_fix: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "check": self.check_name,
            "message": self.message,
            "affected_instances": self.affected_instances,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class FrameValidationResult:
    """Complete validation result for a frame."""
    frame_index: int
    overall_result: ValidationResult
    issues: list[ValidationIssue] = field(default_factory=list)
    checks_passed: int = 0
    checks_failed: int = 0
    checks_warned: int = 0
    
    @property
    def is_valid(self) -> bool:
        return self.overall_result == ValidationResult.PASS
    
    def to_dict(self) -> dict:
        return {
            "frame_index": self.frame_index,
            "result": self.overall_result.value,
            "is_valid": self.is_valid,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "checks_warned": self.checks_warned,
            "issues": [i.to_dict() for i in self.issues],
        }


class FrameValidator:
    """
    MODULE 6 - Frame Validation
    
    Validates frames before accepting into dataset.
    Implements fail-fast philosophy with explicit logging.
    """
    
    MODULE_NAME = "FrameValidator"
    
    def __init__(
        self,
        config: ValidationConfig,
        logger: Optional[ResearchLogger] = None,
    ):
        """
        Initialize validator.
        
        Args:
            config: Validation configuration
            logger: Optional logger
        """
        self.config = config
        self.logger = logger or ResearchLogger(self.MODULE_NAME)
        
        # Statistics
        self._frames_validated = 0
        self._frames_passed = 0
        self._frames_failed = 0
        self._rejection_reasons: dict[str, int] = {}
        
        self.logger.log_init(
            reject_zero_vehicles=config.reject_zero_vehicles,
            reject_all_truncated=config.reject_all_truncated,
            reject_all_occluded=config.reject_all_occluded,
            require_positive_area=config.require_positive_area,
            require_in_frame=config.require_in_frame,
        )
    
    def validate_frame(
        self,
        frame_annotation: FrameAnnotation,
    ) -> FrameValidationResult:
        """
        Validate a frame's annotations.
        
        Args:
            frame_annotation: Frame annotation to validate
            
        Returns:
            FrameValidationResult with pass/fail and issues
        """
        self.logger.info(
            "Validation started",
            frame_index=frame_annotation.frame_index,
            num_instances=len(frame_annotation.instances),
        )
        
        result = FrameValidationResult(
            frame_index=frame_annotation.frame_index,
            overall_result=ValidationResult.PASS,
        )
        
        # Run all validation checks
        checks = [
            self._check_vehicle_count,
            self._check_all_instances_valid,
            self._check_all_truncated,
            self._check_positive_areas,
            self._check_in_frame,
        ]
        
        for check in checks:
            issue = check(frame_annotation)
            if issue:
                result.issues.append(issue)
                
                if issue.severity == ValidationResult.FAIL:
                    result.checks_failed += 1
                    result.overall_result = ValidationResult.FAIL
                elif issue.severity == ValidationResult.WARN:
                    result.checks_warned += 1
                    if result.overall_result == ValidationResult.PASS:
                        result.overall_result = ValidationResult.WARN
                else:
                    result.checks_passed += 1
            else:
                result.checks_passed += 1
        
        # Update statistics
        self._frames_validated += 1
        if result.is_valid:
            self._frames_passed += 1
        else:
            self._frames_failed += 1
            for issue in result.issues:
                if issue.severity == ValidationResult.FAIL:
                    self._rejection_reasons[issue.check_name] = \
                        self._rejection_reasons.get(issue.check_name, 0) + 1
        
        # Log result
        if result.is_valid:
            self.logger.info(
                "Validation PASSED",
                frame_index=frame_annotation.frame_index,
                checks_passed=result.checks_passed,
            )
        else:
            self.logger.error(
                "Validation FAILED",
                frame_index=frame_annotation.frame_index,
                reason=result.issues[0].message if result.issues else "Unknown",
                issues=[i.to_dict() for i in result.issues if i.severity == ValidationResult.FAIL],
                suggested_fix=result.issues[0].suggested_fix if result.issues else None,
            )
        
        return result
    
    def _check_vehicle_count(
        self,
        frame_annotation: FrameAnnotation,
    ) -> Optional[ValidationIssue]:
        """Check that frame has at least one vehicle."""
        if not self.config.reject_zero_vehicles:
            return None
        
        if len(frame_annotation.instances) == 0:
            return ValidationIssue(
                severity=ValidationResult.FAIL,
                check_name="vehicle_count",
                message="Frame has zero vehicles",
                suggested_fix="Increase spawn attempts or reduce rejection rate",
            )
        
        if frame_annotation.num_valid == 0:
            return ValidationIssue(
                severity=ValidationResult.FAIL,
                check_name="valid_vehicle_count",
                message="Frame has no valid vehicle annotations",
                affected_instances=[i.instance_id for i in frame_annotation.instances],
                suggested_fix="Check projection settings or camera position",
            )
        
        return None
    
    def _check_all_instances_valid(
        self,
        frame_annotation: FrameAnnotation,
    ) -> Optional[ValidationIssue]:
        """Check for invalid instances (warning only)."""
        invalid = [i for i in frame_annotation.instances if not i.is_valid]
        
        if invalid:
            return ValidationIssue(
                severity=ValidationResult.WARN,
                check_name="instance_validity",
                message=f"{len(invalid)} of {len(frame_annotation.instances)} instances are invalid",
                affected_instances=[i.instance_id for i in invalid],
            )
        
        return None
    
    def _check_all_truncated(
        self,
        frame_annotation: FrameAnnotation,
    ) -> Optional[ValidationIssue]:
        """Check if all vehicles are heavily truncated."""
        if not self.config.reject_all_truncated:
            return None
        
        valid_instances = frame_annotation.valid_instances
        if not valid_instances:
            return None  # Handled by vehicle_count check
        
        # Check if all are >50% truncated
        all_truncated = all(i.truncation > 0.5 for i in valid_instances)
        
        if all_truncated:
            return ValidationIssue(
                severity=ValidationResult.FAIL,
                check_name="all_truncated",
                message="All vehicles are more than 50% truncated",
                affected_instances=[i.instance_id for i in valid_instances],
                suggested_fix="Adjust camera FOV or vehicle spawn positions",
            )
        
        return None
    
    def _check_positive_areas(
        self,
        frame_annotation: FrameAnnotation,
    ) -> Optional[ValidationIssue]:
        """Check all bboxes have positive area."""
        if not self.config.require_positive_area:
            return None
        
        zero_area = [
            i for i in frame_annotation.valid_instances
            if i.bbox.area <= 0
        ]
        
        if zero_area:
            return ValidationIssue(
                severity=ValidationResult.FAIL,
                check_name="positive_area",
                message=f"{len(zero_area)} bboxes have zero or negative area",
                affected_instances=[i.instance_id for i in zero_area],
                suggested_fix="Check 3D to 2D projection math",
            )
        
        return None
    
    def _check_in_frame(
        self,
        frame_annotation: FrameAnnotation,
    ) -> Optional[ValidationIssue]:
        """Check that bboxes are within image bounds."""
        if not self.config.require_in_frame:
            return None
        
        out_of_frame = []
        img_w = frame_annotation.image_width
        img_h = frame_annotation.image_height
        
        for instance in frame_annotation.valid_instances:
            bbox = instance.bbox
            
            # Check if completely outside
            if (bbox.x >= img_w or bbox.y >= img_h or
                bbox.x + bbox.width <= 0 or bbox.y + bbox.height <= 0):
                out_of_frame.append(instance)
        
        if out_of_frame:
            return ValidationIssue(
                severity=ValidationResult.FAIL,
                check_name="in_frame",
                message=f"{len(out_of_frame)} bboxes are completely outside image",
                affected_instances=[i.instance_id for i in out_of_frame],
                suggested_fix="Check clipping logic in annotation generator",
            )
        
        return None
    
    def get_statistics(self) -> dict:
        """Get validation statistics."""
        return {
            "frames_validated": self._frames_validated,
            "frames_passed": self._frames_passed,
            "frames_failed": self._frames_failed,
            "pass_rate": self._frames_passed / max(self._frames_validated, 1),
            "rejection_reasons": self._rejection_reasons.copy(),
        }
    
    def log_summary(self) -> None:
        """Log validation summary."""
        stats = self.get_statistics()
        
        self.logger.info(
            "Validation summary",
            **stats,
        )
        
        if stats["frames_failed"] > 0:
            self.logger.warning(
                "Frames failed validation",
                count=stats["frames_failed"],
                reasons=stats["rejection_reasons"],
            )
    
    def reset(self) -> None:
        """Reset validation statistics."""
        self._frames_validated = 0
        self._frames_passed = 0
        self._frames_failed = 0
        self._rejection_reasons.clear()
        self.logger.info("Validation statistics reset")
