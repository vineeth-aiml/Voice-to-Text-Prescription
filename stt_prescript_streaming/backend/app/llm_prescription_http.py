import json
import re
import requests
from typing import Any, Dict, List

LLAMA_CHAT_URL = "http://127.0.0.1:8081/v1/chat/completions"

SYSTEM = (
    "You are a clinical documentation + prescription assistant. "
    "Return STRICT JSON only. Do NOT invent facts. "
    "If unknown, use empty string or empty list."
)

SCHEMA: Dict[str, Any] = {
    "patient": {"name": "", "age": "", "sex": "", "id": "", "allergies": [], "known_conditions": []},
    "encounter": {
        "chief_complaints": [],
        "history_of_present_illness": "",
        "exam_notes": "",
        "vitals": {"temperature": "", "bp": "", "pulse": "", "rr": "", "spo2": "", "weight": ""}
    },
    "assessment": {"diagnosis_primary": "", "diagnosis_secondary": [], "differentials": []},
    "plan": {
        "medications": [
            {
                "name": "",
                "strength": "",
                "form": "",
                "route": "",
                "dose_pattern": "",   # REQUIRED: 1-0-1 style OR q6h
                "timing": "",         # REQUIRED: After food / Before breakfast / At bedtime etc
                "duration": "",
                "quantity": "",
                "instructions": "",
                "indication": ""
            }
        ],
        "investigations": [],
        "advice": [],
        "follow_up": ""
    },
    "safety": {"red_flags": [], "when_to_return": [], "drug_warnings": []},
    "quality": {"missing_information_questions": [], "confidence": {"overall": 0.0}}
}

def _clean(s: str) -> str:
    return (s or "").strip()

def _freq_to_pattern(freq: str) -> str:
    f = _clean(freq).lower()
    if re.fullmatch(r"\d-\d-\d", f):
        return f

    # common abbreviations to Indian pattern
    if "tds" in f or "thrice" in f:
        return "1-1-1"
    if "bd" in f or "twice" in f:
        return "1-0-1"
    if "od" in f or "once" in f:
        return "1-0-0"
    if "qhs" in f or "hs" in f or "bedtime" in f or "night" in f:
        return "0-0-1"

    # every X hours
    if "q6h" in f or "every 6" in f:
        return "q6h"
    if "q8h" in f or "every 8" in f:
        return "q8h"
    if "q12h" in f or "every 12" in f:
        return "q12h"

    return _clean(freq)

def _infer_timing(instructions: str) -> str:
    t = _clean(instructions).lower()
    if "before breakfast" in t:
        return "Before breakfast"
    if "after breakfast" in t:
        return "After breakfast"
    if "before lunch" in t:
        return "Before lunch"
    if "after lunch" in t:
        return "After lunch"
    if "before dinner" in t:
        return "Before dinner"
    if "after dinner" in t:
        return "After dinner"
    if "bedtime" in t or "night" in t or "qhs" in t or "hs" in t:
        return "At bedtime"
    if "before food" in t or "empty stomach" in t:
        return "Before food"
    if "after food" in t or "with food" in t:
        return "After food"
    if "morning" in t:
        return "Morning"
    if "evening" in t:
        return "Evening"
    return ""

def _extract_json(text: str) -> dict:
    a = text.find("{")
    b = text.rfind("}")
    if a != -1 and b != -1 and b > a:
        text = text[a:b+1]
    return json.loads(text)

def _regex_fill_vitals(rx: dict, source_text: str) -> None:
    enc = rx.get("encounter") or {}
    vit = enc.get("vitals") or {}
    blob = source_text or ""

    if not vit.get("temperature"):
        m = re.search(r"temperature\s*[:\-]?\s*(\d+(\.\d+)?)", blob, re.I)
        if m: vit["temperature"] = m.group(1)
        else:
            m = re.search(r"(\d+(\.\d+)?)\s*f", blob, re.I)
            if m: vit["temperature"] = m.group(1) + " F"

    if not vit.get("bp"):
        m = re.search(r"(bp|blood pressure)\s*[:\-]?\s*(\d{2,3})\s*(/|over)\s*(\d{2,3})", blob, re.I)
        if m: vit["bp"] = f"{m.group(2)}/{m.group(4)}"

    if not vit.get("pulse"):
        m = re.search(r"pulse\s*[:\-]?\s*(\d{2,3})", blob, re.I)
        if m: vit["pulse"] = m.group(1)

    if not vit.get("rr"):
        m = re.search(r"(rr|respiratory rate)\s*[:\-]?\s*(\d{2,3})", blob, re.I)
        if m: vit["rr"] = m.group(2)

    if not vit.get("spo2"):
        m = re.search(r"(spo2|saturation)\s*[:\-]?\s*(\d{2,3})\s*%?", blob, re.I)
        if m: vit["spo2"] = m.group(2) + "%"

    enc["vitals"] = vit
    rx["encounter"] = enc

