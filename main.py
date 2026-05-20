import io
import os
import numpy as np
from flask import Flask, jsonify, render_template, request, send_file
from PIL import Image
from encrypter import Encrypt
from file_operations import strip_pdf_metadata

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024 

_HEADER_BYTES = 4
_HEADER_BITS  = _HEADER_BYTES * 8

def _embed_lsb(image_array: np.ndarray, payload: bytes) -> np.ndarray:
    length_header = len(payload).to_bytes(_HEADER_BYTES, "big")
    all_bytes     = length_header + payload
    bits_needed   = len(all_bytes) * 8

    if bits_needed > image_array.size:
        raise ValueError(
            f"Payload is too large for this carrier image. "
            f"Need {bits_needed:,} bits; carrier has {image_array.size:,} pixels. "
            "Use a larger image or a smaller PDF."
        )

    binary_data = "".join(format(b, "08b") for b in all_bytes)
    image_array = image_array.copy()
    image_array.flags.writeable = True
    for i, bit in enumerate(binary_data):
        image_array.flat[i] = (image_array.flat[i] & 0xFE) | int(bit)
    return image_array


def _extract_lsb(image_array: np.ndarray) -> bytes:
    flat = image_array.flat
    n_px = image_array.size
    bits = "".join(str(flat[i] & 1) for i in range(min(n_px, _HEADER_BITS)))

    if len(bits) < _HEADER_BITS:
        raise ValueError("Image is too small to contain a valid header.")

    payload_len = int(bits[:_HEADER_BITS], 2)
    total_bits  = _HEADER_BITS + payload_len * 8

    if total_bits > n_px:
        raise ValueError(
            "No hidden data found in this image, or the image has been modified."
        )

    bits += "".join(str(flat[i] & 1) for i in range(_HEADER_BITS, total_bits))
    payload_bits = bits[_HEADER_BITS:]
    return bytes(int(payload_bits[i : i + 8], 2) for i in range(0, len(payload_bits), 8))


def _validate_password(pw: str, pw2: str | None = None) -> str | None:
    if not pw:
        return "Password must not be empty."
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    if pw2 is not None and pw != pw2:
        return "Passwords do not match."
    return None


def _error(message: str, status: int = 400):
    return jsonify({"error": message}), status


@app.route("/")
def index():
    return render_template('front.html')


@app.get("/health")
def health():
    """Liveness / readiness probe for Azure Container Apps."""
    return jsonify({"status": "ok"}), 200


@app.post("/embed")
def embed():
    pdf_file     = request.files.get("pdf")
    carrier_file = request.files.get("carrier")
    password     = request.form.get("password", "")
    pw_validation    = request.form.get("pw_validation", "")

    if not pdf_file:
        return _error("No PDF file provided.")
    if not carrier_file:
        return _error("No carrier image provided.")

    pw_err = _validate_password(password, pw_validation)
    if pw_err:
        return _error(pw_err)

    pdf_bytes = pdf_file.read()
    if not pdf_bytes.startswith(b"%PDF-"):
        return _error("Uploaded file does not appear to be a valid PDF.")

    carrier_bytes = carrier_file.read()

    try:
        clean_pdf      = strip_pdf_metadata(pdf_bytes)            
        encrypted_blob = Encrypt.encrypt_data(clean_pdf, password)
        carrier_image = Image.open(io.BytesIO(carrier_bytes)).convert("RGB")
        image_array   = np.array(carrier_image, dtype=np.uint8)
        stego_array   = _embed_lsb(image_array, encrypted_blob)   
        stego_buf = io.BytesIO()
        Image.fromarray(stego_array).save(stego_buf, format="PNG")
        stego_buf.seek(0)

    except ValueError as exc:
        return _error(str(exc))
    except Exception as exc:
        app.logger.exception("Embed error")
        return _error(f"Unexpected error: {exc}", 500)
    finally:
        password = password2 = ""

    resp = send_file(stego_buf, mimetype="image/png",
                     as_attachment=True, download_name="stego_image.png")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.post("/extract")
def extract():
    stego_file = request.files.get("stego")
    password   = request.form.get("password", "")

    if not stego_file:
        return _error("No stego image provided.")

    pw_err = _validate_password(password)
    if pw_err:
        return _error(pw_err)

    stego_bytes = stego_file.read()

    try:
        stego_image = Image.open(io.BytesIO(stego_bytes)).convert("RGB")
        image_array = np.array(stego_image, dtype=np.uint8)
        blob = _extract_lsb(image_array)
        pdf_bytes = Encrypt.decrypt_data(blob, password)            

    except ValueError as exc:
        return _error(str(exc))
    except Exception as exc:
        app.logger.exception("Extract error")
        return _error(f"Unexpected error: {exc}", 500)
    finally:
        password = ""

    resp = send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf", as_attachment=True, download_name="recovered.pdf")
    resp.headers["Cache-Control"] = "no-store"
    return resp


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
