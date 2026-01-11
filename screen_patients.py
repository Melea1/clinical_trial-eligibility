import pandas as pd
import glob
import os
import json
import time

try:
    import google.generativeai as genai
except ImportError:
    print("Error: 'google-generativeai' library not found. Please install it: pip install google-generativeai")
    exit(1)

# --- CONFIGURATION ---
PATIENT_FILE = 'patients_for_trial_screening.csv'
TRIALS_DIR = 'trials'
OUTPUT_FILE = 'screening_results.csv'
MAX_PATIENTS = 5  # Start with a small batch

# --- API SETUP ---
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    # Ask user for key if not in env
    api_key = input("Please enter your Google Gemini API Key: ").strip()

if not api_key:
    print("No API Key provided. Exiting.")
    exit(1)

genai.configure(api_key=api_key)

# Initialize Model
model = genai.GenerativeModel('gemini-2.0-flash')

# --- LOAD DATA ---
print(f"Loading patients from {PATIENT_FILE}...")
df_patients = pd.read_csv(PATIENT_FILE)
# Run on all patients
patients_to_screen = df_patients.to_dict(orient='records')

print(f"Loading trials from {TRIALS_DIR}...")
trial_files = glob.glob(os.path.join(TRIALS_DIR, "*.md"))
trials_data = {}
for tf in trial_files:
    trial_name = os.path.basename(tf).replace('.md', '')
    with open(tf, 'r') as f:
        trials_data[trial_name] = f.read()

# --- DEFINITIONS ---
results = []

def screen_patient(patient, trial_name, criteria_text):
    prompt = f"""
    You are an expert Clinical Research Associate.
    Your task is to determine if a patient is ELIGIBLE, INELIGIBLE, or UNCERTAIN for a clinical trial.

    ## TRIAL CRITERIA
    {criteria_text}

    ## PATIENT DATA
    {json.dumps(patient, indent=2)}

    ## INSTRUCTIONS
    1. Compare the patient data against the inclusion and exclusion criteria.
    2. Think step-by-step for each criterion.
    3. Output your final decision in strict JSON format.

    ## JSON OUTPUT FORMAT
    {{
      "decision": "ELIGIBLE" | "INELIGIBLE" | "UNCERTAIN",
      "reason": "Brief explanation of the key factor(s) leading to this decision.",
      "missing_info": ["List of missing data points helpful for decision, if any"]
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        text_resp = response.text
        
        # Use regex to find the JSON object
        import re
        match = re.search(r'\{.*\}', text_resp, re.DOTALL)
        if match:
            json_str = match.group(0)
            return json.loads(json_str)
        else:
            raise ValueError("No JSON found in response")
    except Exception as e:
        print(f"Error screening patient {patient.get('patient_id', 'Unknown')}: {e}")
        return {"decision": "ERROR", "reason": str(e), "missing_info": []}

# --- EXECUTION ---
print(f"Starting screening for {len(patients_to_screen)} patients against {len(trial_files)} trials...")

for i, patient in enumerate(patients_to_screen):
    pid = patient.get('patient_id') or patient.get('subject_id') # Handle potential different col names
    print(f"[{i+1}/{len(patients_to_screen)}] Screening Patient {pid}...")
    
    for trial_name, criteria in trials_data.items():
        result = screen_patient(patient, trial_name, criteria)
        
        # Store result
        row = {
            "patient_id": pid,
            "trial_name": trial_name,
            "decision": result.get("decision"),
            "reason": result.get("reason"),
            "missing_info": "; ".join(result.get("missing_info", []))
        }
        results.append(row)
        time.sleep(1) # Rate limit pause

# --- SAVE ---
df_results = pd.DataFrame(results)
df_results.to_csv(OUTPUT_FILE, index=False)
print(f"Screening complete! Results saved to {OUTPUT_FILE}")
