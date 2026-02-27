# Voice-to-Text Prescription

Offline-capable streaming speech-to-text and prescription drafting system for healthcare workflows.

## 1. Problem Statement

In many clinics and hospitals, doctors still type prescriptions manually or dictate notes to staff who later enter them into a healthcare application. This creates several problems:

* **Doctor time is wasted** on typing instead of patient interaction
* **Manual transcription is slow**
* **Prescription writing is inconsistent**
* **Important details can be missed** during hurried note-taking
* **Follow-up actions, tests, and advice** may not be captured in a structured format
* In some environments, **internet/cloud APIs cannot be used** due to privacy, compliance, or air-gapped/offline requirements

The goal of this project is to provide a local/offline-friendly system that:

1. Captures doctor speech in real time
2. Converts speech to text continuously
3. Generates a structured prescription draft from the transcript
4. Allows the doctor to **edit** the generated prescription before final use
5. Exports the prescription in text and JSON format
6. Can later be integrated into HMIS/EHR/healthcare applications

---

## 2. Proposed Solution

This system solves the problem in two stages:

### Stage 1: Real-time Dictation

* Doctor clicks a single **Dictate** button
* Audio is streamed from browser microphone to backend over WebSocket
* Backend transcribes audio incrementally using a local Whisper-based speech-to-text pipeline
* Partial transcript is shown live in the UI
* Final transcript is committed when dictation stops

### Stage 2: Prescription Generation

* Final transcript is sent to a locally running LLM endpoint
* LLM converts the doctor dictation into a structured prescription format
* Prescription is rendered in human-readable editable text
* Doctor can manually correct any wrong or missing details
* Final prescription can be copied or downloaded as:

  * `.txt`
  * `.json`

This reduces typing effort and creates a structured output useful for downstream integration.

---

## 3. What Is Implemented

### Frontend

* React-based UI
* Single **Dictate / Stop** microphone button
* Live transcript display in a single text area
* Prescription generation button
* Editable prescription text area
* Copy transcript
* Copy prescription
* Download prescription as TXT
* Download prescription as JSON

### Backend

* FastAPI server
* WebSocket endpoint for audio streaming
* Real-time Whisper transcription
* HTTP endpoint for prescription generation
* LLM integration through `llama-server.exe`
* JSON + markdown-like prescription output formatting

### LLM Output Covers

* Patient information
* Known conditions
* Allergies
* Diagnosis
* Vitals
* Medication list
* Dose pattern
* Timing instructions
* Tests / investigations
* Advice
* Return warnings / red flags
* Follow-up

---

## 4. High-Level Architecture

```text
Browser Mic
   ↓
React Frontend
   ↓  WebSocket (PCM audio chunks)
FastAPI Backend
   ↓
Whisper STT
   ↓
Transcript
   ↓  HTTP
llama.cpp server (Qwen2.5-3B-Instruct GGUF)
   ↓
Structured Prescription JSON
   ↓
Editable Prescription UI
   ↓
Copy / Download / Integrate into HMIS
```

---

## 5. Technologies Used

### Frontend

* React
* JavaScript
* HTML/CSS
* Web Audio API
* WebSocket

### Backend

* Python
* FastAPI
* Uvicorn
* WebSocket
* Faster-Whisper / Whisper-based transcription flow

### Local LLM

* `llama.cpp` / `llama-server.exe`
* `Qwen2.5-3B-Instruct-Q4_K_M.gguf`

### Data Formats

* JSON
* Plain text export

---

## 6. Why These Technologies

### Why React

* Fast UI iteration
* Easy state handling for transcript and prescription
* Easy later embedding into larger healthcare apps

### Why FastAPI

* Simple and fast backend APIs
* Easy WebSocket support
* Good for local/intranet microservice deployment

### Why Whisper-based STT

* Strong speech-to-text quality
* Good offline/local capability
* Better for noisy and natural dictation than browser-only speech recognition in many cases

### Why `llama-server.exe`

* Avoids Python native compilation issues with `llama-cpp-python`
* Easy to run local GGUF models
* Exposes simple OpenAI-style HTTP API
* Better for offline delivery and client deployment

### Why Qwen2.5-3B-Instruct Q4_K_M

* Small enough for local inference compared to larger models
* Good instruction-following for structured extraction
* Reasonable trade-off between quality and latency

---

## 7. Project Structure

