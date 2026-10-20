"""Environment-configurable prototype rules, not food-safety predictions."""
import os
from dataclasses import dataclass


def positive_setting(name, default):
    try:
        value = int(os.getenv(name, default))
        if value < 1:
            raise ValueError
        return value
    except ValueError:
        raise RuntimeError(f"{name} must be a positive integer.") from None


@dataclass(frozen=True)
class RiskRules:
    cooldown_seconds: int = 60
    failed_attempt_threshold: int = 3
    quality_rejection_threshold: int = 2
    urgent_deadline_days: int = 1
    combined_failure_threshold: int = 2


RULES = RiskRules(
    positive_setting("MATCHING_ATTEMPT_COOLDOWN_SECONDS", 60),
    positive_setting("ROUTING_FAILED_ATTEMPT_THRESHOLD", 3),
    positive_setting("ROUTING_QUALITY_REJECTION_THRESHOLD", 2),
    positive_setting("ROUTING_URGENT_DEADLINE_DAYS", 1),
    positive_setting("ROUTING_COMBINED_FAILURE_THRESHOLD", 2),
)
