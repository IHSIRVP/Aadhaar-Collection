from tkinter import Tk, Label, Entry, Button, StringVar, DISABLED, NORMAL, Toplevel
from PIL import Image, ImageTk
import os, time, threading, fitz, requests, shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from PyPDF2 import PdfReader, PdfWriter
from flask import Flask, request, jsonify, send_from_directory
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import base64
# === Config ===
downloads_folder = os.path.expanduser("~/Downloads")
screenshot_path = "aadhaar_page.png"
chrome_binary_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
bearer_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc0ODM1MDA1MywianRpIjoiYTJmOTU5YzMtNzM2MS00M2NlLTg3ZTEtMDFmMGRiOWFiYmE4IiwidHlwZSI6ImFjY2VzcyIsImlkZW50aXR5IjoiZGV2LnN1bnRlY2tyZWFsdHlAc3VyZXBhc3MuaW8iLCJuYmYiOjE3NDgzNTAwNTMsImV4cCI6MTc1MDk0MjA1MywiZW1haWwiOiJzdW50ZWNrcmVhbHR5QHN1cmVwYXNzLmlvIiwidGVuYW50X2lkIjoibWFpbiIsInVzZXJfY2xhaW1zIjp7InNjb3BlcyI6WyJ1c2VyIl19fQ.dlZP9ep1mbsAoqov_ARLY5akUiavHJLLpY3qrK4jLT8"
locked_pdf_path = "static/locked.pdf"
unlocked_pdf_path = "static/unlocked.pdf"
status_text = {"status": "🔄 Starting...", "pdf_ready": False, "qr_text": ""}


# === Tkinter GUI ===
root = Tk()
root.title("Aadhaar Automation UI")
root.geometry("500x800")

aadhaar_var = StringVar()
captcha_var = StringVar()
otp_var = StringVar()

aadhaar_label = Label(root, text="Enter Aadhaar Number:")
aadhaar_entry = Entry(root, textvariable=aadhaar_var, state=DISABLED)
aadhaar_submit_btn = Button(root, text="Submit Aadhaar", state=DISABLED)

captcha_label_img = Label(root)
captcha_label = Label(root, text="Enter CAPTCHA:")
captcha_entry = Entry(root, textvariable=captcha_var)
captcha_submit_btn = Button(root, text="Submit CAPTCHA", state=DISABLED)

otp_label = Label(root, text="Enter OTP:")
otp_entry = Entry(root, textvariable=otp_var)
otp_submit_btn = Button(root, text="Submit OTP", state=DISABLED)

status_label = Label(root, text=status_text["status"])
response_display = Label(root, text="", justify="left", wraplength=480, anchor="w")

aadhaar_label.pack()
aadhaar_entry.pack()
aadhaar_submit_btn.pack(pady=10)
status_label.pack(pady=10)
response_display.pack(pady=10)

# === Chrome Setup ===
chrome_options = Options()
chrome_options.binary_location = chrome_binary_path
prefs = {"download.default_directory": downloads_folder}
chrome_options.add_experimental_option("prefs", prefs)
chromedriver_path = "/Users/rishivijaywargiya/chromedriver-mac-arm64/chromedriver"
driver = webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)
# Prevent window focus shifts
chrome_options.add_argument("--disable-backgrounding-occluded-windows")
chrome_options.add_argument("--disable-background-timer-throttling")
chrome_options.add_argument("--disable-renderer-backgrounding")
chrome_options.add_argument("--start-minimized")  # 👈 Starts minimiz


# === Helper ===
def update_status(msg):
    status_label.config(text=msg)
    status_text["status"] = msg

def read_qr_code_from_image(image_path):
    # url = "http://api.qrserver.com/v1/read-qr-code/"

    with open(image_path, "rb") as f:
        files = {"file": f}
        response = requests.post(url, files=files)
    try:
        data = response.json()
        return data[0]["symbol"][0]["data"]
    except Exception as e:
        print(f"❌ QR decode error: {e}")
        return None

