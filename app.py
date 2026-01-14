import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
import json
from screening_utils import configure_genai, screen_patient

# Set page config
st.set_page_config(layout="wide", page_title="Clinical Trial Screener", page_icon="🏥")

# Ensure trials dir exists
os.makedirs("trials", exist_ok=True)

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
    
    /* Input Fields Background */
    div[data-baseweb="input"] { background-color: #ffffff !important; color: #0f172a !important; }
    div[data-baseweb="select"] { background-color: #ffffff !important; color: #0f172a !important; }
    textarea { background-color: #ffffff !important; color: #0f172a !important; }
</style>
""", unsafe_allow_html=True)

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
    
    DATA_FILE = 'screening_results.csv'
    PATIENT_FILE = 'patients_for_trial_screening.csv'

    # Load Trial Files
    trial_files_all = glob.glob(os.path.join('trials', "*.md"))
    trial_names_files = [os.path.basename(t).replace('.md', '') for t in trial_files_all]

    # Pre-loading data for sidebar filter usage
    trials_list = trial_names_files.copy()
    if os.path.exists(DATA_FILE):
             df_temp = pd.read_csv(DATA_FILE)
             existing_trials = df_temp['trial_name'].unique().tolist()
             trials_list = list(set(trials_list + existing_trials))
    
    # Sort list
    trials_list.sort()

    col_filter, col_refresh = st.columns([4, 1])
    with col_filter:
        selected_filter_trial = st.selectbox("Topic Focus", ["All Protocols"] + trials_list)
    with col_refresh:
        if st.button("🔄", help="Refresh List"):
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")
    st.caption(f"v1.0.5 • Found {len(trials_list)} protocols")
    
    # DEBUG UTILS
    with st.expander("🕵️ Debug: File List", expanded=False):
        st.write("Files in /trials:")
        for t in trial_files_all:
             st.code(t)


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

        # KPI CARDS
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

                    # Pregnancy Check
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
                        
                        # Show Detailed Lists if available
                        if row.get('inclusion_criteria_not_met') and row.get('inclusion_criteria_not_met') != "[]":
                             st.error(f"❌ Unmet Inclusions: {row.get('inclusion_criteria_not_met')}")
                        if row.get('exclusion_criteria_met') and row.get('exclusion_criteria_met') != "[]":
                             st.error(f"⛔ Met Exclusions: {row.get('exclusion_criteria_met')}")

                        if pd.notna(row.get('missing_info')) and row.get('missing_info') and row.get('missing_info') != "[]":
                            st.warning(f"**Missing:** {row.get('missing_info')}")


# --- TAB 2: MANUAL SCREENING ---
with tab2:
    st.markdown("### 🩺 Human-in-the-Loop Screening")
    st.info("Enter clinical data below to screen a new patient in real-time.")

    # Load Trials for Manual
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
        if not os.environ.get("GEMINI_API_KEY") and not st.secrets.get("GEMINI_API_KEY"):
            st.error("⚠️ Backend API Key not configured.")
        else:
            patient_data = {
                "age": p_age, "gender": p_gender, "hba1c": p_hba1c,
                "current_medications": p_meds, "comorbidities": p_conditions,
                "insulin_user": p_insulin, "is_pregnant": p_pregnant
            }

            trial_path = os.path.join('trials', f"{selected_manual_trial}.md")
            if os.path.exists(trial_path):
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
                
                # Show parsed lists
                col_i, col_e = st.columns(2)
                with col_i:
                    if result.get('inclusion_criteria_not_met'):
                        for x in result.get('inclusion_criteria_not_met'): st.error(f"❌ {x}")
                with col_e:
                    if result.get('exclusion_criteria_met'):
                        for x in result.get('exclusion_criteria_met'): st.error(f"⛔ {x}")
            else:
                st.error("Trial file not found.")


# --- TAB 3: UPLOAD BATCH ---
with tab3:
    st.markdown("### 📂 Batch Processing")
    uploaded_file = st.file_uploader("Drop patient CSV here", type=["csv"])

    if len(trial_names) == 0:
        st.error("No protocols found in the 'trials' folder.")
    else:
        selected_batch_trial = st.selectbox(
            "Select Protocol for Batch Screening",
            trial_names,
            key="batch_trial"
        )

        if uploaded_file:
            df_upload = pd.read_csv(uploaded_file)
            st.markdown("#### 👀 Preview")
            st.dataframe(df_upload.head(), use_container_width=True, hide_index=True)

            if st.button("Start Batch Screening", type="primary", use_container_width=True):
                if not os.environ.get("GEMINI_API_KEY") and not st.secrets.get("GEMINI_API_KEY"):
                    st.error("API Key required.")
                else:
                    total = len(df_upload)
                    results_batch = []
                    failed = 0
                    
                    target_path = os.path.join("trials", f"{selected_batch_trial}.md")
                    with open(target_path, "r") as f: batch_text = f.read()
                    
                    prog = st.progress(0)
                    status = st.empty()
                    
                    for idx, row in df_upload.iterrows():
                        try:
                            res = screen_patient(row.to_dict(), batch_text)
                            results_batch.append({
                                "patient_id": str(row.get("patient_id", "")),
                                "trial_name": selected_batch_trial,
                                "decision": res.get("decision", "ERROR"),
                                "reason": res.get("reason", ""),
                                "missing_info": res.get("missing_info", ""),
                                "inclusion_criteria_not_met": str(res.get("inclusion_criteria_not_met", [])),
                                "exclusion_criteria_met": str(res.get("exclusion_criteria_met", []))
                            })
                        except:
                            failed += 1
                        prog.progress((idx+1)/total)
                        status.write(f"Processing {idx+1}/{total}...")
                    
                    df_res = pd.DataFrame(results_batch)
                    
                    # Merge and Save
                    if os.path.exists(DATA_FILE):
                        old = pd.read_csv(DATA_FILE)
                        # Remove old for this trial
                        old = old[old['trial_name'] != selected_batch_trial]
                        combined = pd.concat([old, df_res], ignore_index=True)
                    else:
                        combined = df_res
                        
                    combined.to_csv(DATA_FILE, index=False)
                    st.success(f"Batch Complete! Screened {total} patients.")


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
            
            # MAGIE AUTOMATIQUE (Auto-Run)
            if st.form_submit_button("Save & Run Analysis 🚀"):
                safe = "".join([c for c in n_name if c.isalnum() or c in ('_','-')])
                if not safe:
                     st.error("Invalid Name")
                else:
                    # 1. Save
                    with open(os.path.join('trials', f"{safe}.md"), 'w') as f: f.write(n_text)
                    
                    # 2. Auto-Run logic
                    if os.path.exists(PATIENT_FILE):
                         df_pats = pd.read_csv(PATIENT_FILE)
                         st.info(f"Auto-screening {len(df_pats)} patients...")
                         res_auto = []
                         prog = st.progress(0)
                         for i, row in df_pats.iterrows():
                             try:
                                 r = screen_patient(row.to_dict(), n_text)
                                 res_auto.append({
                                     "patient_id": str(row.get("patient_id")),
                                     "trial_name": safe,
                                     "decision": r.get("decision"),
                                     "reason": r.get("reason"),
                                     "missing_info": r.get("missing_info"),
                                     "inclusion_criteria_not_met": str(r.get("inclusion_criteria_not_met", [])),
                                     "exclusion_criteria_met": str(r.get("exclusion_criteria_met", []))
                                 })
                             except: pass
                             prog.progress((i+1)/len(df_pats))
                         
                         df_new = pd.DataFrame(res_auto)
                         if os.path.exists(DATA_FILE):
                             old = pd.read_csv(DATA_FILE)
                             old = old[old['trial_name'] != safe] # Replace old run
                             cmbd = pd.concat([old, df_new], ignore_index=True)
                         else:
                             cmbd = df_new
                         cmbd.to_csv(DATA_FILE, index=False)
                         st.success("✅ Saved & Analyzed!")
                    else:
                         st.success("Saved (No patients found to analyze).")
                    
                    st.cache_data.clear()
                    st.rerun()
