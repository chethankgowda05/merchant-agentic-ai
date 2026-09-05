# StrideSport Revenue Growth Agent

An agentic AI that analyzes a merchant's sales data, finds a real cross-sell
opportunity, proposes a bounded action, gates it against merchant policy,
executes it via Razorpay (test mode), and logs everything.

**Agent loop:** Analyze → Decide → Act → Measure (via audit log) → Learn (future work)

## What it does

1. **Analyzes** order history to find products frequently bought together
   (e.g. 52% of shoe buyers also buy socks).
2. **Decides** on a bundle discount action, with a human-readable reason and
   an honest (not fabricated) expected-impact estimate.
3. **Checks policy**: if the discount exceeds the merchant's auto-approval
   limit (default 10%), the action is **blocked** until a human approves it.
   This is the safety demo.
4. **Acts**: on approval, creates a real Razorpay test-mode order for the
   discounted bundle.
5. **Logs** every step (opportunity → decision → block/approve → execution)
   to an audit trail.
6. Includes a **simulate failure** button to prove the system never fakes
   a success.

## Run it

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** in your browser. That's it — frontend is
served by the same backend.

## Razorpay test mode setup (optional but recommended before demo day)

By default the app runs in **mock mode** — it fakes Razorpay order
responses so you can build and demo without an account. To use real
Razorpay test-mode orders:

1. Sign up at https://dashboard.razorpay.com (free)
2. Go to **Account & Settings → API Keys → Test Mode → Generate Key**
3. Set environment variables before running the server:
   ```bash
   export RAZORPAY_KEY_ID="rzp_test_xxxxxxxxxxxx"
   export RAZORPAY_KEY_SECRET="xxxxxxxxxxxxxxxx"
   ```
4. Restart `uvicorn`. The `mock: true` flag will disappear from responses,
   confirming you're hitting the real Razorpay test API.
5. Test card for any checkout flow you build on top of this:
   `4111 1111 1111 1111`, any future expiry, any CVV.

## Project structure

```
backend/
  main.py            # FastAPI app, all API routes
  agent.py            # Opportunity detection + decision engine (the "brain")
  razorpay_client.py  # Razorpay test-mode Orders API wrapper (with mock fallback)
  data.json           # Fake merchant dataset (products, customers, orders)
frontend/
  index.html          # Single-page dashboard + demo UI
```

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/dashboard` | Merchant overview stats |
| GET | `/api/opportunities` | Detected cross-sell opportunities |
| POST | `/api/decide` | Build a bounded decision for an opportunity |
| POST | `/api/approve/{decision_id}` | Manually approve a decision that needs it |
| POST | `/api/execute/{decision_id}` | Execute via Razorpay (add `?force_fail=true` to demo failure) |
| GET | `/api/audit-log` | Full audit trail |

## What's deliberately NOT built (by design, not oversight)

To keep the one core agentic loop excellent rather than spreading thin:
- No merchant login/auth (single hardcoded merchant)
- No persistent database (in-memory audit log — fine for a demo)
- No "learning over time" (flagged honestly as future work in the pitch)
- No multiple opportunity types (one strong signal, well executed)

## Next steps (Day 2 / Day 3)

- [ ] Get real Razorpay test keys and confirm live (non-mock) order creation
- [ ] Add the architecture diagram
- [ ] Record the 3-4 min demo video
- [ ] Polish README with screenshots
