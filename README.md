# StegaDoc
PoC app steganography tool developed for the War Studies University in Warsaw (Akademia Sztuki Wojennej). Hides AES-256-GCM-encrypted PDF documents inside PNG carrier images using Least-Significant-Bit (LSB) steganography, providing a two-layer protection model: the content of the document is encrypted, and the existence of the document is concealed.

---

## Stack

Python 3.12 · Flask 3.x · Vanilla HTML/CSS/JS

### Plans, hopes and dreams:

Infrastructure | Terraform

Containerization | Docker · Azure Container Apps

---

## Use Cases

**UC-01 — Securing a sensitive document for transfer**
A user selects a PDF (e.g. a financial report or internal memo) and a carrier image. After entering a password, the app produces a PNG file that is visually indistinguishable from the original image but carries the encrypted PDF in its pixel LSBs. The output file can be shared over any channel without revealing that a document is present.

**UC-02 — Recovering a hidden document**
A recipient who has the stego PNG and the correct password uploads the image to the extract panel. The app extracts the LSB payload, decrypts it with AES-256-GCM, verifies the embedded SHA-256 digest, and returns the original PDF as a download.

**UC-03 — Integrity verification**
On every extraction the app independently re-computes the SHA-256 hash of the decrypted payload and compares it against the digest that was encrypted alongside the document at embed time. Any corruption or tampering causes the operation to fail with an explicit error before the file is returned to the user.

---

## HTTP Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the single-page web UI |
| `POST` | `/embed` | Accepts a PDF, a carrier image, and a password; returns a stego PNG |
| `POST` | `/extract` | Accepts a stego PNG and a password; returns the recovered PDF |
| `GET` | `/health` | Liveness / readiness probe for possible containerization |

### POST `/embed`

**Request** — `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `pdf` | file | PDF document to hide |
| `carrier` | file | Carrier image (PNG / JPG / BMP) |
| `password` | string | Passphrase (min. 8 characters) |
| `password2` | string | Passphrase confirmation |

**Response**
- `200 image/png` — stego image with embedded payload
- `400 application/json` — `{"error": "..."}` on validation failure
- `500 application/json` — `{"error": "..."}` on processing failure

### POST `/extract`

**Request** — `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `stego` | file | Stego PNG image |
| `password` | string | Passphrase used during embed |

**Response**
- `200 application/pdf` — recovered PDF document
- `400 application/json` — `{"error": "..."}` on wrong password, tampered data, or missing input
- `500 application/json` — `{"error": "..."}` on processing failure


## Running Locally

```bash
pip install -r requirements.txt
python main.py
```
