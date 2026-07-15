# MyPharma — competitive parity

**Target:** DVAGO / online pharmacies

| Capability | Endpoint |
|------------|----------|
| Search + categories | `GET /drugs?q=&category=` |
| Stock-aware cart | `POST /cart/add` |
| RX gate + upload | `POST /rx/upload`, checkout requires RX for Rx drugs |
| Delivery slots | `GET /slots` |
| Checkout | `POST /checkout` |
| Tracking | `POST /orders/{id}/advance`, `GET /orders/{id}` |
| Generic alternatives | `GET /alternatives?drug_id=` |
| Refills | `POST /refills` |
