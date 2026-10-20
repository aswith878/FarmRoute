from enum import Enum


class UserRole(str, Enum):
    FARMER = "FARMER"
    BUYER = "BUYER"
    PROCESSOR = "PROCESSOR"
    ADMIN = "ADMIN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ProduceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PARTIALLY_SOLD = "PARTIALLY_SOLD"
    MATCHING = "MATCHING"
    HIGH_RISK = "HIGH_RISK"
    REROUTING = "REROUTING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class RequirementStatus(str, Enum):
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
