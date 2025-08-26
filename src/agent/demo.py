from __future__ import annotations

import asyncio
import json

from agent.core import Agent
from agent.llm import LlmClient


async def main():
    llm = LlmClient(
        model_name="openai/gpt-oss-20b",
        base_url="http://localhost:1234/v1",
    )
    agent = Agent(llm)

    # Simulated user messages for happy path
    ctx = None
    # init the conversation
    ctx, _ = await agent.process("", ctx)

    user_messages = [
        "Hi, I'm Steven Manley. I need to schedule a plumbing appointment.",
        "123 Main Street, Springfield.",
        "555-123-4567",
        "I have a leaky faucet.",
        "I prefer in the morning",
        "Let's go with Option 2",
        "No. That's all. Thanks"
    ]

    for user_message in user_messages:
        ctx, reply = await agent.process(user_message, ctx)

    print("--- Transcript ---")
    for who, text in ctx.transcript:
        print(f"{who}: {text}")
    print()

    print("--- Slots ---")
    print(ctx.slots)
    print()

    print("--- Metadata ---")
    print(json.dumps(ctx.metadata, indent=2))

    # write to csv
    import csv
    with open("transcript.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["Speaker", "Dialogue"])
        for who, text in ctx.transcript:
            writer.writerow([who, text])


if __name__ == "__main__":
    asyncio.run(main())
