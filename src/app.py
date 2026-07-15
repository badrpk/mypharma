from __future__ import annotations
"""MyPharma — pharmacy catalog + refill + checkout.
Parity target: DVAGO / online pharmacy platforms.
"""
import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent))

from http_util import JsonAPI, serve, uid, iso

DRUGS = [
    {"id": "d1", "name": "Paracetamol 500mg", "generic": "acetaminophen", "category": "otc",
     "rx_required": False, "price_pkr": 40, "stock": 500, "form": "tablet", "pack_size": 20},
    {"id": "d2", "name": "Amoxicillin 250mg", "generic": "amoxicillin", "category": "antibiotic",
     "rx_required": True, "price_pkr": 180, "stock": 120, "form": "capsule", "pack_size": 10},
    {"id": "d3", "name": "Vitamin D3", "generic": "cholecalciferol", "category": "supplements",
     "rx_required": False, "price_pkr": 320, "stock": 80, "form": "softgel", "pack_size": 30},
    {"id": "d4", "name": "Omeprazole 20mg", "generic": "omeprazole", "category": "gi",
     "rx_required": False, "price_pkr": 210, "stock": 200, "form": "capsule", "pack_size": 14},
    {"id": "d5", "name": "Metformin 500mg", "generic": "metformin", "category": "chronic",
     "rx_required": True, "price_pkr": 95, "stock": 300, "form": "tablet", "pack_size": 30},
    {"id": "d6", "name": "ORS Sachet", "generic": "oral rehydration salts", "category": "otc",
     "rx_required": False, "price_pkr": 35, "stock": 1000, "form": "sachet", "pack_size": 1},
]
SLOTS = ["10:00-12:00", "12:00-15:00", "15:00-18:00", "18:00-21:00"]
CARTS: dict[str, list] = {}
REFILLS: list[dict] = []
ORDERS: dict[str, dict] = {}
RX_UPLOADS: dict[str, dict] = {}