def verify_aadhaar_qr_with_surepass(qr_text):
    url = "https://sandbox.surepass.io/api/v1/aadhaar/upload/qr"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    payload = {"qr_text": qr_text}
    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        if result.get("success"):
            data = result["data"]
            status_text["qr_text"] = data
            display_text = f"✅ Aadhaar Verified\n👤 Name: {data.get('full_name')}\n🎂 DOB: {data.get('dob')}\n⚧ Gender: {data.get('gender')}"
            response_display.config(text=display_text)
        else:
            error_msg = result.get("message", "Unknown error")
            response_display.config(text=f"❌ Verification failed: {error_msg}")
    except Exception as e:
        response_display.config(text=f"❌ API call error:\n{e}")

def wait_for_pdf_download(timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        for file in os.listdir(downloads_folder):
            if file.startswith("EAadhaar_") and file.endswith(".pdf") and not file.endswith(".crdownload"):
                return os.path.join(downloads_folder, file)
        time.sleep(1)
    return None

def unlock_pdf_and_process(path):
    def run():
        prompt = Toplevel(root)
        prompt.title("Unlock PDF")
        prompt.geometry("300x120")
        pass_var = StringVar()
        Label(prompt, text="Enter PDF Password:").pack(pady=5)
        Entry(prompt, textvariable=pass_var, show="*").pack()

        def try_unlock():
            try:
                with open(path, "rb") as f:
                    reader = PdfReader(f)
                    if reader.decrypt(pass_var.get()):
                        writer = PdfWriter()
                        for p in reader.pages:
                            writer.add_page(p)
                        if not os.path.exists("static"):
                            os.makedirs("static")
                        unlocked_path = os.path.join("static", "unlocked.pdf")
                        with open(unlocked_path, "wb") as out:
                            writer.write(out)
                        update_status("✅ PDF Unlocked.")
                        status_text["pdf_ready"] = True
                        img_path = extract_region_from_pdf(unlocked_path)
                        if img_path:
                            qr_data = read_qr_code_from_image(img_path)
                            if qr_data:
                                status_text["qr_text"] = qr_data
                                verify_aadhaar_qr_with_surepass(qr_data)
                        prompt.destroy()
                    else:
                        update_status("❌ Wrong password.")
            except Exception as e:
                update_status(f"❌ Unlock error: {e}")

        Button(prompt, text="Unlock", command=try_unlock).pack(pady=10)
    threading.Thread(target=run).start()

def extract_region_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        rect = fitz.Rect(200, 400, 300, 550)
        mat = fitz.Matrix(4, 4)
        pix = page.get_pixmap(matrix=mat, clip=rect)
        output_img = "static/extracted_region.png"
        pix.save(output_img)
        return output_img
    except Exception as e:
        print(f"❌ PDF extract error: {e}")
        return None

# === Submit OTP ===
def submit_otp():
    def run():
        try:
            otp_input = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//input[@name='otp']")))
            otp_input.clear()
            for o in otp_var.get():
                otp_input.send_keys(o)
                time.sleep(0.1)
            ActionChains(driver).move_to_element_with_offset(driver.find_element(By.TAG_NAME, "body"), 10, 10).click().perform()
            update_status("✅ OTP entered. Waiting for download...")
            for _ in range(30):
                try:
                    btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Verify') and contains(text(), 'Download')]")
                    if btn.value_of_css_property("cursor") == "pointer":
                        driver.execute_script("arguments[0].click();", btn)
                        update_status("📥 Download started.")
                        time.sleep(5)
                        path = wait_for_pdf_download()
                        if path:
                            if not os.path.exists("static"):
                                os.makedirs("static")
                            shutil.copy(path, locked_pdf_path)
                            update_status("✅ PDF downloaded and saved as locked.")
                            return
                except:
                    pass
                time.sleep(1)
            update_status("❌ 'Verify & Download' not clickable.")
        except Exception as e:
            update_status(f"❌ OTP error: {e}")
    threading.Thread(target=run).start()


# === Load Page ===
def load_page():
    def run():
        try:
            driver.get("https://myaadhaar.uidai.gov.in/genricDownloadAadhaar/en")
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, "uid")))
            update_status("✅ Page loaded. Enter Aadhaar number.")
            aadhaar_entry.config(state=NORMAL)
            aadhaar_submit_btn.config(state=NORMAL)
        except Exception as e:
            update_status(f"❌ Failed to load page: {e}")
    threading.Thread(target=run).start()

