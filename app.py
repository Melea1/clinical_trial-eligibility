import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
import json
from screening_utils import configure_genai, screen_patient

# Set page config
st.set_page_config(layout="wide", page_title="Clinical Trial Screener", page_icon="🏥")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    /* Global Settings */
    [data-testid="stAppViewContainer"] { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
    
    /* Typography */
    h1, h2, h3 { color: #0f172a; font-family: 'Inter', sans-serif; }
    p, div, span, label { color: #334155; font-family: 'Inter', sans-serif; }
    
    /* Metric Cards */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    [data-testid="stMetricLabel"] { font-size: 0.9rem; color: #64748b; font-weight: 500; }
    [data-testid="stMetricValue"] { font-size: 2.2rem; color: #0f172a; font-weight: 700; }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; margin-bottom: 24px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        border-radius: 8px;
        background-color: #ffffff;
        color: #64748b;
        border: 1px solid #e2e8f0;
        padding: 0 24px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6 !important;
        color: #ffffff !important;
        border: none;
    }
</style>
""", unsafe_allow_html=True)

# sidebar API Key (Hidden/Backend)
# sidebar API Key (Hidden/Backend)
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key and "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]

if api_key:
    configure_genai(api_key)
else:
    # No key found in env or secrets
    pass

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## 🏥 ClinicalDSS")
    st.caption("AI-Powered Trial Screening")
    st.markdown("---")
    
    st.markdown("### ⚙️ Controls")
    # Filters moved here
    
    DATA_FILE = 'screening_results.csv'
    PATIENT_FILE = 'patients_for_trial_screening.csv'
    
    # Pre-loading data for sidebar filter usage
    if os.path.exists(DATA_FILE):
             df_temp = pd.read_csv(DATA_FILE)
             trials_list = df_temp['trial_name'].unique().tolist()
    else:
             trials_list = []
             
    selected_filter_trial = st.selectbox("Topic Focus", ["All Protocols"] + trials_list)
    
    st.markdown("---")
    st.caption(f"v1.0.2 • MIMIC-IV Data")


# --- HEADER ---
st.title("Clinical Trial Eligibility Dashboard")
st.markdown("Real-time decision support system for **Type 2 Diabetes** clinical trials.")
st.markdown("<br>", unsafe_allow_html=True)

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 Data Overview", "🩺 Patient Screening", "📂 Batch Processing", "📝 Protocol Management"])

# --- TAB 1: DASHBOARD ---
with tab1:
    @st.cache_data
    def load_data(file_mtime): 
        if os.path.exists(DATA_FILE):
             df_res = pd.read_csv(DATA_FILE)
        else:
             df_res = pd.DataFrame(columns=["patient_id", "trial_name", "decision", "reason", "missing_info"])
             
        if os.path.exists(PATIENT_FILE):
            df_pat = pd.read_csv(PATIENT_FILE)
            df_pat['patient_id'] = df_pat['patient_id'].astype(str)
            df_res['patient_id'] = df_res['patient_id'].astype(str)
        else:
            df_pat = pd.DataFrame()

        return df_res, df_pat

    file_mtime = os.path.getmtime(DATA_FILE) if os.path.exists(DATA_FILE) else 0
    df, df_patients = load_data(file_mtime)

    if df.empty:
        st.info("Waiting for data pipeline...")
    else:
        if selected_filter_trial != "All Protocols":
            filtered_df = df[df['trial_name'] == selected_filter_trial]
        else:
            filtered_df = df

        # KPI CARDS (No filters here anymore)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Screened", len(filtered_df), delta="Patients")
        c2.metric("Eligible", len(filtered_df[filtered_df['decision'] == 'ELIGIBLE']), delta_color="normal")
        c3.metric("Ineligible", len(filtered_df[filtered_df['decision'] == 'INELIGIBLE']), delta_color="inverse")
        c4.metric("Uncertain", len(filtered_df[filtered_df['decision'] == 'UNCERTAIN']), delta_color="off")

        st.markdown("<br>", unsafe_allow_html=True)
        
        # VISUALIZATION ROW
        c_chart, c_table = st.columns([1, 2])
        
        with c_chart:
            st.markdown("##### 📈 Eligibility Distribution")
            fig_pie = px.pie(filtered_df, names='decision', color='decision',
                            color_discrete_map={'ELIGIBLE':'#22c55e', 'INELIGIBLE':'#ef4444', 'UNCERTAIN':'#f97316', 'ERROR':'#64748b'},
                            hole=0.6)
            fig_pie.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=250)
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with c_table:
            st.markdown("##### 📋 Recent Decisions")
            # Create a more readable dataframe for display
            display_df = filtered_df[['patient_id', 'trial_name', 'decision']].copy()
            st.dataframe(display_df, height=250, use_container_width=True, hide_index=True)


        # --- PATIENT SNAPSHOT ---
        st.markdown("---")
        st.markdown("### 🧑‍⚕️ Patient 360° View")

        patient_ids = filtered_df['patient_id'].unique()
        selected_patient = st.selectbox("Search Patient ID", patient_ids)

        if selected_patient:
            c_profile, c_analysis = st.columns([1, 2])
            
            with c_profile:
                st.markdown("""<div style="background: white; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0;">
                                <h4 style="margin-top:0;">📋 Clinical Profile</h4>""", unsafe_allow_html=True)
                
                if not df_patients.empty and selected_patient in df_patients['patient_id'].values:
                    pat_row = df_patients[df_patients['patient_id'] == selected_patient].iloc[0]
                    
                    st.markdown(f"""
                    **Age:** {pat_row['age']} &nbsp; • &nbsp; **Gender:** {pat_row['gender']}<br>
                    **HbA1c:** {pat_row['hba1c']}% &nbsp; • &nbsp; **eGFR:** {pat_row['egfr']}<br>
                    **Insulin:** {'✅' if str(pat_row['insulin_user']).lower()=='true' else '❌'}
                    <hr style="margin: 10px 0;">
                    """, unsafe_allow_html=True)
                    
                    st.markdown("**💊 Medications**")
                    st.caption(str(pat_row['current_medications']).replace(';', ', '))
                    
                    # Pregnancy Check (Explicit Display)
                    diag_full = (str(pat_row.get('comorbidities', '')) + " " + str(pat_row.get('diagnoses', ''))).lower()
                    is_pregnant = any(x in diag_full for x in ['pregn', 'gestat'])
                    
                    st.markdown("**🤰 Pregnancy Status**")
                    if is_pregnant:
                        st.error("⚠️ DETECTED (Exclusion Risk)")
                    else:
                        st.caption("✅ Not Detected")

                    st.markdown("**🩺 Comorbidities**")
                    st.caption(str(pat_row['comorbidities']).replace(';', ', '))
                else:
                    st.warning("Data not found.")
                st.markdown("</div>", unsafe_allow_html=True)

            with c_analysis:
                st.markdown("#### 🤖 AI Screening Analysis")
                pat_data = filtered_df[filtered_df['patient_id'] == selected_patient]
                
                for i, row in pat_data.iterrows():
                    dec = row['decision']
                    color = "#22c55e" if dec == "ELIGIBLE" else "#ef4444" if dec == "INELIGIBLE" else "#f97316"
                    icon = "✅" if dec == "ELIGIBLE" else "🚫" if dec == "INELIGIBLE" else "⚠️"
                    
                    with st.expander(f"{icon} {row['trial_name']}", expanded=True):
                        st.markdown(f"<h3 style='color: {color}; margin:0;'>{dec}</h3>", unsafe_allow_html=True)
                        st.info(f"**Summary**: {row.get('reason')}")
                        
                        if pd.notna(row.get('missing_info')) and row.get('missing_info'):
                            st.warning(f"**Missing:** {row.get('missing_info')}")


# --- TAB 2: MANUAL SCREENING ---
with tab2:
    st.markdown("### 🩺 Human-in-the-Loop Screening")
    st.info("Enter clinical data below to screen a new patient in real-time.")
    
    # Load Trials
    trial_files = glob.glob(os.path.join('trials', "*.md"))
    trial_names = [os.path.basename(t).replace('.md', '') for t in trial_files]
    
    selected_manual_trial = st.selectbox("Select Protocol", trial_names, key="manual_trial")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        p_age = c1.number_input("Age", 18, 100, 55)
        p_gender = c2.selectbox("Gender", ["M", "F"])
        p_hba1c = c3.number_input("HbA1c (%)", 4.0, 15.0, 7.5)
        
        c_in, c_preg = st.columns(2)
        p_insulin = c_in.toggle("Uses Insulin?", value=False)
        p_pregnant = c_preg.checkbox("Pregnant?")
        
        p_meds = st.text_input("Medications", "Metformin, Lisinopril")
        p_conditions = st.text_area("Comorbidities", "Type 2 Diabetes, Hypertension, Hyperlipidemia")
        
        submit_btn = st.button("Run AI Screening ✨", type="primary", use_container_width=True)
    
    if submit_btn:
        # Check if key is available (Env or Secrets)
        if not os.environ.get("GEMINI_API_KEY") and not st.secrets.get("GEMINI_API_KEY"):
            st.error("⚠️ Backend API Key not configured.")
        else:
            patient_data = {
                "age": p_age, "gender": p_gender, "hba1c": p_hba1c,
                "current_medications": p_meds, "comorbidities": p_conditions,
                "insulin_user": p_insulin, "is_pregnant": p_pregnant
            }
            
            trial_path = os.path.join('trials', f"{selected_manual_trial}.md")
            with open(trial_path, 'r') as f: trial_text = f.read()
                
            with st.spinner("Analyzing criteria..."):
                result = screen_patient(patient_data, trial_text)
            
            # Result Display
            r_dec = result.get('decision', 'ERROR')
            r_color = "#22c55e" if r_dec == "ELIGIBLE" else "#ef4444" if r_dec == "INELIGIBLE" else "#f97316"
            
            st.markdown(f"""
            <div style="padding: 20px; border-radius: 10px; border-left: 5px solid {r_color}; background-color: #f8fafc; margin-bottom: 20px;">
                <h2 style="color: {r_color}; margin:0;">{r_dec}</h2>
                <p style="font-size: 1.1em; margin-bottom:0;">{result.get('reason')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            col_inc, col_exc = st.columns(2)
            with col_inc:
                st.caption("INCLUSION CRITERIA")
                if result.get('inclusion_criteria_met'):
                    for i in result.get('inclusion_criteria_met'): st.success(f"✅ {i}")
                if result.get('inclusion_criteria_not_met'):
                    for i in result.get('inclusion_criteria_not_met'): st.error(f"❌ {i}")

            with col_exc:
                st.caption("EXCLUSION CRITERIA")
                if result.get('exclusion_criteria_met'): 
                    for i in result.get('exclusion_criteria_met'): st.error(f"⛔ {i} (Found)")
                if result.get('exclusion_criteria_not_met'):
                    for i in result.get('exclusion_criteria_not_met'): st.success(f"✅ {i} (Not Found)")


# --- TAB 3: UPLOAD BATCH ---
with tab3:
    st.markdown("### 📂 Batch Processing")
    
    # 1. Select Protocol for Batch
    batch_trial_select = st.selectbox("Select Protocol for Batch Run", trial_names, key="batch_trial_select")
    
    uploaded_file = st.file_uploader("Drop patient CSV here", type=['csv'])
    
    if uploaded_file:
        df_upload = pd.read_csv(uploaded_file)
        
        # 2. Clear Preview Header
        st.markdown(f"**Preview of uploaded data ({len(df_upload)} rows total) - Showing first 5**:S")
        st.dataframe(df_upload.head(), use_container_width=True)
        
        if st.button("Start Batch Screening", type="primary"):
            if not os.environ.get("GEMINI_API_KEY") and not st.secrets.get("GEMINI_API_KEY"):
                st.error("API Key required in backend.")
            else:
                target_trial_path = os.path.join('trials', f"{batch_trial_select}.md")
                with open(target_trial_path, 'r') as f: batch_trial_text = f.read()
                
                # 3. Progress Tracking
                prog_bar = st.progress(0)
                status_text = st.empty()
                results_batch = []
                failures = 0
                
                total_rows = len(df_upload)
                
                for i, row in df_upload.iterrows():
                    # Update status
                    status_text.caption(f"Processing row {i+1}/{total_rows} • Failures: {failures}")
                    
                    try:
                        pat_dict = row.to_dict()
                        # Ensure ID is string to match system
                        pat_dict['patient_id'] = str(pat_dict.get('patient_id', f'BATCH_{i}'))
                        
                        res = screen_patient(pat_dict, batch_trial_text)
                        
                        results_batch.append({
                            "patient_id": pat_dict['patient_id'],
                            "trial_name": batch_trial_select,
                            "decision": res.get("decision", "ERROR"),
                            "reason": res.get("reason", "Unknown error"),
                            "missing_info": str(res.get("missing_info", []))
                        })
                    except Exception as e:
                        failures += 1
                        results_batch.append({
                            "patient_id": str(row.get('patient_id', f'ERR_{i}')),
                            "trial_name": batch_trial_select,
                            "decision": "ERROR",
                            "reason": f"System Crash: {str(e)}",
                            "missing_info": "[]"
                        })
                        
                    prog_bar.progress((i+1)/total_rows)
                
                # 4. Save Results & Dedupe
                if results_batch:
                    new_results = pd.DataFrame(results_batch)
                    
                    # Load existing if any
                    if os.path.exists(DATA_FILE):
                        existing_df = pd.read_csv(DATA_FILE)
                        # Remove old results that match the new (id + trial) to overwrite them with latest
                        # We use a composite key for filtering
                        existing_df['key'] = existing_df['patient_id'].astype(str) + "_" + existing_df['trial_name']
                        new_results['key'] = new_results['patient_id'].astype(str) + "_" + new_results['trial_name']
                        
                        # Authenticate: Keep rows in existing that are NOT in new
                        final_df = pd.concat([
                            existing_df[~existing_df['key'].isin(new_results['key'])],
                            new_results
                        ]).drop(columns=['key'])
                    else:
                        final_df = new_results
                    
                    final_df.to_csv(DATA_FILE, index=False)
                    st.success(f"✅ Batch Complete! Processed {total_rows} patients. ({failures} failures).")
                    st.info("Results saved to Dashboard. Go to 'Data Overview' tab to see them.")
                    st.dataframe(new_results.head(), use_container_width=True)
                else:
                    st.warning("No results generated.")


# --- TAB 4: MANAGE TRIALS ---
with tab4:
    st.markdown("### 📝 Protocols & Criteria")
    
    c_list, c_add = st.columns([1, 2])
    with c_list:
        st.markdown("**Active Protocols**")
        for t in trial_files:
            st.code(os.path.basename(t).replace('.md',''))
            
    with c_add:
        with st.form("new_trial"):
            st.markdown("**Import New Protocol**")
            n_name = st.text_input("Protocol ID")
            n_text = st.text_area("Criteria (Markdown)", height=200)
            if st.form_submit_button("Save Protocol"):
                # Save logic
                safe = "".join([c for c in n_name if c.isalnum() or c in ('_','-')])
                with open(os.path.join('trials', f"{safe}.md"), 'w') as f: f.write(n_text)
                st.success("Saved!")
                st.rerun()
