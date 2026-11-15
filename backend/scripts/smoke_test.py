"""Production smoke test for CampusBite.

Usage: python scripts/smoke_test.py https://campusbite-api-three.vercel.app
Password is read from SMOKE_PASSWORD (default: the seed demo password).
"""
from __future__ import annotations

import os
import sys

import httpx

PASSWORD = os.environ.get("SMOKE_PASSWORD", "Password123!")
CUSTOMER = "alice@campusbite.example.com"
OWNERS = [
    "owner.curry@campusbite.example.com",
    "owner.burgers@campusbite.example.com",
    "owner.noodles@campusbite.example.com",
]
PARTNER = "dave@campusbite.example.com"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")
    return ok


class Session:
    def __init__(self, base: str):
        self.c = httpx.Client(base_url=base, timeout=60)
        self.h: dict[str, str] = {}

    def login(self, email: str) -> bool:
        r = self.c.post("/auth/login", json={"email": email, "password": PASSWORD})
        if r.status_code == 200:
            self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return check(f"login {email.split('@')[0]}", r.status_code == 200, f"-> {r.status_code}")

    def req(self, method: str, path: str, **kw) -> httpx.Response:
        return self.c.request(method, path, headers=self.h, **kw)


def items_of(body):
    return body["items"] if isinstance(body, dict) and "items" in body else body


def main(base: str) -> int:
    cust = Session(base)
    if not cust.login(CUSTOMER):
        return 1
    r = cust.req("GET", "/restaurants")
    rests = items_of(r.json()) if r.status_code == 200 else []
    check("list restaurants", r.status_code == 200 and len(rests) > 0, f"-> {r.status_code}, {len(rests)}")
    if not rests:
        return 1

    menu_item, rid = None, None
    for rest in rests:
        m = cust.req("GET", f"/restaurants/{rest['id']}/menu")
        if m.status_code != 200:
            continue
        body = m.json()
        its = items_of(body) if not isinstance(body, dict) or "items" in body else body.get("menu", [])
        av = [i for i in its if i.get("is_available")]
        if av:
            menu_item, rid = av[0], rest["id"]
            break
    if not check("find available menu item", menu_item is not None):
        return 1

    r = cust.req("POST", "/orders", json={
        "items": [{"menu_item_id": menu_item["id"], "quantity": 1}],
        "delivery_address": "Hostel 4, Room 210, Campus",
        "delivery_phone": "9000000001",
        "payment": {"card_holder": "Alice Customer", "card_number": "4242424242424242",
                    "expiry": "12/30", "cvv": "123"},
    })
    ok = r.status_code == 201 and r.json().get("status") == "PLACED"
    check("place order", ok, f"-> {r.status_code}")
    if not ok:
        return 1
    oid = r.json()["id"]

    # Owner flow: find the owner who owns the restaurant.
    owner = None
    for email in OWNERS:
        s = Session(base)
        if not s.login(email):
            continue
        r = s.req("PATCH", f"/owner/orders/{oid}/status", json={"status": "ACCEPTED"})
        if r.status_code == 200:
            owner = s
            check("owner accepts", True, f"-> 200 ({email.split('@')[0]})")
            break
    if not owner:
        check("owner accepts", False, "no owner could accept")
        return 1
    for st in ("PREPARING", "READY"):
        r = owner.req("PATCH", f"/owner/orders/{oid}/status", json={"status": st})
        check(f"owner -> {st}", r.status_code == 200 and r.json().get("status") == st, f"-> {r.status_code}")
    r = owner.req("GET", "/owner/delivery-partners")
    partners = items_of(r.json()) if r.status_code == 200 else []
    check("list delivery partners", r.status_code == 200 and len(partners) > 0, f"-> {r.status_code}")

    part = Session(base)
    part.login(PARTNER)
    me = part.req("GET", "/auth/me")
    pid = me.json()["id"] if me.status_code == 200 else None
    r = owner.req("POST", f"/owner/orders/{oid}/assign", json={"delivery_partner_id": pid})
    check("owner assigns partner", r.status_code == 200 and r.json().get("status") == "ASSIGNED", f"-> {r.status_code}")
    r = owner.req("GET", "/owner/stats")
    check("owner stats", r.status_code == 200, f"-> {r.status_code}")
    r = owner.req("GET", "/owner/reminders")
    check("owner reminders", r.status_code == 200, f"-> {r.status_code}")

    # Partner flow
    r = part.req("GET", "/partner/orders")
    check("partner lists orders", r.status_code == 200, f"-> {r.status_code}")
    for st in ("OUT_FOR_DELIVERY", "DELIVERED"):
        r = part.req("PATCH", f"/partner/orders/{oid}/status", json={"status": st})
        check(f"partner -> {st}", r.status_code == 200 and r.json().get("status") == st, f"-> {r.status_code}")

    # Customer post-delivery
    r = cust.req("POST", f"/orders/{oid}/review", json={"rating": 5, "comment": "Smoke test"})
    check("customer review", r.status_code == 201, f"-> {r.status_code}")
    r = cust.req("POST", f"/orders/{oid}/return", json={"reason": "Smoke test return"})
    check("customer return request", r.status_code in (200, 201), f"-> {r.status_code}")
    r = cust.req("POST", "/ai/insights", json={"question": "What are the most popular dishes?"})
    # Expected 503 while OPENAI_API_KEY is unset (documented).
    check("AI question (200 or documented 503)", r.status_code in (200, 503), f"-> {r.status_code}")

    r = owner.req("POST", f"/owner/returns/{oid}/approve")
    check("owner approves refund", r.status_code == 200, f"-> {r.status_code}")
    r = cust.req("GET", f"/orders/{oid}")
    d = r.json() if r.status_code == 200 else {}
    check("final state REFUNDED/refunded/approved",
          d.get("status") == "REFUNDED" and d.get("payment_status") == "refunded"
          and d.get("return_status") == "approved",
          f"-> {d.get('status')}/{d.get('payment_status')}/{d.get('return_status')}")

    failed = [n for n, ok, _ in results if not ok]
    print(f"\nSummary: {len(results) - len(failed)}/{len(results)} passed")
    for n in failed:
        print(f"  FAILED: {n}")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1].rstrip("/")))
