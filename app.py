"""
Auto-Audit Pro: Batch Compliance Engine
---------------------------------------
A Streamlit application for automated batch auditing of PDF invoices against 
configurable business rules and vendor blacklists.

Usage:
    streamlit run app.py
"""

import streamlit as st
import pdfplumber
import re
import pandas as pd

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Auto-Audit Pro", 
    layout="wide", 
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

def extract_financials(text):
    """
    Parses text to find all monetary values using Regex.
    Returns a list of floats found in the document.
    """
    # Regex to capture various currency formats ($1,000.00, 500 USD, etc.)
    dollar_pattern = r"(?:\$|USD)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)|([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)\s*USD"
    
    amounts = []
    matches = re.findall(dollar_pattern, text)
    
    for match in matches:
        # Regex groups: match[0] is prefix ($), match[1] is suffix (USD)
        val_str = match[0] if match[0] else match[1]
        if val_str:
            # Clean string to float
            try:
                clean_val = float(val_str.replace(",", ""))
                amounts.append(clean_val)
            except ValueError:
                continue
                
    return amounts

def convert_df_to_csv(df):
    """
    Converts the audit log DataFrame into a CSV byte string for download.
    """
    return df.to_csv(index=False).encode('utf-8')

def highlight_risk_rows(row):
    """
    Pandas Styler function to color-code rows based on risk status.
    High Risk = Red, Medium = Yellow, Approved = Green.
    """
    base_style = 'font-weight: bold; color: black; '
    
    if row['Status'] == 'High Risk':
        return [base_style + 'background-color: #ffcccc'] * len(row)
    elif row['Status'] == 'Medium Risk':
        return [base_style + 'background-color: #fff3cd'] * len(row)
    else:
        return [base_style + 'background-color: #d4edda'] * len(row)

# ==========================================
# 3. SIDEBAR CONFIGURATION
# ==========================================
st.sidebar.header("⚙️ Audit Configuration")

# Reset Button
if st.sidebar.button("🔄 Reset / Clear All"):
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("Define your compliance thresholds below.")

# User Inputs
audit_threshold = st.sidebar.number_input(
    "Max Transaction Limit ($)", 
    min_value=0, 
    value=500, 
    step=50,
    help="Transactions above this amount trigger a Medium Risk alert."
)

vendor_blacklist_raw = st.sidebar.text_area(
    "Vendor Watchlist (One per line)", 
    "Bad Wolf Corp\nBolton\nSuspicious LLC",
    help="Any invoice containing these names will automatically be flagged as High Risk."
)

# Process Blacklist into a clean list
vendor_blacklist = [v.strip() for v in vendor_blacklist_raw.split('\n') if v.strip()]

# Legend
st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ Risk Score Key")
st.sidebar.info("""
- **0-49 (Low):** Safe transaction.
- **50-99 (Medium):** Exceeds spending limit OR extraction failed.
- **100+ (High):** Blacklisted Vendor detected.
""")

# ==========================================
# 4. MAIN APPLICATION INTERFACE
# ==========================================
st.title("🛡️ Auto-Audit Pro: Batch Compliance Engine")
st.markdown("""
**Enterprise Mode:** Upload multiple invoices to automatically audit them against business rules.
""")

# File Uploader
uploaded_files = st.file_uploader(
    "Upload Invoices (PDF)", 
    type=["pdf"], 
    accept_multiple_files=True,
    help="Drag and drop multiple PDF invoices here to start the batch audit."
)

# ==========================================
# 5. BATCH PROCESSING ENGINE
# ==========================================

if uploaded_files:
    # Initialize Master List for the CSV
    master_audit_log = []
    
    # Dashboard Metrics
    total_processed = 0
    high_risk_count = 0
    total_value_audited = 0.0

    st.write("---")
    st.subheader(f"📂 Processing {len(uploaded_files)} Documents...")
    
    progress_bar = st.progress(0)

    # --- Document Loop ---
    for i, file in enumerate(uploaded_files):
        extracted_text = ""
        error_msg = None
        
        # A. Text Extraction (PDFPlumber)
        try:
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text
        except Exception as e:
            error_msg = f"Error reading PDF: {str(e)}"
            extracted_text = ""

        # B. Financial Data Extraction
        amounts_found = []
        if not error_msg:
            amounts_found = extract_financials(extracted_text)

        # Heuristic: Largest dollar amount is likely the "Total"
        total_amount = max(amounts_found) if amounts_found else 0.0
        total_value_audited += total_amount
        
        # C. Risk Scoring Engine
        risk_score = 0
        reasons = []
        
        # 1. Error Checks (+25 pts)
        if error_msg:
            risk_score += 25
            reasons.append(f"⚠️ {error_msg}")
        elif total_amount == 0:
            risk_score += 25
            reasons.append("Extraction Failed: No dollar amounts detected")

        # 2. High Value Check (+50 pts)
        if total_amount > audit_threshold:
            risk_score += 50
            reasons.append(f"Amount (${total_amount:,.2f}) exceeds threshold")
        
        # 3. Blacklist Check (+100 pts)
        for bad_vendor in vendor_blacklist:
            # Word Boundary Check (\b) ensures we don't match substrings like "Bad" in "Baden"
            pattern = r"\b" + re.escape(bad_vendor) + r"\b"
            if re.search(pattern, extracted_text, re.IGNORECASE):
                risk_score += 100
                reasons.append(f"Vendor '{bad_vendor}' found on Watchlist")

        # D. Status Determination
        if risk_score >= 100:
            status = "High Risk"  # Must involve Blacklist
            high_risk_count += 1
        elif risk_score >= 50:
            status = "Medium Risk" # High Value or errors
        elif risk_score > 0:
            status = "Medium Risk" # Minor extraction issues
        else:
            status = "Approved"

        # E. Log Result
        master_audit_log.append({
            "Filename": file.name,
            "Total Amount": total_amount,
            "Status": status,
            "Risk Score": risk_score,
            "Issues": "; ".join(reasons)
        })
        
        # Update Progress Bar
        progress_bar.progress((i + 1) / len(uploaded_files))

    # ==========================================
    # 6. RESULTS DASHBOARD
    # ==========================================
    st.write("---")
    
    # KPI Cards
    col1, col2, col3 = st.columns(3)
    col1.metric("📄 Files Processed", len(uploaded_files))
    col2.metric("💰 Total Value Audited", f"${total_value_audited:,.2f}")
    col3.metric("🚩 High Risk Invoices", high_risk_count, delta_color="inverse")

    # Detailed Table
    st.subheader("📊 Detailed Audit Log")
    
    if master_audit_log:
        df = pd.DataFrame(master_audit_log)
        
        # Apply Conditional Formatting (Red/Yellow/Green)
        st.dataframe(df.style.apply(highlight_risk_rows, axis=1), use_container_width=True)

        # Download Button
        csv_data = convert_df_to_csv(df)
        st.download_button(
            label="📥 Download Master Audit Report (CSV)",
            data=csv_data,
            file_name="master_audit_report.csv",
            mime="text/csv",
            key='download-csv'
        )

else:
    # Empty State Message
    st.info("👆 Upload one or more PDF invoices to begin the batch audit.")
