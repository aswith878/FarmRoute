"""Register all models with the shared SQLAlchemy metadata."""
from app.models.user import User
from app.models.produce_batch import ProduceBatch
from app.models.buyer_requirement import BuyerRequirement
from app.models.transaction import Transaction
from app.models.risk_tracking import MatchingAttempt, BuyerRejection
from app.models.routing_case import RoutingCase
from app.models.processor_requirement import ProcessorRequirement
from app.models.alternative_allocation import AlternativeAllocation
from app.models.batch_event import BatchEvent

__all__ = ["User", "ProduceBatch", "BuyerRequirement", "Transaction", "MatchingAttempt", "BuyerRejection", "RoutingCase", "ProcessorRequirement", "AlternativeAllocation", "BatchEvent"]
