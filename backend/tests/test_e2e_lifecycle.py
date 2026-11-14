"""End-to-end order lifecycle through the real HTTP API (Req 40, 27.1, 45.1)."""
CARD = {"card_holder": "Asha Rao", "card_number": "4242424242424242", "expiry": "12/99", "cvv": "123"}
PW = "Passw0rd!x"


def _register(client, name, role, email, **extra):
    body = {"name": name, "email": email, "password": PW, "phone": "9000011111", "role": role, **extra}
    r = client.post("/auth/register", json=body)
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_full_lifecycle(client):
    cust = _register(client, "Asha Rao", "CUSTOMER", "e2e-cust@example.com", address="Block C")
    owner = _register(
        client, "Olga Owner", "RESTAURANT_OWNER", "e2e-owner@example.com",
        restaurant={"name": "E2E Kitchen", "description": "Tasty", "cuisine": "Indian",
                    "address": "Campus Road 1"},
    )
    partner = _register(client, "Pat Partner", "DELIVERY_PARTNER", "e2e-partner@example.com")

    r = client.post("/owner/menu-items", json={"name": "E2E Biryani", "price": "12.50"}, headers=owner)
    assert r.status_code == 201, r.text
    dish_id = r.json()["id"]

    dishes = client.get("/dishes", headers=cust).json()
    assert any(d["id"] == dish_id for d in dishes["items"])
    restaurant_id = next(d for d in dishes["items"] if d["id"] == dish_id)["restaurant_id"]

    r = client.post("/orders", headers=cust, json={
        "items": [{"menu_item_id": dish_id, "quantity": 2}],
        "delivery_address": "Block C, Room 7", "delivery_phone": "9000022222", "payment": CARD})
    assert r.status_code == 201, r.text
    order = r.json()
    oid = order["id"]
    assert order["payment_status"] == "mock_paid"
    assert order["total_amount"] == "25.00"

    for st in ("ACCEPTED", "PREPARING", "READY"):
        r = client.patch(f"/owner/orders/{oid}/status", json={"status": st}, headers=owner)
        assert r.status_code == 200 and r.json()["status"] == st, r.text

    parts = client.get("/owner/delivery-partners", headers=owner).json()["items"]
    pid = next(p for p in parts if p["name"] == "Pat Partner")["id"]
    r = client.post(f"/owner/orders/{oid}/assign", json={"delivery_partner_id": pid}, headers=owner)
    assert r.status_code == 200 and r.json()["status"] == "ASSIGNED", r.text

    for st in ("OUT_FOR_DELIVERY", "DELIVERED"):
        r = client.patch(f"/partner/orders/{oid}/status", json={"status": st}, headers=partner)
        assert r.status_code == 200 and r.json()["status"] == st, r.text
    assert r.json()["delivered_at"] is not None

    r = client.post(f"/orders/{oid}/review", json={"rating": 5, "comment": "Great"}, headers=cust)
    assert r.status_code == 201, r.text
    r = client.post(f"/orders/{oid}/return", json={"reason": "Food was cold"}, headers=cust)
    assert r.status_code in (200, 201), r.text

    returns = client.get("/owner/returns", headers=owner).json()
    assert any(x["order_id"] == oid for x in returns["items"])
    r = client.post(f"/owner/returns/{oid}/approve", headers=owner)
    assert r.status_code == 200, r.text

    d = client.get(f"/orders/{oid}", headers=cust).json()
    assert d["status"] == "REFUNDED"
    assert d["payment_status"] == "refunded"
    assert d["return_status"] == "approved"
    types = sorted(e["entry_type"] for e in d["ledger_entries"])
    assert types == ["PAYMENT", "REFUND"]

    stats = client.get("/owner/stats", headers=owner).json()
    assert stats["net_revenue"] == "0.00"
    assert stats["status_counts"]["REFUNDED"] == 1

    hist = client.get("/partner/history", headers=partner).json()
    assert [x["id"] for x in hist["items"]] == [oid]

    reviews = client.get(f"/restaurants/{restaurant_id}/reviews").json()
    assert reviews["total"] == 1 and reviews["items"][0]["rating"] == 5

    assert client.get("/owner/reminders", headers=owner).status_code == 200
