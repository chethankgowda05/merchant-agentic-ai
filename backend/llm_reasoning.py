"""
Optional Claude-API-powered reasoning layer.
If ANTHROPIC_API_KEY is not set, or the call fails for any reason
(bad key, rate limit, network issue), every function here returns None
and the caller falls back to the deterministic template - the app
never breaks because of this layer.
"""
import os
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"  # fast + cheap, right fit for short reasoning text


def _call_claude(prompt: str, max_tokens: int = 200):
    if not ANTHROPIC_API_KEY:
        return None
    try:
        resp = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return " ".join(text_blocks).strip() or None
    except Exception:
        # Never let an LLM hiccup (no credits, rate limit, network issue) break the
        # agent - silently fall back to the deterministic template.
        return None


def generate_decision_reason(opportunity, product_a, product_b, discount_pct):
    prompt = (
        f"You are an AI agent explaining a business decision to a small merchant in plain, "
        f"confident language. Data: {opportunity['support_pct']}% of customers who bought "
        f"'{product_a['name']}' also bought '{product_b['name']}' "
        f"({opportunity['co_occurrences']} of {opportunity['product_a_total_orders']} orders). "
        f"You are proposing a bundle of these two products at a {discount_pct}% discount. "
        f"Write a 2-sentence explanation of why this is a good action for the merchant to take. "
        f"Be specific and reference the actual numbers. No preamble, just the explanation."
    )
    return _call_claude(prompt, max_tokens=120)


def generate_nightly_summary_text(merchant_name, stats, top_opp):
    prompt = (
        f"You are an AI agent giving {merchant_name} a friendly end-of-day business summary. "
        f"Today's facts: {stats['total_orders']} total orders, ~INR {stats['total_revenue']} revenue, "
        f"{stats['actions_executed']} agent actions executed, {stats['actions_blocked']} blocked by "
        f"safety rules, {stats['actions_failed']} failed cleanly. "
        + (
            f"Tomorrow's top opportunity: {top_opp['support_pct']}% of buyers of "
            f"'{top_opp['product_a_name']}' also buy '{top_opp['product_b_name']}'. "
            if top_opp else ""
        )
        + "Write a short, warm, plain-language 3-4 sentence summary a busy shop owner could "
          "read in 10 seconds. Use only the numbers given, do not invent anything. No preamble."
    )
    return _call_claude(prompt, max_tokens=180)
