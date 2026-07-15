# MyPharma 💊

**Pharmacy catalog + prescription refill** service for Pakistan.

Healthcare vertical — not general e-commerce (Rangoons) and not food (Khaana / Laiba Badar).

## Run

```bash
git clone https://github.com/badrpk/mypharma.git
cd mypharma
python3 src/app.py
```

## API

- `GET /drugs?q=` — search medicines  
- `GET /refills` — list refill requests  
- `POST /refills` — `{drug_id, patient, rx_code?}`  

## Contribute

[CONTRIBUTING.md](CONTRIBUTING.md) · [COMMUNITY.md](COMMUNITY.md)
