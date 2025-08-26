import asyncio
import datetime
import uuid
from typing import Any, Optional


async def check_service(service_name: str) -> dict[str, Any]:
    """Check if the named service exists. Returns {exists: bool, service_id: Optional[str], suggestions: List[str]}"""
    known = {
        "plumb": "plumb_000",
        "repair": "plumb_001",
        "install": "plumb_002",
        "clean": "plumb_003",
        "jet": "plumb_004",
        "re-pipes": "plumb_005",
    }
    lower = (service_name or "").strip().lower()
    if lower in known:
        return {"exists": True, "service_id": known[lower], "suggestions": []}
    return {"exists": False, "service_id": None, "suggestions": list(known.keys())}


async def get_availability(
        service_id: str, date_range: Optional[str] = None,
        branch: Optional[str] = None,
        time_preference: Optional[str] = "") -> dict[str, Any]:
    """Return availability slots for a service_id. {slots: [ {slot_id, start_iso, end_iso, location} ]}
    This is a stubbed schedule generator for demo.
    """
    now = datetime.datetime.now()
    slots = []
    # create 5 slots over the next 7 days
    for i in range(1, 7):
        if time_preference.lower() == "pm":
            slot_dt = ((now + datetime.timedelta(days=i)).replace(hour=13, minute=0, second=0, microsecond=0)
                       + datetime.timedelta(hours=i % 3))
        elif time_preference.lower() == "am":
            slot_dt = ((now + datetime.timedelta(days=i)).replace(hour=8, minute=0, second=0, microsecond=0)
                       + datetime.timedelta(hours=i % 3))
        else:
            slot_dt = ((now + datetime.timedelta(days=i)).replace(hour=8, minute=0, second=0, microsecond=0)
                       + datetime.timedelta(hours=i))
        slots.append({
            "slot_id": f"slot_{service_id}_{i}",
            "start_iso": slot_dt.isoformat(),
            "end_iso": (slot_dt + datetime.timedelta(minutes=45)).isoformat(),
            # "location": branch or "Main Branch"
        })
    return {"slots": slots}


async def create_appointment(customer: dict[str, Any], service_id: str,
                             slot_id: str, contact: Optional[str] = None) -> dict[str, Any]:
    """Create appointment - returns success + appointment id and details."""
    appointment_id = f"ap_{uuid.uuid4().hex[:8]}"
    return {
        "success": True,
        "appointment_id": appointment_id,
        "details": {
            "customer": customer,
            "service_id": service_id,
            "slot_id": slot_id,
            "contact": contact,
        }
    }


async def create_waitlist_entry(customer: dict[str, Any] = {}, service_id: str = '',
                                preferred_window: Optional[str] = None) -> dict[str, Any]:
    entry_id = f"wait_{uuid.uuid4().hex[:8]}"
    return {"success": True, "waitlist_id": entry_id}


async def main():
    service = await check_service("Plumbing")
    print(service)
    service = await check_service("Plumbing service")
    print(service)
    avail = await get_availability(service.get("service_id"))
    print(avail)
    apt = await create_appointment(
        customer={"name": "Will"},
        service_id=service.get("service_id"),
        slot_id=avail.get("slots")[0].get("slot_id"),
    )
    print(apt)
    waitlist = await create_waitlist_entry()
    print(waitlist)


if __name__ == "__main__":
    asyncio.run(main())
