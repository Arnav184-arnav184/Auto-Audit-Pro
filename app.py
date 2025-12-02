import streamlit as st
import pdfplumber
import re
import pandas as pd

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Auto-Audit Pro", layout="wide", page_icon="🛡️")

# --- SESSION STATE ---
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# --- SIDEBAR: CONFIGURATION ---
st.sidebar.header("⚙️ Audit Configuration")

if st.sidebar.button("🔄 Reset / Clear All"):
    st.session_state.uploader_key += 1
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("Define your compliance thresholds below.")
audit_threshold = st.sidebar.number_input("Max Transaction Limit ($)", min_value=0, value=500, step=50)
vendor_blacklist = st.sidebar.text_area("Vendor Watchlist (One per line)", "Bad Wolf Corp\nBolton\nSuspicious LLC")

st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ Risk Score Key")
st.sidebar.info("""
- **0-49 (Low):** Safe transaction.
- **50-99 (Medium):** High Value OR Extraction Uncertainty.
- **100+ (High):** Blacklisted Vendor detected.
""")

st.title("🛡️ Auto-Audit Pro: Batch Compliance Engine")
st.markdown("""
**Enterprise Mode:** Upload multiple invoices to automatically audit them against business rules.
""")

# --- MAIN APP ---
uploaded_files = st.file_uploader(
    "Upload Invoices (PDF)", 
    type=["pdf"], 
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.uploader_key}"
)

if uploaded_files:
    master_audit_log = []
    
    total_processed = 0
    high_risk_count = 0
    total_value_audited = 0.0

    st.write("---")
    st.subheader(f"📂 Processing {len(uploaded_files)} Documents...")
    
    progress_bar = st.progress(0)

    for i, file in enumerate(uploaded_files):
        extracted_text = ""
        error_msg = None
        
        # 1. ROBUST EXTRACTION
        try:
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    extracted_text += page.extract_text() or ""
        except Exception as e:
            error_msg = f"Error reading PDF: {str(e)}"

        # 2. INTELLIGENT TOTAL FINDER
        # Regex to find money formats
        dollar_pattern = r"(?:\$|USD)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)|([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)\s*USD"
        
        lines = extracted_text.split('\n')
        high_confidence_totals = [] 
        all_amounts = []           

        # Expanded Keyword List for Context
        total_keywords = ['total', 'amount due', 'amount payable', 'balance due', 'grand total', 'invoice total']

        if not error_msg:
            for line in lines:
                amounts_in_line = []
                for match in re.findall(dollar_pattern, line):
                    val_str = match[0] if match[0] else match[1]
                    if val_str:
                        amt = float(val_str.replace(",", ""))
                        amounts_in_line.append(amt)
                        all_amounts.append(amt)
                
                # CONTEXT CHECK: Check if line contains any of our keywords
                if amounts_in_line:
                    lower_line = line.lower()
                    if any(keyword in lower_line for keyword in total_keywords):
                        high_confidence_totals.extend(amounts_in_line)

        # Decision Logic
        final_total = 0.0
        logic_used = "Max Value (Fallback)"
        
        if high_confidence_totals:
            final_total = max(high_confidence_totals)
            logic_used = "Keyword Context Match"
        elif all_amounts:
            final_total = max(all_amounts)
        
        total_value_audited += final_total
        
        # 3. RISK ANALYSIS
        risk_score = 0
        reasons = []
        
        if error_msg:
            risk_score += 25
            reasons.append(f"⚠️ {error_msg}")
        elif final_total == 0:
            risk_score += 25
            reasons.append("Extraction Failed: No dollar amounts detected")
        
        # Rule 1: Threshold
        if final_total > audit_threshold:
            risk_score += 50
            reasons.append(f"Amount (${final_total:,.2f}) exceeds threshold")
        
        # Rule 2: VENDOR MATCHING (Fixed: Word Boundaries)
        blacklist_list = [v.strip() for v in vendor_blacklist.split('\n') if v.strip()]
        for bad_vendor in blacklist_list:
            # Use \b to ensure "Bolton" matches "Bolton" but NOT "Bolton Street"
            # re.escape ensures special characters in vendor names don't break regex
            pattern = r"\b" + re.escape(bad_vendor) + r"\b"
            if re.search(pattern, extracted_text, re.IGNORECASE):
                risk_score += 100
                reasons.append(f"Vendor '{bad_vendor}' detected")

        # Determine Status
        if risk_score >= 100:
            status = "High Risk"
            high_risk_count += 1
        elif risk_score >= 50:
            status = "Medium Risk"
        elif risk_score > 0:
            status = "Medium Risk"
        else:
            status = "Approved"

        master_audit_log.append({
            "Filename": file.name,
            "Detected Total": final_total,
            "Logic Used": logic_used,
            "Status": status,
            "Risk Score": risk_score,
            "Issues": "; ".join(reasons)
        })
        
        progress_bar.progress((i + 1) / len(uploaded_files))

    # --- DASHBOARD ---
    st.write("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("📄 Files Processed", len(uploaded_files))
    col2.metric("💰 Total Value Audited", f"${total_value_audited:,.2f}")
    col3.metric("🚩 High Risk Invoices", high_risk_count, delta_color="inverse")

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

    if not df.empty:
        st.dataframe(df.style.apply(highlight_risk, axis=1))
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Report (CSV)",
            csv,
            "audit_report.csv",
            "text/csv",
            key='download-csv'
        )
    else:
        st.warning("⚠️ No results to display. All files may have failed to process.")

else:
    st.info("👆 Upload one or more PDF invoices to begin the batch audit.")
