import { useState } from "react";

export default function AadhaarTestApp() {
  const [lead, setLead] = useState("lead1");
  const [applicant, setApplicant] = useState("user1");
  const [aadhaar, setAadhaar] = useState("");
  const [captcha, setCaptcha] = useState("");
  const [otp, setOtp] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("Idle");
  const [captchaUrl, setCaptchaUrl] = useState("");

  const backend = "http://127.0.0.1:7001";
  const path = (p) => `${backend}/${lead}/${applicant}${p}`;

  const post = async (url, body = {}) => {
    const res = await fetch(path(url), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return res.ok ? await res.json() : { error: await res.text() };
  };

  const downloadBlob = async (url) => {
    const res = await fetch(path(url), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(url === "/unlock" ? { password } : { otp }),
    });
    if (!res.ok) return setStatus(await res.text());
    const blob = await res.blob();
    const urlObj = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = urlObj;
    a.download = url.includes("unlock") ? "unlocked.pdf" : "aadhaar.pdf";
    a.click();
    URL.revokeObjectURL(urlObj);
  };

  return (
    <div style={{ maxWidth: 600, margin: "0 auto", padding: 20 }}>
      <h2>Aadhaar Automation UI</h2>

      <div>
        <input placeholder="Lead ID" value={lead} onChange={(e) => setLead(e.target.value)} />
        <input placeholder="Applicant ID" value={applicant} onChange={(e) => setApplicant(e.target.value)} />
      </div>

      <button onClick={async () => setStatus(JSON.stringify(await post("/init")))}>Init Session</button>

      <div>
        <input placeholder="Aadhaar Number" value={aadhaar} onChange={(e) => setAadhaar(e.target.value)} />
        <button onClick={async () => setStatus(JSON.stringify(await post("/fill-aadhaar", { aadhaar })))}>
          Submit Aadhaar
        </button>
      </div>

      <div>
      <button onClick={async () => {
        const res = await fetch(path("/captcha-url"));
        const json = await res.json();
        if (json.src) setCaptchaUrl(json.src);
        setStatus(JSON.stringify(json));
      }}>
        Load Captcha
      </button>

      {captchaUrl && (
        <div style={{ marginTop: 10 }}>
          <img
  src={`http://localhost:7001/${lead}/${applicant}/captcha-image`}
  alt="CAPTCHA"
  style={{ border: "1px solid #ccc", marginTop: 10 }}
/>
        </div>
      )}

      <input placeholder="Captcha" value={captcha} onChange={(e) => setCaptcha(e.target.value)} />
      <button onClick={async () => setStatus(JSON.stringify(await post("/fill-captcha", { captcha })))}>
        Submit Captcha
      </button>
    </div>

      <div>
        <input placeholder="OTP" value={otp} onChange={(e) => setOtp(e.target.value)} />
        <button onClick={() => downloadBlob("/fill-otp")}>Submit OTP & Download</button>
      </div>

      <div>
        <input placeholder="PDF Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button onClick={() => downloadBlob("/unlock")}>Unlock PDF</button>
      </div>

      <div>
        <button onClick={async () => {
          const res = await fetch(path("/status"));
          setStatus(JSON.stringify(await res.json()));
        }}>
          Status
        </button>

        <button onClick={async () => {
          const res = await fetch(path(""), { method: "DELETE" });
          setStatus(JSON.stringify(await res.json()));
        }}>
          Close Session
        </button>
      </div>

      <pre style={{ background: "#f0f0f0", padding: 10, borderRadius: 5 }}>{status}</pre>
    </div>
  );
}