def _postprocess(rx: dict, source_text: str) -> dict:
    _regex_fill_vitals(rx, source_text)

    plan = rx.get("plan") or {}
    meds = plan.get("medications") or []
    for m in meds:
        # normalize pattern even if model outputs OD/BD/QHS in wrong field
        raw = m.get("dose_pattern") or m.get("frequency") or ""
        m["dose_pattern"] = _freq_to_pattern(raw)

        # timing
        if not _clean(m.get("timing", "")):
            m["timing"] = _infer_timing(m.get("instructions", ""))

        # if OD but instructions say "night"
        if m["dose_pattern"] == "1-0-0" and "night" in _clean(m.get("instructions", "")).lower():
            m["dose_pattern"] = "0-0-1"
            if not m.get("timing"):
                m["timing"] = "At bedtime"

    plan["medications"] = meds
    rx["plan"] = plan
    return rx

def rx_from_text(dictation: str) -> dict:
    prompt = (
        "Extract a structured prescription from this doctor dictation.\n\n"
        f"DICTATION:\n\"\"\"{dictation}\"\"\"\n\n"
        "Return ONLY valid JSON matching this schema:\n"
        f"{json.dumps(SCHEMA, indent=2)}\n\n"
        "CRITICAL RULES:\n"
        "1) If dictation contains vitals, fill them exactly: temperature, bp, pulse, rr, spo2.\n"
        "2) For each medication, dose_pattern MUST be EXACT Indian format: "
        "1-0-0 / 1-0-1 / 1-1-1 / 0-0-1. (OD=>1-0-0, BD=>1-0-1, TDS=>1-1-1, QHS/HS=>0-0-1)\n"
        "3) timing MUST be one of: Before breakfast, After breakfast, Before lunch, After lunch, "
        "Before dinner, After dinner, At bedtime, Before food, After food, Morning, Evening.\n"
        "4) Do not invent missing data.\n"
    )

    payload = {
        "model": "local",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1600,
    }

    r = requests.post(LLAMA_CHAT_URL, json=payload, timeout=180)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()

    rx = _extract_json(content)
    return _postprocess(rx, dictation)

def rx_markdown(rx: dict) -> str:
    p = rx.get("patient", {}) or {}
    enc = rx.get("encounter", {}) or {}
    vit = enc.get("vitals", {}) or {}
    ass = rx.get("assessment", {}) or {}
    plan = rx.get("plan", {}) or {}
    safety = rx.get("safety", {}) or {}

    lines: List[str] = []
    lines.append(f"Patient: {_clean(p.get('name'))} | Age/Sex: {_clean(p.get('age'))} {_clean(p.get('sex'))}".strip())
    if _clean(p.get("id")):
        lines.append(f"UHID: {_clean(p.get('id'))}")
    if p.get("allergies"):
        lines.append("Allergies: " + ", ".join(p.get("allergies", [])))
    if p.get("known_conditions"):
        lines.append("Known conditions: " + ", ".join(p.get("known_conditions", [])))

    vparts = []
    if _clean(vit.get("temperature")): vparts.append(f"Temp: {_clean(vit.get('temperature'))}")
    if _clean(vit.get("bp")): vparts.append(f"BP: {_clean(vit.get('bp'))}")
    if _clean(vit.get("pulse")): vparts.append(f"Pulse: {_clean(vit.get('pulse'))}")
    if _clean(vit.get("rr")): vparts.append(f"RR: {_clean(vit.get('rr'))}")
    if _clean(vit.get("spo2")): vparts.append(f"SpO2: {_clean(vit.get('spo2'))}")
    if vparts:
        lines.append("Vitals: " + " | ".join(vparts))

    dx = []
    if _clean(ass.get("diagnosis_primary")):
        dx.append(_clean(ass.get("diagnosis_primary")))
    dx += (ass.get("diagnosis_secondary") or [])
    if dx:
        lines.append("Diagnosis: " + ", ".join([_clean(x) for x in dx if _clean(x)]))

    meds = plan.get("medications") or []
    if meds:
        lines.append("\nMedications:")
        for i, m in enumerate(meds, 1):
            name = _clean(m.get("name"))
            strength = _clean(m.get("strength"))
            form = _clean(m.get("form"))
            route = _clean(m.get("route"))
            pat = _clean(m.get("dose_pattern"))
            timing = _clean(m.get("timing"))
            dur = _clean(m.get("duration"))

            main = f"{i}. {name} {strength}".strip()
            meta = " | ".join([x for x in [form, route, pat, timing, (f"x {dur}" if dur else "")] if x])
            lines.append((main + (" — " + meta if meta else "")).strip())

            instr = _clean(m.get("instructions"))
            if instr:
                lines.append("   " + instr)

    if plan.get("investigations"):
        lines.append("\nTests: " + ", ".join(plan.get("investigations", [])))
    if plan.get("advice"):
        lines.append("\nAdvice: " + ", ".join(plan.get("advice", [])))
    if safety.get("when_to_return"):
        lines.append("\nReturn immediately if: " + ", ".join(safety.get("when_to_return", [])))
    if plan.get("follow_up"):
        lines.append("\nFollow-up: " + plan.get("follow_up"))

    return "\n".join(lines)