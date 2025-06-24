from __future__ import annotations
import os, time, base64, requests
from pathlib import Path
from typing import Dict, Tuple, Optional
from io import BytesIO

from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from PyPDF2 import PdfReader, PdfWriter

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.resolve()
DOWNLOADS = ROOT / "downloads"
DOWNLOADS.mkdir(exist_ok=True)

# Update for EC2 if needed
CHROMEDRIVER = "/Users/rishivijaywargiya/chromedriver-mac-arm64/chromedriver"

# ---------------------------------------------------------------------------
# Selenium wrapper
# ---------------------------------------------------------------------------
class AadhaarCrawler:
    def __init__(self, session_dir: Path):
        opts = Options()
        # opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-gpu")

        prefs = {"download.default_directory": str(session_dir)}
        opts.add_experimental_option("prefs", prefs)

        self.driver = webdriver.Chrome(service=Service(CHROMEDRIVER), options=opts)
        self.phase = "created"
        self.session_dir = session_dir
        self.pdf_path: Optional[Path] = None

    def open_portal(self):
        self.driver.get("https://myaadhaar.uidai.gov.in/genricDownloadAadhaar/en")
        WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.NAME, "uid")))
        self.phase = "awaiting_aadhaar"

    def fill_aadhaar(self, number: str):
        self.driver.find_element(By.NAME, "uid").send_keys(number)
        self.phase = "awaiting_captcha"

    def fill_captcha(self, captcha: str):
        self.driver.find_element(By.NAME, "captcha").send_keys(captcha)
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Send OTP')]"))
        ).click()
        self.phase = "awaiting_otp"

    def fill_otp(self, otp: str):
        WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.NAME, "otp"))).send_keys(otp)
        ActionChains(self.driver).move_by_offset(5, 5).click().perform()
        WebDriverWait(self.driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Verify') and contains(text(),'Download')]"))
        ).click()
        self.phase = "downloading"
        path = self._await_pdf()
        if not path:
            self.phase = "download_error"
            raise RuntimeError("PDF download timed out")
        self.phase = "downloaded"
        self.pdf_path = path
        return path

    def get_captcha_src(self) -> str:
        img = self.driver.find_element(By.CSS_SELECTOR, ".pvc-form__captcha-box img")
        src = img.get_attribute("src")
        if not src.startswith("data:image") and not src.startswith("data:application/image"):
            raise ValueError("Unexpected CAPTCHA src format")
        return src

    def _await_pdf(self, timeout: int = 60) -> Optional[Path]:
        start = time.time()
        while time.time() - start < timeout:
            for p in self.session_dir.iterdir():
                if p.name.startswith("EAadhaar_") and p.suffix == ".pdf" and not p.name.endswith(".crdownload"):
                    return p
            time.sleep(1)
        return None

    def unlock(self, password: str, out_path: Path) -> bool:
        if not self.pdf_path:
            return False
        reader = PdfReader(str(self.pdf_path))
        if not reader.decrypt(password):
            return False
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        with out_path.open("wb") as fh:
            writer.write(fh)
        return True

    def quit(self):
        self.driver.quit()
        self.phase = "closed"

# ---------------------------------------------------------------------------
# Session manager
# ---------------------------------------------------------------------------
SessionKey = Tuple[str, str]

class CrawlerPool:
    def __init__(self):
        self._pool: Dict[SessionKey, AadhaarCrawler] = {}

    def get(self, lead: str, app: str) -> AadhaarCrawler:
        key = (lead, app)
        if key not in self._pool or self._pool[key].phase == "closed":
            session_dir = DOWNLOADS / f"{lead}_{app}"
            session_dir.mkdir(parents=True, exist_ok=True)
            self._pool[key] = AadhaarCrawler(session_dir)
        return self._pool[key]

    def destroy(self, lead: str, app: str):
        key = (lead, app)
        if key in self._pool:
            try:
                self._pool[key].quit()
            finally:
                self._pool.pop(key, None)

pool = CrawlerPool()

# ---------------------------------------------------------------------------
# Flask API
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)

def _session(lead: str, appid: str) -> AadhaarCrawler:
    return pool.get(lead, appid)


@app.route("/<lead>/<app>/init", methods=["POST"])
def init_session(lead, app):
    crawler = _session(lead, app)
    crawler.open_portal()
    return {"phase": crawler.phase}

@app.route("/<lead>/<app>/captcha-url", methods=["GET"])
def captcha_url(lead, app):
    crawler = _session(lead, app)
    try:
        return jsonify({"src": crawler.get_captcha_src()})
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/<lead>/<app>/captcha-image", methods=["GET"])
def captcha_image(lead, app):
    crawler = _session(lead, app)
    try:
        src = crawler.get_captcha_src()
        if src.startswith("data:image") or src.startswith("data:application/image"):
            header, b64data = src.split(",", 1)
            image_data = base64.b64decode(b64data)
            response = make_response(image_data)
            response.headers.set("Content-Type", "image/png")
            return response
        else:
            r = requests.get(src)
            return send_file(BytesIO(r.content), mimetype="image/png")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/<lead>/<app>/fill-aadhaar", methods=["POST"])
def fill_aadhaar(lead, app):
    number = request.json.get("aadhaar", "")
    _session(lead, app).fill_aadhaar(number)
    return {"phase": "awaiting_captcha"}

@app.route("/<lead>/<app>/fill-captcha", methods=["POST"])
def fill_captcha(lead, app):
    captcha = request.json.get("captcha", "")
    _session(lead, app).fill_captcha(captcha)
    return {"phase": "awaiting_otp"}

@app.route("/<lead>/<app>/fill-otp", methods=["POST"])
def fill_otp(lead, app):
    otp = request.json.get("otp", "")
    crawler = _session(lead, app)
    pdf_path = crawler.fill_otp(otp)
    return send_file(pdf_path, as_attachment=True)

@app.route("/<lead>/<app>/unlock", methods=["POST"])
def unlock(lead, app):
    password = request.json.get("password", "")
    crawler = _session(lead, app)
    dest = crawler.session_dir / f"unlocked_{lead}_{app}.pdf"
    if crawler.unlock(password, dest):
        return send_file(dest, as_attachment=True)
    return {"error": "wrong password"}, 403

@app.route("/<lead>/<app>/status", methods=["GET"])
def status(lead, app):
    crawler = _session(lead, app)
    return {
        "phase": crawler.phase,
        "pdf": str(crawler.pdf_path) if crawler.pdf_path else None,
        "download_dir": str(crawler.session_dir)
    }

@app.route("/<lead>/<app>", methods=["DELETE"])
def close(lead, app):
    pool.destroy(lead, app)
    return {"closed": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7001, debug=False, use_reloader=False)
