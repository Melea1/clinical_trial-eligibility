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
    1. Compare the patient data against the inclusion and exclusion criteria.
    2. Think step-by-step for each criterion.
    3. Output your final decision in strict JSON format.

    ## JSON OUTPUT FORMAT
    {{
      "decision": "ELIGIBLE" | "INELIGIBLE" | "UNCERTAIN",
      "reason": "Overall summary of the decision.",
      "inclusion_criteria_met": ["List of inclusion criteria specific to this trial that the patient MEETS"],
      "inclusion_criteria_not_met": ["List of inclusion criteria specific to this trial that the patient does NOT meet"],
      "exclusion_criteria_met": ["List of exclusion criteria specific to this trial that the patient MEETS (bad)"],
      "exclusion_criteria_not_met": ["List of exclusion criteria specific to this trial that the patient does NOT meet (good)"],
      "missing_info": ["List of missing data points helpful for decision, if any"]
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        text_resp = response.text
        
        # Robust JSON extraction
        match = re.search(r'\{.*\}', text_resp, re.DOTALL)
        if match:
            json_str = match.group(0)
            return json.loads(json_str)
        else:
            return {"decision": "ERROR", "reason": "No JSON found in response", "missing_info": []}
            
    except Exception as e:
        return {"decision": "ERROR", "reason": str(e), "missing_info": []}