```text
stt_prescript_streaming/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── llm_prescription.py
│   │   ├── llm_prescription_http.py
│   │   ├── audio.py
│   │   ├── sessions.py
│   │   └── stt.py
│   ├── models/
│   │   └── qwen2.5-3b-instruct-q4_k_m.gguf   # not committed to git
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── index.js
│   │   └── index.css
│   ├── package.json
│   └── package-lock.json
│
└── README.md
```

---

## 8. What Needs to Be Downloaded Separately

These large/runtime items are **not usually pushed to GitHub** and must be downloaded or placed manually.

### Required

1. **Python 3.10+**
2. **Node.js + npm**
3. **Qwen2.5-3B-Instruct GGUF model**

   * Place inside:

   ```text
   backend/models/
   ```
4. **llama.cpp Windows binary / llama-server.exe**

   * Used to serve the GGUF model locally

### Optional

* GPU support for faster inference
* Better microphone hardware for cleaner dictation

---

## 9. Setup Instructions

## 9.1 Backend Setup

Open terminal inside backend folder:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install requests
```

If `requirements.txt` does not include all needed packages, ensure these are installed:

* fastapi
* uvicorn
* requests
* faster-whisper
* numpy
* pydantic

---

## 9.2 Model Setup

Put the model file here:

```text
backend/models/qwen2.5-3b-instruct-q4_k_m.gguf
```

---

## 9.3 Start Local LLM Server

Example command:

```bash
cd /d "D:\path\to\llama_cpp_folder"
llama-server.exe -m "D:\path\to\backend\models\qwen2.5-3b-instruct-q4_k_m.gguf" --host 127.0.0.1 --port 8081 -c 4096
```

Expected output:

```text
server is listening on http://127.0.0.1:8081
```

---

## 9.4 Start Backend API

```bash
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

---

## 9.5 Start Frontend

```bash
cd frontend
npm install
npm start
```

Frontend will run at:

```text
http://localhost:3000
```

---

## 10. How to Use

1. Open frontend in browser
2. Click **Dictate**
3. Speak doctor dictation naturally
4. Click **Stop**
5. Final transcript appears
6. Prescription is generated automatically or via button
7. Review the generated prescription
8. Edit any incorrect information manually
9. Use:

   * **Copy Transcript**
   * **Copy Prescription**
   * **Download TXT**
   * **Download JSON**

---

## 11. Example Input

```text
Patient name is Ravi Kumar, age 52 years, male, UHID 102938. He has type 2 diabetes for 8 years and hypertension for 5 years. Allergy to penicillin causes rash. Today he came with fever for 3 days, cough with yellow sputum, sore throat, and mild shortness of breath since yesterday. No chest pain. No vomiting. He is on metformin 500 twice daily and amlodipine 5 mg once daily, taking regularly. On examination: temperature 101.4 Fahrenheit, blood pressure 152 over 94, pulse 96 per minute, respiratory rate 22 per minute, SpO2 94 percent on room air. Chest has mild wheeze and crackles at right base. Impression is acute bronchitis with possible early pneumonia, and diabetes and hypertension as comorbidities. Plan: start azithromycin 500 mg tablet once daily after food for 3 days. Paracetamol 650 mg tablet one tablet three times a day after food for 3 days as needed for fever. Levocetirizine 5 mg one tablet at night for 5 days. Salbutamol inhaler two puffs every 6 hours as needed for wheeze with spacer. Continue metformin and amlodipine same dose. Advise warm saline gargles, steam inhalation twice daily, drink plenty of fluids, and rest. Tests: CBC, CRP, random blood sugar, HbA1c, kidney function test, and chest X ray PA view. Warn patient to come immediately if breathing difficulty increases, SpO2 drops below 92, high fever persists more than 2 days, chest pain, confusion, or severe weakness. Follow up after 48 hours with reports, earlier if worsening.
```

---

## 12. Example Output

### Human-readable prescription

* Patient details
* Vitals
* Diagnosis
* Medications
* Advice
* Tests
* Follow-up
* Warning signs

### Structured JSON

Useful for:

* HMIS integration
* downstream automation
* analytics
* audit trail
* structured storage

---

## 13. What Pain Points This Solves

### Before

* Doctor types manually
* Staff re-enters dictated notes
* Delays in prescription generation
* Inconsistent formatting
* Repetition for common advice/tests
* Higher chance of omission

### After

* Dictate once
* Auto transcript
* Auto structured prescription draft
* Edit and finalize quickly
* Export in reusable format

---

## 14. Time Saved / Operational Value

Actual savings depend on doctor style, specialty, and case complexity.

