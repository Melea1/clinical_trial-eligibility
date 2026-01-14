import google.generativeai as genai
import json
import re
import os
from typing import Any, Dict, List, Tuple

ALLOWED_DECISIONS = {"ELIGIBLE", "INELIGIBLE", "UNCERTAIN", "ERROR"}

EXPECTED_KEYS = [
    "decision",
    "reason",
    "inclusion_criteria_met",
    "inclusion_criteria_not_met",
    "exclusion_criteria_met",
    "exclusion_criteria_not_met",
    "missing_info",
]

def configure_genai(api_key: str) -> None:
    """Configures the Gemini API with the provided key."""
    if not api_key:
        raise ValueError("API Key is required.")
    os.environ["GEMINI_API_KEY"] = api_key
    genai.configure(api_key=api_key)

def _extract_json_candidate(text: str) -> str:
    """
    Extract a JSON object from a model response text.
    Tries fenced code blocks first, then falls back to brace matching.
    """
    if not text:
        return ""

    # Prefer ```json ... ``` blocks when available
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()

    # Fallback: attempt to find the first top-level JSON object via brace matching
    start = text.find("{")
    if start == -1:
        return ""

    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1].strip()

    return ""

def _ensure_list(value: Any) -> List[str]:
    """Normalize a field into a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        v = value.strip()
        return [v] if v else []
    # Any other type -> single-item list
    s = str(value).strip()
    return [s] if s else []

def _normalize_decision(decision: Any) -> str:
    """Normalize decision to one of the allowed decisions."""
    if decision is None:
        return "ERROR"
    d = str(decision).strip().upper()
    # Common variants
    if d in {"ELIGIBLE", "INELIG"}:
        return "ELIGIBLE"
    if d in {"INELIGIBLE", "NOT_ELIGIBLE", "INELIGIBLE."}:
        return "INELIGIBLE"
    if d in {"UNCERTAIN", "UNKNOWN", "UNSURE"}:
        return "UNCERTAIN"
    if d == "ERROR":
        return "ERROR"
    # Anything else is invalid -> ERROR
    return "ERROR"

def _validate_and_fix_result(result: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validate model output shape and enforce basic consistency rules.
    Returns (fixed_result, validation_warnings).
    """
    warnings: List[str] = []

    # Ensure all expected keys exist
    for k in EXPECTED_KEYS:
        if k not in result:
            result[k] = [] if k != "reason" and k != "decision" else ""
            warnings.append(f"Missing key '{k}' was added with a default value.")

    # Normalize decision + reason
    result["decision"] = _normalize_decision(result.get("decision"))
    if result["decision"] == "ERROR":
        if not result.get("reason"):
            result["reason"] = "Invalid or missing decision returned by model."
            warnings.append("Decision was invalid; set to ERROR.")

    if not isinstance(result.get("reason"), str):
        result["reason"] = str(result.get("reason", "")).strip()
        warnings.append("Reason was not a string; coerced to string.")

    # Normalize list fields
    result["inclusion_criteria_met"] = _ensure_list(result.get("inclusion_criteria_met"))
    result["inclusion_criteria_not_met"] = _ensure_list(result.get("inclusion_criteria_not_met"))
    result["exclusion_criteria_met"] = _ensure_list(result.get("exclusion_criteria_met"))
    result["exclusion_criteria_not_met"] = _ensure_list(result.get("exclusion_criteria_not_met"))
    result["missing_info"] = _ensure_list(result.get("missing_info"))

    # Sanity checks (basic clinical logic consistency)
    # Rule 1: Any exclusion met => should not be ELIGIBLE
    if result["decision"] == "ELIGIBLE" and len(result["exclusion_criteria_met"]) > 0:
        result["decision"] = "INELIGIBLE"
        warnings.append("Decision changed to INELIGIBLE because at least one exclusion criterion was met.")

    # Rule 2: Any inclusion not met => should not be ELIGIBLE
    if result["decision"] == "ELIGIBLE" and len(result["inclusion_criteria_not_met"]) > 0:
        result["decision"] = "INELIGIBLE"
        warnings.append("Decision changed to INELIGIBLE because at least one inclusion criterion was not met.")

    # Rule 3: If key patient fields are missing, UNCERTAIN is safer than ELIGIBLE
    if result["decision"] == "ELIGIBLE" and len(result["missing_info"]) > 0:
        result["decision"] = "UNCERTAIN"
        warnings.append("Decision changed to UNCERTAIN because missing information was reported.")

    # Ensure decision is always allowed
    if result["decision"] not in ALLOWED_DECISIONS:
        result["decision"] = "ERROR"
        warnings.append("Decision not in allowed set; forced to ERROR.")

    # Add warnings into reason
    if warnings and result["decision"] != "ERROR":
        result["reason"] = (result["reason"] or "").strip()
        note = " | Validation: " + "; ".join(warnings[:2])
        if result["reason"]:
            result["reason"] += note
        else:
            result["reason"] = "Validation applied." + note

    return result, warnings

