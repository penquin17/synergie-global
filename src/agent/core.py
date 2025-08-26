from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from typing import Any, Callable, Optional

from agent.data_model import SessionContext, StateName
from agent.llm import LlmClient
from agent.prompts import *
from agent.tools import check_service, create_appointment, get_availability
from agent.utils import parse_json_strict


class StateHandler:
    def __init__(self, llm_client: LlmClient):
        self.llm = llm_client

    async def greeting(self, ctx: SessionContext, user_text: str = '') -> tuple[StateName, str]:
        prompt = f"{SYSTEM_PROMPT}{GREETING_PROMPT}"

        resp = self.llm.run(prompt.strip())
        return (StateName.LISTEN, resp)

    async def listen_and_route(self, ctx: SessionContext, user_text: str) -> tuple[StateName, str]:
        prompt = f"{SYSTEM_PROMPT}{LISTEN_AND_ROUTE_PROMPT}"
        prompt += "\n[Conversation history]\n{hist}\n".format(hist="\n".join([
            ': '.join(d) for d in ctx.transcript
        ]))
        prompt += f"\n[User utterance]\n{user_text}\n"

        raw = self.llm.run(prompt)
        parsed = parse_json_strict(raw)

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
        # print("user_text", user_text)
        # print("intent", intent)
        # print("slots", slots)
        # print()

        for k, v in slots.items():
            if hasattr(ctx.slots, k) and v:
                if not getattr(ctx.slots, k):
                    setattr(ctx.slots, k, v)

        if intent == "book":
            return StateName.COLLECT_INFO, ""
        else:
            return StateName.HANDOFF_TO_COMPLETION, ""

    async def handoff_to_completion(self, ctx: SessionContext, user_text: str) -> tuple[StateName, str]:
        # Use LLM to answer generic queries
        prompt = f"{HANDOFF_TO_COMPLETION_PROMPT}: {user_text}"
        resp = self.llm.run(prompt)
        return StateName.END, resp

    async def collect_info(self, ctx: SessionContext) -> tuple[StateName, str]:
        missing = ctx.slots.missing_slots()
        if not missing:
            return StateName.CALL_API_CHECK_SERVICE, ""
        # Ask for the first missing slot
        to_ask = missing[0]
        prompt = SYSTEM_PROMPT + "\n[Conversation history]\n{hist}\n".format(hist="\n".join([
            ': '.join(d) for d in ctx.transcript
        ])) + REQUEST_INFO_PROMPT
        prompt += f"{to_ask.replace('_', ' ')}?"
        resp = self.llm.run(prompt)
        # if to_ask in ["service_requested", "problem_description"]:
        #     q = "Which service would you like to book?"
        # elif to_ask == "preferred_date_or_time":
        #     q = "Do you have a preferred date or time for the appointment?"
        # else:
        #     q = f"Could you provide {to_ask.replace('_', ' ')}?"
        return StateName.LISTEN, resp

    async def call_api_check_service(self, ctx: SessionContext) -> tuple[StateName, str]:
        serv = ctx.slots.service_requested or ""
        api_resp = await check_service(serv)
        ctx.metadata.setdefault("service_check", api_resp)
        if api_resp.get("exists"):
            ctx.metadata["service_id"] = api_resp.get("service_id")
            return StateName.GET_AVAILABILITY, ""
        else:
            return StateName.SERVICE_NOT_FOUND_SUGGEST, ""

    async def service_not_found_suggest(self, ctx: SessionContext) -> tuple[StateName, str]:
        suggestions = ctx.metadata.get(
            "service_check", {}).get("suggestions", [])
        if not suggestions:
            return StateName.LISTEN, "I'm sorry, I couldn't find that service. Could you rephrase?"
        opts = ", ".join(suggestions[:3])
        return StateName.LISTEN, f"I couldn't find that exact service. Did you mean: {opts}?"

    async def get_availability(self, ctx: SessionContext) -> tuple[StateName, str]:
        service_id = ctx.metadata.get("service_id")
        date_range = ctx.slots.preferred_date
        res = await get_availability(service_id, date_range,
                                     time_preference=ctx.slots.preferred_time)
        ctx.metadata["availability"] = res
        if res.get("slots"):
            return StateName.OFFER_SLOTS, ""
        else:
            return StateName.NO_AVAILABILITY_HANDLE, ""

    async def offer_slots(self, ctx: SessionContext) -> tuple[StateName, str]:
        slots = ctx.metadata.get("availability", {}).get("slots", [])[:3]
        if not slots:
            return StateName.NO_AVAILABILITY_HANDLE, ""
        # craft a user-facing message
        options = []
        for i, s in enumerate(slots, 1):
            dt = s.get("start_iso")
            dt_parsed = dt
            options.append(f"Option {i}: {dt_parsed}")
        text = ("We have the following available slots: " +
                "; ".join(options) + ". Which option would you like?")
        # Save presented options so we can map user choice
        ctx.metadata["presented_slots"] = slots
        return StateName.CONFIRM_SCHEDULE, text

    async def no_availability_handle(self, ctx: SessionContext) -> tuple[StateName, str]:
        return (StateName.LISTEN,
                "Sorry, there are no available slots in your requested window. Would you like me to offer alternatives or join a waitlist?")

    async def confirm_schedule(self, ctx: SessionContext, user_text: Optional[str] = None) -> tuple[StateName, str]:
        # map user selection (e.g., "Option 1" or a datetime) to a slot
        selected = None
        if user_text:
            lower = user_text.lower()
            # try match Option N
            if "option" in lower:
                for token in lower.split():
                    if token.isdigit():
                        idx = int(token) - 1
                        try:
                            selected = ctx.metadata.get(
                                "presented_slots", [])[idx]
                        except Exception:
                            selected = None
            # try parse iso match
            if not selected:
                for s in ctx.metadata.get("presented_slots", []):
                    if s.get("start_iso", "") in user_text:
                        selected = s
        if not selected:
            return StateName.CONFIRM_SCHEDULE, "I didn't catch which slot you preferred. Please say the option number or the date and time."
        # Create appointment
        customer = {
            "name": ctx.slots.customer_name,
            "contact": ctx.slots.contact_number,
        }
        service_id = ctx.metadata.get("service_id")
        resp = await create_appointment(customer, service_id, selected.get("slot_id"), ctx.slots.contact_number)
        if resp.get("success"):
            details = resp.get("details", {})
            ctx.metadata["appointment_id"] = resp.get("appointment_id")
            msg = (f"Your appointment is confirmed for {selected.get('start_iso')}. Reference {resp.get('appointment_id')}. "
                   f"We'll contact you at {ctx.slots.contact_number} if anything changes. Can I help you with anything else?")
            return StateName.ANYTHING_ELSE, msg
        else:
            return StateName.CONFIRM_SCHEDULE, "Sorry, I couldn't create the appointment — would you like me to try a different slot?"

    async def anything_else(self, ctx: SessionContext, user_text: Optional[str] = None) -> tuple[StateName, str]:
        prompt = f"{SYSTEM_PROMPT}{ANYTHING_ELSE_PROMPT}"
        prompt += "\n[Conversation history]\n{hist}\n".format(hist="\n".join([
            ': '.join(d) for d in ctx.transcript
        ]))
        prompt += f"\n[User utterance]\n{user_text}\n"

        raw = self.llm.run(prompt.strip())
        parsed = parse_json_strict(raw)

        if not parsed:
            # fallback simplistic heuristics (very rough)
            lower = user_text.lower()
            if any(word in lower for word in ["no", "nah"]):
                answer = "no"
            elif any(word in lower for word in ["yes", "yeah"]):
                answer = "yes"
            else:
                answer = "other"
        else:
            answer = parsed.get("answer", "other")

        if answer == "no":
            return StateName.END_CONVERSATION, ""
        else:
            return StateName.LISTEN, "Sure! What else can I do for you?"

    async def end_conversation(self, ctx: SessionContext, user_text: Optional[str] = None) -> tuple[StateName, str]:
        prompt = f"{SYSTEM_PROMPT}{END_CONVERSATION_PROMPT}"
        resp = self.llm.run(prompt.strip())
        return StateName.END, resp


