import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class StateName(str, Enum):
    START = "START"
    GREETING = "GREETING"
    LISTEN = "LISTEN"
    HANDOFF_TO_COMPLETION = "HANDOFF_TO_COMPLETION"
    COLLECT_INFO = "COLLECT_INFO"
    CALL_API_CHECK_SERVICE = "CALL_API_CHECK_SERVICE"
    SERVICE_NOT_FOUND_SUGGEST = "SERVICE_NOT_FOUND_SUGGEST"
    GET_AVAILABILITY = "GET_AVAILABILITY"
    OFFER_SLOTS = "OFFER_SLOTS"
    NO_AVAILABILITY_HANDLE = "NO_AVAILABILITY_HANDLE"
    CONFIRM_SCHEDULE = "CONFIRM_SCHEDULE"
    ANYTHING_ELSE = "ANYTHING_ELSE"
    SUGGEST_ALTERNATIVES = "SUGGEST_ALTERNATIVES"
    WAITLIST_CREATION = "WAITLIST_CREATION"
    END_CONVERSATION = "END_CONVERSATION"
    END = "END"


@dataclass
class Slots:
    customer_name: Optional[str] = None
    contact_address: Optional[str] = None
    contact_number: Optional[str] = None
    service_requested: Optional[str] = None
    problem_description: Optional[str] = None
    preferred_date: Optional[str] = None  # ISO date or human text
    preferred_time: Optional[str] = None  # human text or ISO time
    extra_notes: Optional[str] = None

    def minimal_filled(self) -> bool:
        # Minimal required for an API check (service + at least date or time preference)
        return bool(self.service_requested) and (bool(self.preferred_date) or bool(self.preferred_time))

    def missing_slots(self) -> list[str]:
        required = ["customer_name", "contact_address",
                    "contact_number", "service_requested",
                    "problem_description"]
        # require at least one of preferred_date or preferred_time
        missing = [s for s in required if getattr(self, s) in (None, "")]
        if not (self.preferred_date or self.preferred_time):
            missing.append("preferred_date_or_time")
        return missing


@dataclass
class SessionContext:
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    slots: Slots = field(default_factory=Slots)
    state: StateName = StateName.START
    transcript: list[tuple[str, str]] = field(
        default_factory=list)  # list of (who, text)
    metadata: dict[str, Any] = field(default_factory=dict)