# === Flask API ===
app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": "*"}}) ## CORS Value Previous was ""CORS(app)"" -- MAIN
# CORS(app, resources={r"/*": {"origins": "https://0e85-2401-4900-56d3-624e-84a6-13c8-d129-ba05.ngrok-free.app"}})
# CORS(app, resources={r"/*": {"origins": "*"}}) 

CORS(
    app,
    resources={r"/*": {
        "origins": [
            "http://localhost:5174", 
            "https://2f6c-2405-201-15-20ef-c15f-2b15-a9a3-d9f7.ngrok-free.app"  # prod front-end -- Change this URL is the terminal shuts

        ]
    }}     # turn on only if you send cookies / auth headers
)


@app.route("/")
def index():
    return {"message": "Backend is running"}, 200



@app.route('/captcha-image', methods=['GET'])
def get_captcha_image():
    return send_from_directory('/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static', 'captcha_only.png')



@app.route('/set-aadhaar', methods=['POST'])

def set_aadhaar():
    data = request.json
    aadhaar_number = data.get("aadhaar")
    if aadhaar_number:
        aadhaar_var.set(aadhaar_number)
        if aadhaar_entry['state'] == NORMAL:
            submit_aadhaar()

        # Wait for CAPTCHA image to exist
        for _ in range(20):
            if os.path.exists("/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static"):
                break
            time.sleep(0.1)



        # ✅ Screenshot the full UIDAI page and encode as base64
        screenshot_file = "/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static/full_page_after_aadhaar.png"
        driver.save_screenshot(screenshot_file)

        with open(screenshot_file, "rb") as img_file:
            screenshot_base64 = base64.b64encode(img_file.read()).decode("utf-8")

        captcha_ready = os.path.exists("/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static")
        return jsonify({
            "status": "success",
            "message": "Aadhaar set",
            "captcha_ready": captcha_ready,
            "screenshot_base64": screenshot_base64  # ✅ added
        })
    return jsonify({"status": "error", "message": "No Aadhaar number received"}), 400

def submit_aadhaar():
    def run():
        try:
            aadhaar_input = driver.find_element(By.NAME, "uid")
            aadhaar_input.clear()
            aadhaar_input.send_keys(aadhaar_var.get())
            update_status("📷 Capturing CAPTCHA...")
            time.sleep(2)  # Give CAPTCHA a moment to load
            captcha_input = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, "//input[@name='captcha']")))
            driver.save_screenshot(screenshot_path)
            x, y = captcha_input.location['x'], captcha_input.location['y']
            if not os.path.exists("/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static"):
                os.makedirs("/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static")
            img = Image.open(screenshot_path).crop((x + 200, y + 300, x + 2000, y + 450))
            img.save("/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static/captcha_only.png")
            captcha_image = ImageTk.PhotoImage(Image.open("/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static/captcha_only.png"))
            captcha_label_img.config(image=captcha_image)
            captcha_label_img.image = captcha_image
            captcha_label_img.pack()
            captcha_label.pack()
            captcha_entry.pack()
            captcha_submit_btn.config(state=NORMAL)
            captcha_submit_btn.pack(pady=10)
            update_status("✍️ Enter CAPTCHA.")
        except Exception as e:
            update_status(f"❌ Aadhaar error: {e}")
    threading.Thread(target=run).start()


