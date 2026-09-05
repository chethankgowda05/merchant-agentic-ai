"""
Merchant Revenue Growth Agent - API
Run with: uvicorn main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime

import agent
import razorpay_client

app = FastAPI(title="Merchant Revenue Growth Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory per-merchant state (fine for a hackathon demo)
AUDIT_LOGS = {}      # merchant_id -> list of log entries
DECISIONS = {}       # decision_id -> decision dict (includes merchant_id)
_next_decision_id = 1


def get_audit_log(merchant_id: str):
    return AUDIT_LOGS.setdefault(merchant_id, [])


def log_event(merchant_id: str, event_type: str, payload: dict):
    get_audit_log(merchant_id).append({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": event_type,
        "payload": payload,
    })


@app.get("/api/merchants")
def merchants():
    """List available merchants - proves this is a multi-merchant engine, not a one-off script."""
    ids = agent.list_merchants()
    out = []
    for mid in ids:
        data = agent.load_data(mid)
        out.append({"id": mid, "name": data["merchant"]["name"], "category": data["merchant"]["category"]})
    return {"merchants": out}


@app.get("/api/dashboard")
def dashboard(merchant_id: str = "stridesport"):
    data = agent.load_data(merchant_id)
    underperformers = agent.find_underperforming_products(data)
    total_orders = len(data["orders"])
    products = agent.product_lookup(data)
    total_revenue_estimate = sum(products[i]["price"] for o in data["orders"] for i in o["items"])

    return {
        "merchant": data["merchant"],
        "products": data["products"],
        "total_orders": total_orders,
        "total_revenue_estimate": total_revenue_estimate,
        "underperforming_products": underperformers,
    }


@app.get("/api/opportunities")
def opportunities(merchant_id: str = "stridesport"):
    data = agent.load_data(merchant_id)
    opps = agent.analyze_co_purchases(data)
    return {"opportunities": opps[:5]}


class DecisionRequest(BaseModel):
    merchant_id: str = "stridesport"
    product_a: str
    product_b: str
    discount_pct: int = 15


@app.post("/api/decide")
def decide(req: DecisionRequest):
    """Step 2 (Decide) + Step 2b (check critical rules)."""
    global _next_decision_id
    data = agent.load_data(req.merchant_id)
    opps = agent.analyze_co_purchases(data)
    match = next(
        (o for o in opps if o["product_a"] == req.product_a and o["product_b"] == req.product_b),
        None,
    )
    if match is None:
        return {"error": "Opportunity not found for this product pair."}

    decision = agent.build_decision(data, match, discount_pct=req.discount_pct)
    rule_results = agent.evaluate_critical_rules(data, decision)
    all_passed = all(r["passed"] for r in rule_results)

    decision_id = f"D{_next_decision_id:04d}"
    _next_decision_id += 1
    decision["decision_id"] = decision_id
    decision["merchant_id"] = req.merchant_id
    decision["rule_results"] = rule_results
    decision["needs_approval"] = not all_passed
    decision["status"] = "auto_approved" if all_passed else "awaiting_approval"
    DECISIONS[decision_id] = decision

    log_event(req.merchant_id, "opportunity_detected", {"opportunity": match})
    log_event(req.merchant_id, "decision_made", {"decision_id": decision_id, "rule_results": rule_results})

    return decision


@app.post("/api/execute/{decision_id}")
def execute(decision_id: str, force_fail: bool = False):
    """Step 3 (Act): execute via Razorpay test mode, ONLY if all critical rules passed or approval was given."""
    decision = DECISIONS.get(decision_id)
    if decision is None:
        return {"error": "Decision not found."}
    merchant_id = decision["merchant_id"]

    if decision["needs_approval"] and not decision.get("approved", False):
        failed_rules = [r for r in decision["rule_results"] if not r["passed"]]
        log_event(merchant_id, "action_blocked", {
            "decision_id": decision_id,
            "failed_rules": failed_rules,
        })
        return {
            "status": "blocked",
            "message": "Blocked by critical rule(s) - approve manually to proceed.",
            "failed_rules": failed_rules,
            "decision_id": decision_id,
        }

    if force_fail:
        log_event(merchant_id, "payment_failed", {"decision_id": decision_id, "reason": "Simulated card decline for demo purposes."})
        return {
            "status": "failed",
            "message": "Payment failed (simulated decline). No order was created, no success was recorded.",
            "decision_id": decision_id,
        }

    order = razorpay_client.create_order(
        amount_rupees=decision["bundle_price_discounted"],
        receipt=f"bundle_{decision_id}",
        notes={
            "product_a": decision["product_a"]["name"],
            "product_b": decision["product_b"]["name"],
            "discount_pct": decision["discount_pct"],
        },
    )

    if order.get("status") == "failed" or order.get("id") is None:
        log_event(merchant_id, "payment_failed", {"decision_id": decision_id, "error": order.get("error")})
        return {"status": "failed", "message": "Razorpay order creation failed.", "razorpay_response": order}

    log_event(merchant_id, "action_executed", {"decision_id": decision_id, "razorpay_order": order})
    return {"status": "executed", "razorpay_order": order, "decision_id": decision_id}


@app.post("/api/approve/{decision_id}")
def approve(decision_id: str):
    decision = DECISIONS.get(decision_id)
    if decision is None:
        return {"error": "Decision not found."}
    decision["approved"] = True
    decision["status"] = "manually_approved"
    log_event(decision["merchant_id"], "decision_approved", {"decision_id": decision_id})
    return {"status": "approved", "decision_id": decision_id}


@app.get("/api/audit-log")
def audit_log(merchant_id: str = "stridesport"):
    return {"log": get_audit_log(merchant_id)}


@app.get("/api/nightly-summary")
def nightly_summary(merchant_id: str = "stridesport"):
    """Step 4 (Measure/Learn): plain-language end-of-day summary + next-action prediction."""
    data = agent.load_data(merchant_id)
    return agent.generate_nightly_summary(data, get_audit_log(merchant_id))


# Serve the frontend
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