### Typical manual process

* Typing/transcribing note + prescription: **2 to 5 minutes per patient**

### With this system

* Dictation + review/edit: **45 seconds to 2 minutes per patient**

### Approximate savings

* **30 to 70 percent reduction** in documentation time for routine OPD cases
* Faster generation of repeated medication/advice/test instructions
* Less retyping across patient visits

If a doctor sees:

* **40 patients/day**
* and saves even **1.5 minutes per patient**

That is:

* **60 minutes/day saved**
* **~25 hours/month** saved (assuming ~25 working days)

This can improve:

* doctor throughput
* patient face time
* consistency in documentation

---

## 15. Accuracy Expectations

### STT Accuracy

Depends on:

* microphone quality
* background noise
* accent
* medical terminology
* speaking pace

In clean environments, transcript quality is usually good enough for draft generation, but **doctor review is mandatory**.

### Prescription Accuracy

The LLM generates a **draft**, not an autonomous final prescription.
It can:

* miss vitals if not clearly dictated
* normalize dose patterns incorrectly in some cases
* omit fields if input is incomplete
* misunderstand ambiguous medicine timing

### Important Rule

**Doctor must always review and edit before final use.**

This tool is a **clinical drafting assistant**, not a replacement for clinician judgment.

---

## 16. Trade-offs

## 16.1 Why local/offline inference

### Pros

* Better privacy
* No cloud dependency
* Good for intranet / air-gapped use
* More control over deployment

### Cons

* More local hardware load
* Larger runtime package size
* Setup complexity higher than cloud APIs
* Smaller local models may be less accurate than larger hosted models

---

## 16.2 Why Qwen 3B instead of a larger model

### Pros

* Faster inference locally
* Lower memory use
* Easier offline deployment

### Cons

* Less robust than larger models
* May require prompt tuning and post-processing

---

## 16.3 Why editable prescription output

### Pros

* Safer clinical workflow
* Doctor can correct mistakes immediately
* Practical for real usage

### Cons

* Still requires human review
* Final structured JSON may not fully reflect manual text edits unless synchronized

---

## 17. Current Limitations

* Model may not always extract all vitals perfectly
* Timing instructions may be generic if not explicitly dictated
* Drug interaction logic is currently basic or prompt-driven only
* No formal medical coding integration yet
* No EMR/HMIS authentication or patient context injection yet
* Manual edit in text area does not automatically update structured JSON

---

## 18. Future Improvements

* HMIS/EHR integration API
* ICD suggestion support
* Drug interaction checking
* Patient allergy safety rules
* Editable structured medication table
* PDF prescription export
* Doctor templates / specialty templates
* Multi-language dictation
* Role-based access and audit logs
* Packaging as Windows service / portable installer / EXE

---

## 19. Integration with Healthcare Applications

This system is designed to be integrated as a local AI microservice.

### Integration flow

Healthcare application can:

1. Send transcript text to:

   ```text
   POST /api/prescription
   ```
2. Receive:

   * structured JSON
   * formatted prescription text
3. Map output to HMIS prescription fields

This allows use inside:

* hospital intranet apps
* clinic software
* HMIS/EHR products
* local desktop healthcare systems

---

## 20. API Summary

### Health check

```http
GET /health
```

### Generate prescription

```http
POST /api/prescription
Content-Type: application/json
```

Request:

```json
{
  "text": "doctor dictation transcript here"
}
```

Response:

```json
{
  "prescription": { "...structured json..." },
  "markdown": "formatted prescription text"
}
```

### Real-time dictation

```text
WebSocket /ws/stt
```

Used for streaming microphone audio and transcript updates.

---

## 21. Safety Note

This software generates a **draft prescription** from dictated clinical input.

It must be treated as an **assistant tool only**.

* Final diagnosis is clinician responsibility
* Final medicine selection is clinician responsibility
* Final dosage and contraindication checks are clinician responsibility
* Review before saving, printing, or prescribing is mandatory

---

## 22. Git / Repository Notes

Large files such as:

* `.venv`
* `node_modules`
* `.gguf` models
* `backend/models/`

should not be pushed to Git.

Use `.gitignore` to exclude them.

---

## 23. Summary

This project provides a practical, offline-friendly way to convert doctor dictation into an editable prescription draft using:

* streaming speech-to-text
* local LLM-based prescription structuring
* editable frontend review
* downloadable text and JSON outputs

It is designed to reduce documentation burden and prepare for integration into real healthcare applications.

---