class H(JsonAPI):
    def do_GET(self):
        path, q = self.parse()
        if path in ("/", "/health"):
            return self._send(200, {"ok": True, "service": "mypharma", "version": "2.0.0",
                                    "parity_target": "DVAGO / online pharmacy",
                                    "routes": ["/drugs", "/categories", "/cart", "/refills",
                                               "/orders", "/slots", "/alternatives", "/capabilities"]})
        if path == "/capabilities":
            return self._send(200, {"ok": True, "competitor": "DVAGO", "features": [
                "drug_search", "categories", "stock", "rx_gate", "rx_upload", "cart",
                "delivery_slots", "checkout", "order_tracking", "generic_alternatives", "refills"
            ]})
        if path == "/categories":
            cats = sorted({d["category"] for d in DRUGS})
            return self._send(200, {"ok": True, "categories": cats})
        if path == "/drugs":
            term = ((q.get("q") or [""])[0] or "").lower()
            cat = (q.get("category") or [None])[0]
            rows = []
            for d in DRUGS:
                if term and term not in d["name"].lower() and term not in d["generic"].lower():
                    continue
                if cat and d["category"] != cat:
                    continue
                rows.append(d)
            return self._send(200, {"ok": True, "count": len(rows), "drugs": rows})
        if path == "/alternatives":
            drug_id = (q.get("drug_id") or [""])[0]
            base = next((d for d in DRUGS if d["id"] == drug_id), None)
            if not base:
                return self._send(404, {"ok": False, "error": "unknown_drug"})
            alts = [d for d in DRUGS if d["generic"] == base["generic"] and d["id"] != drug_id]
            # also same category cheaper
            cheaper = [d for d in DRUGS if d["category"] == base["category"] and d["price_pkr"] < base["price_pkr"] and d["id"] != drug_id]
            return self._send(200, {"ok": True, "drug_id": drug_id, "same_generic": alts, "cheaper_same_category": cheaper})
        if path == "/slots":
            return self._send(200, {"ok": True, "delivery_slots": SLOTS, "currency": "PKR", "delivery_fee_pkr": 99})
        if path == "/cart":
            user = (q.get("user") or ["guest"])[0]
            return self._send(200, {"ok": True, "user": user, "items": CARTS.get(user, [])})
        if path == "/refills":
            return self._send(200, {"ok": True, "refills": REFILLS})
        if path == "/orders":
            user = (q.get("user") or [None])[0]
            rows = list(ORDERS.values())
            if user:
                rows = [o for o in rows if o["user"] == user]
            return self._send(200, {"ok": True, "orders": rows})
        if path.startswith("/orders/"):
            oid = path.split("/")[2]
            o = ORDERS.get(oid)
            return self._send(200 if o else 404, {"ok": bool(o), "order": o} if o else {"ok": False, "error": "not_found"})
        self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        path, _ = self.parse()
        body = self._read_json()
        if body.get("_error"):
            return self._send(400, {"ok": False, "error": "invalid_json"})
        if path == "/cart/add":
            user = str(body.get("user") or "guest")
            drug = next((d for d in DRUGS if d["id"] == body.get("drug_id")), None)
            if not drug:
                return self._send(400, {"ok": False, "error": "unknown_drug"})
            if drug["stock"] < int(body.get("qty") or 1):
                return self._send(400, {"ok": False, "error": "out_of_stock", "stock": drug["stock"]})
            CARTS.setdefault(user, []).append({
                "drug_id": drug["id"], "name": drug["name"], "qty": int(body.get("qty") or 1),
                "unit_price": drug["price_pkr"], "rx_required": drug["rx_required"],
            })
            return self._send(200, {"ok": True, "cart": CARTS[user]})
        if path == "/rx/upload":
            rid = uid("rx")
            RX_UPLOADS[rid] = {
                "id": rid, "patient": body.get("patient") or "anonymous",
                "filename": body.get("filename") or "rx.jpg",
                "content_b64_len": len(body.get("content_b64") or ""),
                "status": "pending_review", "at": iso(),
            }
            return self._send(201, {"ok": True, "rx": RX_UPLOADS[rid]})
        if path == "/refills":
            drug = next((d for d in DRUGS if d["id"] == body.get("drug_id")), None)
            if not drug:
                return self._send(400, {"ok": False, "error": "unknown_drug_id"})
            if drug["rx_required"] and not body.get("rx_code") and not body.get("rx_id"):
                return self._send(400, {"ok": False, "error": "rx_code_or_rx_id_required"})
            rec = {"id": uid("rf"), "drug": drug, "patient": body.get("patient") or "anonymous",
                   "status": "queued", "at": iso()}
            REFILLS.append(rec)
            return self._send(201, {"ok": True, "refill": rec})
        if path in ("/checkout", "/order"):
            user = str(body.get("user") or "guest")
            items = CARTS.get(user, [])
            if not items:
                return self._send(400, {"ok": False, "error": "cart_empty"})
            needs_rx = any(i["rx_required"] for i in items)
            if needs_rx and not body.get("rx_code") and not body.get("rx_id"):
                return self._send(400, {"ok": False, "error": "prescription_required_for_cart"})
            slot = body.get("slot") or SLOTS[0]
            if slot not in SLOTS:
                return self._send(400, {"ok": False, "error": "invalid_slot", "slots": SLOTS})
            sub = sum(i["unit_price"] * i["qty"] for i in items)
            fee = 99
            oid = uid("ph")
            order = {
                "id": oid, "user": user, "items": items, "subtotal_pkr": sub,
                "delivery_fee_pkr": fee, "total_pkr": sub + fee,
                "slot": slot, "address": body.get("address") or "",
                "payment_method": body.get("payment_method") or "cod",
                "status": "placed", "timeline": [{"status": "placed", "at": iso()}],
                "created_at": iso(),
            }
            ORDERS[oid] = order
            CARTS[user] = []
            return self._send(201, {"ok": True, "order": order})
        if path.startswith("/orders/") and path.endswith("/advance"):
            oid = path.split("/")[2]
            o = ORDERS.get(oid)
            if not o:
                return self._send(404, {"ok": False})
            seq = ["placed", "pharmacist_review", "packing", "out_for_delivery", "delivered"]
            i = seq.index(o["status"]) if o["status"] in seq else 0
            if i < len(seq) - 1:
                o["status"] = seq[i + 1]
                o["timeline"].append({"status": o["status"], "at": iso()})
            return self._send(200, {"ok": True, "order": o})
        self._send(404, {"ok": False, "error": "not_found"})

def main():
    serve(H, port=int(__import__("os").environ.get("PORT", "8765")), name="MyPharma v2 (DVAGO parity)")

if __name__ == "__main__":
    main()