class Agent:
    def __init__(self, llm_client: LlmClient):
        self.llm = llm_client
        self.handler = StateHandler(self.llm)

    async def process(self, user_message: str,
                      context: Optional[SessionContext] = None) -> tuple[SessionContext, str]:
        if not context:
            ctx = SessionContext()
            ctx.state = StateName.START
        else:
            ctx = deepcopy(context)

        # START -> GREETING
        if ctx.state == StateName.START:
            ctx.state, greeting_text = await self.handler.greeting(ctx)
            ctx.transcript.append(("assistant", greeting_text))
            return ctx, greeting_text

        # listen loop
        user_text = user_message
        ctx.transcript.append(("user", user_text))
        EOP: bool = False
        while not EOP:
            # central listen state handles many transitions
            if ctx.state == StateName.LISTEN:
                ctx.state, reply = await self.handler.listen_and_route(ctx, user_text)

            # handle state-specific actions
            elif ctx.state == StateName.HANDOFF_TO_COMPLETION:
                ctx.state, reply = await self.handler.handoff_to_completion(ctx, user_text)

            elif ctx.state == StateName.COLLECT_INFO:
                # try collect info - will ask for missing slot if any
                ctx.state, reply = await self.handler.collect_info(ctx)

            elif ctx.state == StateName.CALL_API_CHECK_SERVICE:
                ctx.state, reply = await self.handler.call_api_check_service(ctx)

            elif ctx.state == StateName.SERVICE_NOT_FOUND_SUGGEST:
                ctx.state, reply = await self.handler.service_not_found_suggest(ctx)

            elif ctx.state == StateName.GET_AVAILABILITY:
                ctx.state, reply = await self.handler.get_availability(ctx)

            elif ctx.state == StateName.OFFER_SLOTS:
                ctx.state, reply = await self.handler.offer_slots(ctx)

            elif ctx.state == StateName.NO_AVAILABILITY_HANDLE:
                ctx.state, reply = await self.handler.no_availability_handle(ctx)

            elif ctx.state == StateName.CONFIRM_SCHEDULE:
                ctx.state, reply = await self.handler.confirm_schedule(ctx, user_text)

            elif ctx.state == StateName.ANYTHING_ELSE:
                ctx.state, reply = await self.handler.anything_else(ctx, user_text)

            elif ctx.state == StateName.END_CONVERSATION:
                ctx.state, reply = await self.handler.end_conversation(ctx, user_text)

            elif ctx.state == StateName.END:
                EOP = True
                continue

            else:
                # default fallback
                reply = ""
                ctx.state = StateName.LISTEN

            if reply:
                ctx.transcript.append(("assistant", reply))
                EOP = True
                continue

        return ctx, reply
