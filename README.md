# LLM-Based Clinical Trial Eligibility Screening System

A Decision Support System (DSS) that uses Large Language Models (LLMs) to screen patients for clinical trial eligibility based on structured patient data and unstructured trial criteria.

## 📌 Project Overview
Clinical trial recruitment is often delayed due to the complexity of manually matching patients to strict inclusion/exclusion criteria. This project automates this process using **Google Gemini 2.0 Flash** to:
1.  Ingest patient health records (derived from MIMIC-IV).
2.  Parse clinical trial protocols (from ClinicalTrials.gov).
3.  Provide an **Eligible / Ineligible / Uncertain** decision with a natural language explanation.

## 📂 Repository Structure
-   `screen_patients.py`: Main script to run the screening process.
-   `extract_patients_flat.py`: Utility to sample patients from the dataset.
-   `trials/`: Directory containing eligibility criteria (Markdown format).
    -   `NCT06864546_Glutotrack.md`
    -   `DECLARE_TIMI58.md`
    -   `NCT05928572_CGM_Initiation.md`
-   `requirements.txt`: Python dependencies.
-   `screening_results.csv`: (Output) The results of the screening process.

## 🚀 Setup & Usage

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Key
You need a Google Gemini API key.
```bash
export GEMINI_API_KEY="your_api_key_here"
```

### 3. Run the Screener (Batch Script)
To screen patience against the defined trials via command line:
```bash
python3 screen_patients.py
```

### 4. Launch the Dashboard (Streamlit)
To visualize results and perform manual screening in a GUI:
```bash
streamlit run app.py
```

## 📊 Methods
-   **Data Source**: MIMIC-IV (De-identified electronic health records).
-   **Model**: Gemini 2.0 Flash (via `google-generativeai` library).
-   **Approach**: Zero-shot prompting with Chain-of-Thought reasoning.

## 📝 License
[Your License, e.g., MIT]