@app.route('/set-captcha', methods=['POST'])
def set_captcha():
    data = request.json
    captcha = data.get("captcha")
    if captcha:
        captcha_var.set(captcha)
        if captcha_submit_btn['state'] == NORMAL:
            submit_captcha()
        return jsonify({"status": "success", "message": "CAPTCHA set"})
    return jsonify({"status": "error", "message": "No CAPTCHA received"}), 400

def submit_captcha():
    def run():
        try:
            captcha_input = driver.find_element(By.XPATH, "//input[@name='captcha']")
            captcha_input.clear()
            for c in captcha_var.get():
                captcha_input.send_keys(c)
                time.sleep(0.1)
            ActionChains(driver).move_to_element_with_offset(driver.find_element(By.TAG_NAME, "body"), 5, 5).click().perform()
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Send OTP')]"))).click()
            update_status("📨 OTP sent. Enter OTP.")
            otp_label.pack()
            otp_entry.pack()
            otp_submit_btn.config(state=NORMAL)
            otp_submit_btn.pack(pady=10)
        except Exception as e:
            update_status(f"❌ CAPTCHA error: {e}")
    threading.Thread(target=run).start()


@app.route('/set-otp', methods=['POST'])
def set_otp():
    data = request.json
    otp = data.get("otp")
    if otp:
        otp_var.set(otp)
        if otp_submit_btn['state'] == NORMAL:
            submit_otp()
        # Wait briefly to allow backend to process
        for _ in range(60):
            if os.path.exists(locked_pdf_path):
                break
            time.sleep(1)
        if os.path.exists(locked_pdf_path):
            return send_file(locked_pdf_path, as_attachment=True)
        return jsonify({"status": "error", "message": "PDF not ready yet."})
    return jsonify({"status": "error", "message": "No OTP received"}), 400

from flask import request, jsonify

from flask import request, jsonify
import sys, logging

@app.route("/status", methods=["GET"])
def get_status():
    # preferred: use the Flask logger
    app.logger.info("🔍 /status hit – Origin=%s  URL=%s",
                    request.headers.get("Origin"), request.url)

    print("HIT")
    # if you still want plain print, flush immediately
    print("🧾 status_text:", status_text, flush=True)

    return jsonify(status_text)

@app.route('/check-download', methods=['GET'])
def check_download():
    if status_text["pdf_ready"]:
        return jsonify({"status": "ready", "message": "✅ PDF is ready to download."})
    else:
        return jsonify({"status": "not_ready", "message": "⏳ PDF is not ready yet."})

@app.route('/aadhaar-details', methods=['GET'])
def aadhaar_details():
    if status_text.get("qr_text"):
        return jsonify({"status": "success", "details": status_text["qr_text"]})
    else:
        return jsonify({"status": "error", "message": "QR data not available"}), 404
    
@app.route('/download-pdf', methods=['GET'])
def download_pdf():
    if os.path.exists(unlocked_pdf_path):
        return send_file(unlocked_pdf_path, as_attachment=True)
    return jsonify({"status": "error", "message": "Locked PDF not found."}), 404



