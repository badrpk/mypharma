from __future__ import annotations
"""MyPharma v3 — DVAGO parity + multi-rail payments + undercut."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from http_util import JsonAPI, serve, uid, iso
import payments as pay
import auth as authmod

DRUGS = [
    {"id": "d1", "name": "Paracetamol 500mg", "generic": "acetaminophen", "category": "otc",
     "rx_required": False, "price_pkr": 28, "competitor_price_pkr": 45, "stock": 500, "form": "tablet", "pack_size": 20},
    {"id": "d2", "name": "Amoxicillin 250mg", "generic": "amoxicillin", "category": "antibiotic",
     "rx_required": True, "price_pkr": 129, "competitor_price_pkr": 180, "stock": 120, "form": "capsule", "pack_size": 10},
    {"id": "d3", "name": "Vitamin D3", "generic": "cholecalciferol", "category": "supplements",
     "rx_required": False, "price_pkr": 199, "competitor_price_pkr": 320, "stock": 80, "form": "softgel", "pack_size": 30},
    {"id": "d4", "name": "Omeprazole 20mg", "generic": "omeprazole", "category": "gi",
     "rx_required": False, "price_pkr": 149, "competitor_price_pkr": 210, "stock": 200, "form": "capsule", "pack_size": 14},
    {"id": "d5", "name": "Metformin 500mg", "generic": "metformin", "category": "chronic",
     "rx_required": True, "price_pkr": 65, "competitor_price_pkr": 95, "stock": 300, "form": "tablet", "pack_size": 30},
    {"id": "d6", "name": "ORS Sachet", "generic": "oral rehydration salts", "category": "otc",
     "rx_required": False, "price_pkr": 22, "competitor_price_pkr": 35, "stock": 1000, "form": "sachet", "pack_size": 1},
]
SLOTS = ["10:00-12:00", "12:00-15:00", "15:00-18:00", "18:00-21:00"]
CARTS, REFILLS, ORDERS, RX_UPLOADS, SUBS = {}, [], {}, {}, {}
LABS = [{"id": "lab1", "name": "CBC", "price_pkr": 499, "competitor_price_pkr": 900},
        {"id": "lab2", "name": "Blood Sugar Fasting", "price_pkr": 199, "competitor_price_pkr": 400}]

class H(JsonAPI):
    def do_GET(self):
        path, q = self.parse()
        if path.startswith("/auth"):
            # headers as dict
            hdrs = {k: v for k, v in self.headers.items()}
            code, body = authmod.handle_auth_request("GET", path, {}, hdrs, product="mypharma")
            return self._send(code, body)

        if path in ("/", "/health"):
            return self._send(200, {"ok": True, "service": "mypharma", "version": "3.0.0", "parity_target": "DVAGO",
                "gaps_closed": ["lab_tests", "subscription_refills", "teleconsult_stub", "insurance_claim_stub", "multi_rail_payments", "undercut"]})
        if path == "/capabilities":
            return self._send(200, {"ok": True, "competitor": "DVAGO", "features": [
                "drug_search", "stock", "rx_gate", "rx_upload", "cart", "slots", "checkout", "tracking",
                "generics", "refills", "lab_tests", "subscriptions", "teleconsult", "stripe", "signup", "login", "otp", "oauth_google", "oauth_facebook", "jazzcash"]})
        if path == "/pricing": return self._send(200, {"ok": True, **pay.pricing_for("mypharma")})
        if path == "/payments/rails": return self._send(200, {"ok": True, "rails": pay.list_rails()})
        if path == "/gap-analysis":
            return self._send(200, {"ok": True, "competitor": "DVAGO", "added_in_v3": [
                "lab tests", "auto-refill subscription", "teleconsult booking stub", "insurance claim stub",
                "stripe + PK wallets + crypto", "menu/drug prices undercut"]})
        if path == "/categories":
            return self._send(200, {"ok": True, "categories": sorted({d["category"] for d in DRUGS})})
        if path == "/drugs":
            term = ((q.get("q") or [""])[0] or "").lower(); cat = (q.get("category") or [None])[0]
            rows = [d for d in DRUGS if (not term or term in d["name"].lower() or term in d["generic"].lower()) and (not cat or d["category"]==cat)]
            return self._send(200, {"ok": True, "drugs": rows})
        if path == "/labs": return self._send(200, {"ok": True, "labs": LABS})
        if path == "/alternatives":
            base = next((d for d in DRUGS if d["id"] == (q.get("drug_id") or [""])[0]), None)
            if not base: return self._send(404, {"ok": False})
            return self._send(200, {"ok": True, "same_generic": [d for d in DRUGS if d["generic"]==base["generic"] and d["id"]!=base["id"]],
                                    "cheaper": [d for d in DRUGS if d["price_pkr"] < base["price_pkr"]]})
        if path == "/slots": return self._send(200, {"ok": True, "delivery_slots": SLOTS, "delivery_fee_pkr": 49})
        if path == "/cart":
            user = (q.get("user") or ["guest"])[0]
            return self._send(200, {"ok": True, "items": CARTS.get(user, [])})
        if path == "/refills": return self._send(200, {"ok": True, "refills": REFILLS})
        if path == "/subscriptions":
            user = (q.get("user") or [None])[0]
            rows = list(SUBS.values())
            if user: rows = [s for s in rows if s["user"]==user]
            return self._send(200, {"ok": True, "subscriptions": rows})
        if path == "/orders":
            user = (q.get("user") or [None])[0]
            rows = list(ORDERS.values())
            if user: rows = [o for o in rows if o["user"]==user]
            return self._send(200, {"ok": True, "orders": rows})
        if path.startswith("/orders/"):
            o = ORDERS.get(path.split("/")[2])
            return self._send(200 if o else 404, {"ok": bool(o), "order": o})
        if path.startswith("/payments/invoices/"):
            inv = pay.get_invoice(path.split("/")[-1])
            return self._send(200 if inv else 404, {"ok": bool(inv), "invoice": inv})
        self._send(404, {"ok": False})

    def do_POST(self):
        _path_early = (self.path.split("?")[0].rstrip("/") or "/")
        if _path_early.startswith("/auth"):
            hdrs = {k: v for k, v in self.headers.items()}
            body = self._read_json() if hasattr(self, "_read_json") else self._read()
            code, resp = authmod.handle_auth_request("POST", _path_early, body if isinstance(body, dict) else {}, hdrs, product="mypharma")
            return self._send(code, resp)
        path, _ = self.parse()
        body = self._read_json()
        if path == "/cart/add":
            user = str(body.get("user") or "guest")
            drug = next((d for d in DRUGS if d["id"]==body.get("drug_id")), None)
            if not drug: return self._send(400, {"ok": False, "error": "unknown_drug"})
            if drug["stock"] < int(body.get("qty") or 1): return self._send(400, {"ok": False, "error": "out_of_stock"})
            CARTS.setdefault(user, []).append({"drug_id": drug["id"], "name": drug["name"], "qty": int(body.get("qty") or 1),
                "unit_price": drug["price_pkr"], "rx_required": drug["rx_required"]})
            return self._send(200, {"ok": True, "cart": CARTS[user]})
        if path == "/rx/upload":
            rid = uid("rx")
            RX_UPLOADS[rid] = {"id": rid, "patient": body.get("patient") or "anonymous", "filename": body.get("filename") or "rx.jpg",
                               "status": "pending_review", "at": iso()}
            return self._send(201, {"ok": True, "rx": RX_UPLOADS[rid]})
        if path == "/teleconsult":
            return self._send(201, {"ok": True, "booking": {"id": uid("tc"), "patient": body.get("patient"),
                "slot": body.get("slot") or SLOTS[0], "fee_pkr": 299, "competitor_fee_pkr": 800, "status": "scheduled", "at": iso()}})
        if path == "/insurance/claim":
            return self._send(201, {"ok": True, "claim": {"id": uid("cl"), "order_id": body.get("order_id"),
                "provider": body.get("provider") or "EFU", "status": "submitted", "at": iso()}})
        if path == "/subscriptions":
            user = str(body.get("user") or "guest")
            drug = next((d for d in DRUGS if d["id"]==body.get("drug_id")), None)
            if not drug: return self._send(400, {"ok": False, "error": "unknown_drug"})
            sid = uid("sub")
            inv = pay.create_invoice("mypharma", 149, "PKR", method=body.get("payment_method") or "stripe",
                                     customer=user, sku="subscription", description="Chronic refill plan")
            SUBS[sid] = {"id": sid, "user": user, "drug_id": drug["id"], "every_days": int(body.get("every_days") or 30),
                         "status": "active", "invoice": inv, "at": iso()}
            return self._send(201, {"ok": True, "subscription": SUBS[sid]})
        if path == "/labs/book":
            lab = next((l for l in LABS if l["id"]==body.get("lab_id")), None)
            if not lab: return self._send(400, {"ok": False})
            method = body.get("payment_method") or "cod"
            inv = pay.create_invoice("mypharma", lab["price_pkr"], "PKR", method=method, customer=body.get("user") or "guest",
                                     description=lab["name"])
            return self._send(201, {"ok": True, "booking": {"id": uid("lb"), "lab": lab, "invoice": inv, "status": "booked"}})
        if path in ("/checkout", "/order"):
            user = str(body.get("user") or "guest")
            items = CARTS.get(user, [])
            if not items: return self._send(400, {"ok": False, "error": "cart_empty"})
            if any(i["rx_required"] for i in items) and not body.get("rx_code") and not body.get("rx_id"):
                return self._send(400, {"ok": False, "error": "prescription_required_for_cart"})
            slot = body.get("slot") or SLOTS[0]
            if slot not in SLOTS: return self._send(400, {"ok": False, "error": "invalid_slot", "slots": SLOTS})
            sub = sum(i["unit_price"]*i["qty"] for i in items); fee = 49
            total = sub + fee
            method = (body.get("payment_method") or "cod").lower()
            inv = pay.create_invoice("mypharma", total, "PKR", method=method, customer=user, description="Pharmacy order")
            oid = uid("ph")
            order = {"id": oid, "user": user, "items": items, "subtotal_pkr": sub, "delivery_fee_pkr": fee,
                     "total_pkr": total, "slot": slot, "address": body.get("address") or "",
                     "payment_method": method, "invoice_id": inv["id"], "payment": inv,
                     "status": "placed", "timeline": [{"status": "placed", "at": iso()}], "created_at": iso(),
                     "savings_vs_dvago_style": {"delivery": 99-49, "note": "drug unit prices already undercut"}}
            ORDERS[oid] = order; CARTS[user] = []
            return self._send(201, {"ok": True, "order": order})
        if path == "/payments/create":
            inv = pay.create_invoice("mypharma", float(body.get("amount") or 0), body.get("currency") or "PKR",
                method=body.get("method") or "stripe", customer=body.get("customer") or "guest", sku=body.get("sku"),
                description=body.get("description") or "")
            return self._send(201, {"ok": True, "invoice": inv})
        if path.startswith("/payments/invoices/") and path.endswith("/mark-paid"):
            inv = pay.mark_paid(path.split("/")[3], body.get("proof") or "")
            return self._send(200 if inv else 404, {"ok": bool(inv), "invoice": inv})
        if path.startswith("/orders/") and path.endswith("/advance"):
            o = ORDERS.get(path.split("/")[2])
            if not o: return self._send(404, {"ok": False})
            seq = ["placed", "pharmacist_review", "packing", "out_for_delivery", "delivered"]
            i = seq.index(o["status"]) if o["status"] in seq else 0
            if i < len(seq)-1:
                o["status"] = seq[i+1]; o["timeline"].append({"status": o["status"], "at": iso()})
            return self._send(200, {"ok": True, "order": o})
        if path == "/refills":
            drug = next((d for d in DRUGS if d["id"]==body.get("drug_id")), None)
            if not drug: return self._send(400, {"ok": False})
            if drug["rx_required"] and not body.get("rx_code") and not body.get("rx_id"):
                return self._send(400, {"ok": False, "error": "rx_required"})
            rec = {"id": uid("rf"), "drug": drug, "patient": body.get("patient") or "anonymous", "status": "queued", "at": iso()}
            REFILLS.append(rec)
            return self._send(201, {"ok": True, "refill": rec})
        self._send(404, {"ok": False})

def main():
    serve(H, port=int(__import__("os").environ.get("PORT", "8765")), name="MyPharma v3")
if __name__ == "__main__":
    main()
