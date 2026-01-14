import google.generativeai as genai
import json
import re
import os

def configure_genai(api_key):
    """Configures the Gemini API with the provided key."""
    if not api_key:
        raise ValueError("API Key is required.")
    os.environ["GEMINI_API_KEY"] = api_key
    genai.configure(api_key=api_key)

def screen_patient(patient_data, trial_text, model_name='gemini-2.0-flash'):
    """
    Screens a single patient against trial criteria using Gemini.
    
    Args:
        patient_data (dict): Patient information.
        trial_text (str): Full text of the trial criteria.
        model_name (str): Gemini model to use.
        
    Returns:
        dict: The JSON decision from the model.
    """
    try:
        model = genai.GenerativeModel(model_name)
    except Exception as e:
         return {"decision": "ERROR", "reason": f"Model init failed: {e}", "missing_info": []}

    prompt = f"""
    You are an expert Clinical Research Associate.
    Your task is to determine if a patient is ELIGIBLE, INELIGIBLE, or UNCERTAIN for a clinical trial.

    ## TRIAL CRITERIA
    {trial_text}

    ## PATIENT DATA
    {json.dumps(patient_data, indent=2)}

    ## INSTRUCTIONS
    1. Analyze the patient data against every single inclusion and exclusion criterion.
    2. **CRITICAL:** Provide a VERY DETAILED, STEP-BY-STEP reasoning in the 'reason' field. 
       - Quote specific patient values (e.g. "Patient age is 45").
       - Quote specific trial limits (e.g. "Trial requires age > 50").
       - Explain exactly why the match failed or succeeded.
       - Do NOT be concise. Be verbose and clinical.
    3. Output your final decision in strict JSON format.
    
    ## JSON OUTPUT FORMAT
    {{
      "decision": "ELIGIBLE" | "INELIGIBLE" | "UNCERTAIN",
      "reason": "STEP 1: Checking Age... [analysis]. STEP 2: Checking HbA1c... [analysis]. CONCLUSION: [summary]",
      "inclusion_criteria_met": ["list of strings"],
      "inclusion_criteria_not_met": ["list of strings"],
      "exclusion_criteria_met": ["list of strings (bad)"],
      "exclusion_criteria_not_met": ["list of strings (good)"],
      "missing_info": ["list of strings"]
    }}
    """
    
    try:
        # Set temperature to 0.0 for maximum determinism (Low Creativity, High Factuality)
        generation_config = genai.types.GenerationConfig(temperature=0.0)
        
        response = model.generate_content(prompt, generation_config=generation_config)
        text_resp = response.text
        
        # 1. Advanced JSON Extraction
        json_str = ""
        # Try finding code block first
        code_block = re.search(r'```json\s*(\{.*?\})\s*```', text_resp, re.DOTALL)
        if code_block:
            json_str = code_block.group(1)
        else:
            # Fallback to brace matching
            match = re.search(r'\{.*\}', text_resp, re.DOTALL)
            if match:
                json_str = match.group(0)
        
        if not json_str:
            return {"decision": "ERROR", "reason": "No JSON found in response. Raw: " + text_resp[:100], "missing_info": []}

        # 2. Parse & Validate Structure
        data = json.loads(json_str)
        
        # Ensure strict keys exist with defaults
        final_res = {
            "decision": str(data.get("decision", "ERROR")).upper(),
            "reason": str(data.get("reason", "Unknown reason")),
            "inclusion_criteria_met": list(data.get("inclusion_criteria_met", [])),
            "inclusion_criteria_not_met": list(data.get("inclusion_criteria_not_met", [])),
            "exclusion_criteria_met": list(data.get("exclusion_criteria_met", [])),
            "exclusion_criteria_not_met": list(data.get("exclusion_criteria_not_met", [])),
            "missing_info": list(data.get("missing_info", []))
        }
        
        # 3. Sanitary Logic Overrides (Automated Quality Control)
        # Rule A: If any exclusion is met, patient MUST be INELIGIBLE
        if final_res["exclusion_criteria_met"] and final_res["decision"] == "ELIGIBLE":
            final_res["decision"] = "INELIGIBLE"
            final_res["reason"] = "[AUTO-CORRECT] Found met exclusion criteria. " + final_res["reason"]
            
        # Rule B: If any inclusion is NOT met, patient MUST be INELIGIBLE
        if final_res["inclusion_criteria_not_met"] and final_res["decision"] == "ELIGIBLE":
            final_res["decision"] = "INELIGIBLE"
            final_res["reason"] = "[AUTO-CORRECT] Found unmet inclusion criteria. " + final_res["reason"]
            
        # Rule C: If missing info and currently marked Eligible, downgrade to UNCERTAIN
        if final_res["missing_info"] and final_res["decision"] == "ELIGIBLE":
            final_res["decision"] = "UNCERTAIN"
            final_res["reason"] = "[AUTO-CORRECT] Missing critical info. " + final_res["reason"]

        return final_res
            
    except Exception as e:
        return {"decision": "ERROR", "reason": str(e), "missing_info": []}
