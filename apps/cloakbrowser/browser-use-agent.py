#!/usr/bin/env python3
"""Run a browser-use natural-language agent against the in-container CDP session."""

from __future__ import annotations

import asyncio
import os
import sys

from browser_use import Agent, BrowserSession, ChatOpenAI


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def required_env(name: str) -> str:
    value = env(name)
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value


async def main() -> int:
    if len(sys.argv) < 2:
        print("usage: browser-use-agent <task>", file=sys.stderr)
        return 2

    task = " ".join(sys.argv[1:]).strip()
    cdp_url = required_env("BROWSER_USE_CDP_URL")
    model = env("BROWSER_USE_LLM_MODEL", env("OPENAI_MODEL", "gpt-5.4-mini"))
    api_key = required_env("OPENAI_API_KEY")
    base_url = required_env("OPENAI_BASE_URL")
    temperature = float(env("BROWSER_USE_LLM_TEMPERATURE", "0.2") or "0.2")
    timeout = float(env("BROWSER_USE_LLM_TIMEOUT", "120") or "120")
    max_steps = int(env("BROWSER_USE_AGENT_MAX_STEPS", "5") or "5")

    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        timeout=timeout,
    )
    browser_session = BrowserSession(cdp_url=cdp_url, keep_alive=False)
    try:
        agent = Agent(
            task=task,
            llm=llm,
            browser_session=browser_session,
            use_vision=env("BROWSER_USE_AGENT_USE_VISION", "false").lower() == "true",
            max_actions_per_step=int(env("BROWSER_USE_AGENT_MAX_ACTIONS_PER_STEP", "3") or "3"),
            llm_timeout=int(timeout),
        )
        history = await agent.run(max_steps=max_steps)

        final_result = None
        if hasattr(history, "final_result"):
            final_result = history.final_result()
        if final_result:
            print(final_result)
        else:
            print(history)
    finally:
        if getattr(browser_session, "initialized", False):
            await browser_session.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
