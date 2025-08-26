from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Optional

from agent.data_model import SessionContext, StateName
from agent.llm import LlmClient
from agent.prompts import *
from agent.tools import check_service, create_appointment, get_availability
from agent.utils import parse_json_strict

llm = LlmClient(
    model_name="openai/gpt-oss-20b",
    base_url="http://192.168.0.198:1234/v1",
)


def greeting(ctx: SessionContext) -> tuple[StateName, str]:
    return StateName.LISTEN, "Hello! Thank you for calling Jacobs Plumbing. How can I help you today?"


def listen_and_route(ctx: SessionContext, user_text: str) -> tuple[StateName, str]:

    # A prompt template for slot extraction (ask for JSON)
    prompt = LISTEN_AND_ROUTE_PROMPT.strip()
    prompt += f"User utterance: '''{user_text}'''\n"
    raw: str = llm.run(prompt)
    parsed: dict = parse_json_strict(raw)
    if not parsed:
        # fallback simplistic heuristics (very rough)
        lower = user_text.lower()
        if any(word in lower for word in ["book", "appointment", "schedule"]):
            intent = "book"
        else:
            intent = "other"
        slots = {}
    else:
        intent = parsed.get("intent", "other")
        slots = parsed.get("slots", {}) or {}

    # merge extracted slots into context
    for k, v in slots.items():
        if hasattr(ctx.slots, k) and v:
            setattr(ctx.slots, k, v)
    print(ctx)
    if intent == "book":
        return StateName.COLLECT_INFO, ""
    else:
        return StateName.HANDOFF_TO_COMPLETION, ""


def handoff_to_completion(ctx: SessionContext, user_text: str) -> tuple[StateName, str]:
    # Use LLM to answer generic queries
    prompt = f"{HANDOFF_TO_COMPLETION_PROMPT}: {user_text}"
    resp = llm.run(prompt)
    return StateName.LISTEN, resp


def collect_info(ctx: SessionContext, user_text: str = "") -> tuple[StateName, str]:
    missing = ctx.slots.missing_slots()
    if not missing:
        return StateName.CALL_API_CHECK_SERVICE, ""
    # Ask for the first missing slot
    to_ask = missing[0]
    if to_ask == "service_requested":
        q = "Which service would you like to book?"
    elif to_ask == "preferred_date_or_time":
        q = "Do you have a preferred date or time for the appointment?"
    else:
        q = f"Could you provide {to_ask.replace('_', ' ')}?"
    return StateName.LISTEN, q


if __name__ == "__main__":
    context = SessionContext()
    print(greeting(context))

    print(listen_and_route(
        context, "I'm Steven Manley. I need to schedule a plumbing appointment."))

    print(collect_info(
        context, "I'm Steven Manley. I need to schedule a plumbing appointment."))

    print(handoff_to_completion(
        context, "No. That's all. Thanks!"))