@app.route("/verify-qr-text", methods=["POST"])
def verify_qr_text():
    try:
        data = request.get_json()
        qr_data = data.get("qr_text")
        print(qr_data)
        if not qr_data:
            return jsonify({"status": "error", "message": "Missing qr_text"}), 400

        headers = {
            "Authorization": f"Bearer {bearer_token}",  # 🔒 Replace with actual token
            "Content-Type": "application/json"
        }

        response = requests.post(
            # "https://sandbox.surepass.app/api/v1/aadhaar/upload/qr",
            headers=headers,
            json={"qr_text": qr_data}
        )
        response.raise_for_status()

        return jsonify(response.json())

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/scan', methods=['POST'])
def scan_qr_from_pdf():
    try:
        if not os.path.exists(unlocked_pdf_path):
            return jsonify({"status": "error", "message": "Unlocked PDF not found."}), 404

        # Step 1: Extract high-resolution QR region
        doc = fitz.open(unlocked_pdf_path)
        page = doc.load_page(0)
        rect = fitz.Rect(200, 400, 300, 550)
        mat = fitz.Matrix(4, 4)
        pix = page.get_pixmap(matrix=mat, clip=rect)
        qr_image_path = "static/extracted_region.png"
        pix.save(qr_image_path)
        

        # Step 2: Decode QR from image
        with open(qr_image_path, "rb") as f:
            files = {"file": f}
            qr_res = requests.post("http://api.qrserver.com/v1/read-qr-code/", files=files)

        qr_data = qr_res.json()[0]["symbol"][0]["data"]
        print("📦 QR Data:", qr_data)
        if not qr_data:
            return jsonify({"status": "error", "message": "QR code could not be read."}), 400
        qr_data = qr_data.strip()

        # Step 3: Verify QR via Surepass
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }
        payload = {"qr_text": qr_data}

        response = requests.post(
            # "https://sandbox.surepass.app/api/v1/aadhaar/upload/qr",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        print(result)

        print("📤 Surepass status:", response.status_code)
        print("📤 Surepass raw:", response.text)

        verify_data = response.json()
        if verify_data.get("success"):
            status_text["qr_text"] = verify_data["data"]
            return jsonify({"status": "success", "data": verify_data["data"]})
        else:
            return jsonify({
                "status": "error",
                "message": verify_data.get("message", "Verification failed.")
            }), 400

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

from werkzeug.utils import secure_filename
from io import BytesIO

@app.route('/analyze-image', methods=['POST'])
def analyze_image():
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400

        image_file = request.files['file']
        if image_file.filename == '':
            return jsonify({"status": "error", "message": "Empty filename"}), 400

        filename = secure_filename(image_file.filename)
        image_path = os.path.join("static", filename)

        # Save uploaded image
        if not os.path.exists("static"):
            os.makedirs("static")
        image_file.save(image_path)

        # Step 1: Decode QR
        with open(image_path, "rb") as f:
            files = {"file": f}
            # qr_res = requests.post("http://api.qrserver.com/v1/read-qr-code/", files=files)

        qr_data = qr_res.json()[0]["symbol"][0]["data"]
        print(qr_data)
        print("📦 QR Data from image:", qr_data)

        if not qr_data:
            return jsonify({"status": "error", "message": "QR code could not be read."}), 400

        qr_data = qr_data.strip()

        # Step 2: Verify via Surepass
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }
        payload = {"qr_text": qr_data}

        response = requests.post(
            "https://sandbox.surepass.app/api/v1/aadhaar/upload/qr",
            headers=headers,
            json=payload
        )

        if response.status_code != 200:
            return jsonify({
                "status": "error",
                "message": f"Surepass error: {response.status_code} - {response.text}"
            }), 500

        verify_data = response.json()
        print("✅ Surepass Response:", verify_data)

        if verify_data.get("success"):
            return jsonify({"status": "success", "data": verify_data["data"]})
        else:
            return jsonify({
                "status": "error",
                "message": verify_data.get("message", "Verification failed.")
            }), 400

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

import json
from datetime import datetime