def screen_patient(patient_data: Dict[str, Any], trial_text: str, model_name: str = "gemini-2.0-flash") -> Dict[str, Any]:
    """
    Screens a single patient against trial criteria using Gemini.
    """
    # Basic input checks
    if not isinstance(patient_data, dict) or not patient_data:
        return {
            "decision": "ERROR",
            "reason": "Invalid patient_data dict.",
            "missing_info": ["patient_data"],
        }

    try:
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        return {
            "decision": "ERROR",
            "reason": f"Model init failed: {e}",
            "missing_info": [],
        }

    prompt = f"""
    You are an expert Clinical Research Associate.
    Your task is to determine if a patient is ELIGIBLE, INELIGIBLE, or UNCERTAIN for a clinical trial.

    ## TRIAL CRITERIA
    {trial_text}

    ## PATIENT DATA
    {json.dumps(patient_data, indent=2)}

    ## INSTRUCTIONS
    1. Analyze the patient data against every single inclusion and exclusion criterion.
    2. **CRITICAL:** Provide a DETAILED reasoning in the 'reason' field, but write it as a natural clinical summary.
       - Quote specific patient values and trial limits.
       - Explain exactly why the match failed or succeeded.
       - **DO NOT** use "STEP 1", "STEP 2" labels. Write fluidly.
       - Be professional, verbose, and clear.
    3. Output your final decision in strict JSON format.
    
    ## JSON OUTPUT FORMAT
    {{
      "decision": "ELIGIBLE" | "INELIGIBLE" | "UNCERTAIN",
      "reason": "The patient is eligible based on age (45 vs >18) and diagnosis. However, ... [Detailed clinical narrative]",
      "inclusion_criteria_met": ["list of strings"],
      "inclusion_criteria_not_met": ["list of strings"],
      "exclusion_criteria_met": ["list of strings (bad)"],
      "exclusion_criteria_not_met": ["list of strings (good)"],
      "missing_info": ["list of strings"]
    }}
    """

    try:
        # RE-INJECTED TEMPERATURE 0.0
        generation_config = genai.types.GenerationConfig(temperature=0.0)
        
        response = model.generate_content(prompt, generation_config=generation_config)
        text_resp = getattr(response, "text", "") or ""

        json_candidate = _extract_json_candidate(text_resp)
        if not json_candidate:
            return {
                "decision": "ERROR",
                "reason": "No JSON found in model response. Raw: " + text_resp[:100],
                "missing_info": [],
            }

        try:
            parsed = json.loads(json_candidate)
        except Exception as e:
            return {
                "decision": "ERROR",
                "reason": f"Failed to parse JSON: {str(e)}",
                "missing_info": [],
            }

        if not isinstance(parsed, dict):
            return {
                "decision": "ERROR",
                "reason": "Parsed JSON is not an object.",
                "missing_info": [],
            }

        fixed, _warnings = _validate_and_fix_result(parsed)
        return fixed

    except Exception as e:
        return {
            "decision": "ERROR",
            "reason": str(e),
            "missing_info": [],
        }






