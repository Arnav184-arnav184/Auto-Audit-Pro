import streamlit as st
import pdfplumber
import re
import pandas as pd

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Auto-Audit Pro", layout="wide", page_icon="🛡️")

# --- SESSION STATE (The Fix for Clearing Files) ---
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# --- SIDEBAR: CONFIGURATION ---
st.sidebar.header("⚙️ Audit Configuration")

# 1. Clear All Button (Now actually clears files!)
if st.sidebar.button("🔄 Reset / Clear All"):
    st.session_state.uploader_key += 1
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("Define your compliance thresholds below.")
audit_threshold = st.sidebar.number_input("Max Transaction Limit ($)", min_value=0, value=500, step=50)
vendor_blacklist = st.sidebar.text_area("Vendor Watchlist (One per line)", "Bad Wolf Corp\nBolton\nSuspicious LLC")

# 2. Risk Score Legend
st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ Risk Score Key")
st.sidebar.info("""
- **0-49 (Low):** Safe transaction.
- **50-99 (Medium):** Exceeds spending limit OR extraction failed.
- **100+ (High):** Blacklisted Vendor detected.
""")

st.title("🛡️ Auto-Audit Pro: Batch Compliance Engine")
st.markdown("""
**Enterprise Mode:** Upload multiple invoices to automatically audit them against business rules.
""")

# --- MAIN APP: BATCH UPLOAD ---
# We use the session_state key here so it resets when the button is clicked
uploaded_files = st.file_uploader(
    "Upload Invoices (PDF)", 
    type=["pdf"], 
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.uploader_key}"
)

if uploaded_files:
    # Initialize Master List for the CSV
    master_audit_log = []
    
    # Dashboard Metrics Placeholders
    total_processed = 0
    high_risk_count = 0
    total_value_audited = 0.0

    st.write("---")
    st.subheader(f"📂 Processing {len(uploaded_files)} Documents...")
    
    progress_bar = st.progress(0)

    # --- PROCESSING LOOP ---
    for i, file in enumerate(uploaded_files):
        extracted_text = ""
        error_msg = None
        
        # 3. ERROR HANDLING
        try:
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    extracted_text += page.extract_text() or ""
        except Exception as e:
            error_msg = f"Error reading PDF: {str(e)}"
            extracted_text = ""

        # 4. ANALYZE DATA
        dollar_pattern = r"(?:\$|USD)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)|([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)\s*USD"
        
        amounts_found = []
        if not error_msg:
            for match in re.findall(dollar_pattern, extracted_text):
                val_str = match[0] if match[0] else match[1]
                if val_str:
                    amounts_found.append(float(val_str.replace(",", "")))

        # Assumption: Largest number is total
        total_amount = max(amounts_found) if amounts_found else 0.0
        total_value_audited += total_amount
        
        # 5. DETERMINE RISK LEVEL
        risk_score = 0
        reasons = []
        
        # Logic: Errors
        if error_msg:
            risk_score += 25
            reasons.append(f"⚠️ {error_msg}")
        elif total_amount == 0:
            risk_score += 25
            reasons.append("Extraction Failed: No dollar amounts detected")

        # Rule 1: High Value Check (+50 pts)
        if total_amount > audit_threshold:
            risk_score += 50
            reasons.append(f"Amount (${total_amount:,.2f}) exceeds threshold")
        
        # Rule 2: Blacklist Check (+100 pts)
        blacklist_list = [v.strip() for v in vendor_blacklist.split('\n') if v.strip()]
        for bad_vendor in blacklist_list:
            pattern = r"\b" + re.escape(bad_vendor) + r"\b"
            if re.search(pattern, extracted_text, re.IGNORECASE):
                risk_score += 100
                reasons.append(f"Vendor '{bad_vendor}' found on Watchlist")

        # Determine Status Label
        if risk_score >= 100:
            status = "High Risk"
            high_risk_count += 1
        elif risk_score >= 50:
            status = "Medium Risk"
        elif risk_score > 0:
            status = "Medium Risk"
        else:
            status = "Approved"

        # Add to Master Log
        master_audit_log.append({
            "Filename": file.name,
            "Total Amount": total_amount,
            "Status": status,
            "Risk Score": risk_score,
            "Issues": "; ".join(reasons)
        })
        
        progress_bar.progress((i + 1) / len(uploaded_files))

    # --- DASHBOARD SUMMARY ---
    st.write("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("📄 Files Processed", len(uploaded_files))
    col2.metric("💰 Total Value Audited", f"${total_value_audited:,.2f}")
    col3.metric("🚩 High Risk Invoices", high_risk_count, delta_color="inverse")

    # --- DETAILED RESULTS TABLE ---
    st.subheader("📊 Detailed Audit Log")
    
    df = pd.DataFrame(master_audit_log)
    
    def highlight_risk(row):
        base_style = 'font-weight: bold; color: black; '
        if row['Status'] == 'High Risk':
            return [base_style + 'background-color: #ffcccc'] * len(row)
        elif row['Status'] == 'Medium Risk':
            return [base_style + 'background-color: #fff3cd'] * len(row)
        else:
            return [base_style + 'background-color: #d4edda'] * len(row)

    st.dataframe(df.style.apply(highlight_risk, axis=1))

    # --- MASTER CSV DOWNLOAD ---
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Download Master Audit Report (CSV)",
        csv,
        "master_audit_report.csv",
        "text/csv",
        key='download-csv'
    )

else:
    st.info("👆 Upload one or more PDF invoices to begin the batch audit.")