@app.route('/check-image', methods=['POST'])
def check_image_text():
    try:
        data = request.get_json(force=True)
        qr_text = data.get("qr_text")

        if not qr_text:
            return jsonify({"status": "error", "message": "No QR text provided"}), 400

        print("📥 Received QR text:", qr_text[:100] + "...")

        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }
        payload = { "qr_text": qr_text.strip() }

        response = requests.post(
            "https://sandbox.surepass.app/api/v1/aadhaar/upload/qr",
            headers=headers,
            json=payload
        )

        if response.status_code != 200:
            return jsonify({
                "status": "error",
                "message": f"Surepass error: {response.status_code}",
                "details": response.text
            }), 500

        result = response.json()
        print(result)

        if result.get("success"):
            # ✅ Save result to a JSON file
            if not os.path.exists("logs"):
                os.makedirs("logs")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join("logs", f"aadhaar_verified_{timestamp}.json")

            with open(filepath, "w") as outfile:
                json.dump(result["data"], outfile, indent=2)

            print(f"📝 Result saved to {filepath}")
            return jsonify({"status": "success", "data": result["data"]})
        else:
            return jsonify({
                "status": "error",
                "message": result.get("message", "Verification failed.")
            }), 400

    except Exception as e:
        print("❌ Exception in /check-image:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500
    

@app.route('/aadhaar-latest', methods=['GET'])
def get_latest_aadhaar_result():
    try:
        print("HELLOO")
        logs_dir = "/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/logs"
        if not os.path.exists(logs_dir):
            print("NOWWW")
            return jsonify({"status": "error", "message": "No logs found"}), 404

        files = [f for f in os.listdir(logs_dir) if f.startswith("aadhaar_verified_") and f.endswith(".json")]
        if not files:
            return jsonify({"status": "error", "message": "No Aadhaar data available"}), 404

        latest_file = sorted(files)[-1]
        with open(os.path.join(logs_dir, latest_file), "r") as f:
            data = json.load(f)

        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
    file = request.files['file']

    print(file.name)
    files = {'file': (file.filename, file.stream, file.content_type)}
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    res = requests.post("https://kyc-api.surepass.app/api/v1/esign/upload", files=files, headers=headers)

    if res.status_code == 200:
        return jsonify(res.json())
    else:
        return jsonify({"error": "Upload failed", "details": res.text}), 500

@app.route('/unlock', methods=['POST'])
def unlock_pdf():
    data = request.json
    password = data.get("password")
    locked_pdf_path = "static/locked.pdf"
    unlocked_path = "static/unlocked.pdf"

    if not os.path.exists(locked_pdf_path):
        return jsonify({"status": "error", "message": "Locked PDF not found."}), 404

    try:
        with open(locked_pdf_path, "rb") as f:
            reader = PdfReader(f)
            if reader.decrypt(password):
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                with open(unlocked_path, "wb") as out:
                    writer.write(out)
                update_status("✅ PDF unlocked via API")
                return jsonify({"status": "success", "message": "PDF unlocked successfully."})
            else:
                return jsonify({"status": "error", "message": "Wrong password."}), 403
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

import signal
import sys

def safe_delete(path):
    try:
        if os.path.exists(path):
            os.remove(path)
            print(f"🧹 Deleted: {path}")
        else:
            print(f"⚠️ File not found: {path}")
    except Exception as e:
        print(f"❌ Error deleting {path}: {e}")

cleanup_paths = [
    
    "/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static/captcha_only.png",
    "/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static/full_page_after_aadhaar.png",
    "/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/aadhaar_page.png", 
    "/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static/extracted_region.png", 
    "/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static/locked.pdf", 
    "/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static/unlocked.pdf", 
    "/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/static/cropped.jpg", 
    "/Users/rishivijaywargiya/Desktop/FULL_For_IPAD/logs"

]

def cleanup_and_exit(signum, frame):
    print("\n🛑 Detected exit signal. Cleaning up...")
    for file_path in cleanup_paths:
        safe_delete(file_path)
    sys.exit(0)

# Register signal handler for Ctrl+C and termination
signal.signal(signal.SIGINT, cleanup_and_exit)   # Ctrl+C
signal.signal(signal.SIGTERM, cleanup_and_exit)  # Kill/terminate


def run_flask():
    # • turn the reloader off
    # • keep debug=False (True would start the reloader again)
    # • threaded=True lets Flask handle several requests while Tkinter is running
    app.run(
        host="0.0.0.0",
        port=6969,
        debug=False,
        use_reloader=False,
        threaded=True
    )

threading.Thread(target=run_flask, daemon=True).start()


# === GUI Start ===
load_page()
root.mainloop()
