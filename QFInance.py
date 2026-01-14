# QRupees.py: Enhanced Streamlit dashboard for Nepse stocks with advanced security, features, and webpage-like styling.
# Focused on Nepal Stock Exchange (NEPSE) data using web scraping.
# Uses SQLite for secure storage, admin approval for registrations.
# Integrates provided logos and cover photo with your exact filenames.

import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import bcrypt
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Config
st.set_page_config(page_title="QRupees Dashboard", page_icon="📊", layout="wide")

# Inject CSS for webpage-like styling (if you have Style.css, otherwise skip or create an empty file)
if os.path.exists("Style.css"):
    with open("Style.css", "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# DB Adapter Class
class DBAdapter:
    def __init__(self):
        self.mode = "sqlite"
        self.conn = None
        self.c = None
        self.sheet_users = None
        self.sheet_regs = None
        
        # Try to connect to Google Sheets
        try:
            if "gcp_service_account" in st.secrets:
                # Load credentials from Streamlit secrets
                creds_dict = dict(st.secrets["gcp_service_account"])
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                client = gspread.authorize(creds)
                
                # Open sheets (Must create these in Google Sheets first)
                sheet_url = "QRupees_DB" # You can use title or key
                try:
                    spreadsheet = client.open("QRupees_DB")
                except:
                    # Create if not exists (requires more permissions usually, so assume it exists or fallback)
                    spreadsheet = client.create("QRupees_DB")
                    spreadsheet.share(creds_dict['client_email'], perm_type='user', role='writer')
                
                # Get or create worksheets
                try:
                    self.sheet_users = spreadsheet.worksheet("Users")
                except:
                    self.sheet_users = spreadsheet.add_worksheet(title="Users", rows=1000, cols=10)
                    self.sheet_users.append_row(["id", "email", "password", "is_admin"])
                    
                try:
                    self.sheet_regs = spreadsheet.worksheet("Registrations")
                except:
                    self.sheet_regs = spreadsheet.add_worksheet(title="Registrations", rows=1000, cols=30)
                    self.sheet_regs.append_row(["id", "user_id", "full_name", "phone", "address", "city", "state", "zip_code", 
                                                "country", "highest_degree", "field_of_study", "university", "graduation_year", 
                                                "certifications", "trading_duration", "trading_style", "markets", "specializations", 
                                                "current_occupation", "company", "years_of_experience", "linkedin", "about_yourself", 
                                                "goals", "references", "consent", "approved"])
                
                self.mode = "gsheets"
                st.toast("Connected to Google Sheets Database", icon="☁️")
        except Exception as e:
            # print(f"Google Sheets not configured: {e}") # Optional logging
            self.mode = "sqlite"
        
        # Fallback to SQLite
        if self.mode == "sqlite":
            self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            self.c = self.conn.cursor()
            self.create_sqlite_tables()
            st.toast("Using Local SQLite Database", icon="📂")

    def create_sqlite_tables(self):
        self.c.execute('''CREATE TABLE IF NOT EXISTS users 
             (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password BLOB, is_admin INTEGER DEFAULT 0)''')
        self.c.execute('''CREATE TABLE IF NOT EXISTS registrations 
             (id INTEGER PRIMARY KEY, user_id INTEGER, full_name TEXT, phone TEXT, address TEXT, city TEXT, 
              state TEXT, zip_code TEXT, country TEXT, highest_degree TEXT, field_of_study TEXT, university TEXT, 
              graduation_year INTEGER, certifications TEXT, trading_duration TEXT, trading_style TEXT, 
              markets TEXT, specializations TEXT, current_occupation TEXT, company TEXT, years_of_experience TEXT, 
              linkedin TEXT, about_yourself TEXT, goals TEXT, "references" TEXT, consent INTEGER, approved INTEGER DEFAULT 0)''')
        self.conn.commit()
    
    def get_user(self, email):
        if self.mode == "gsheets":
            try:
                records = self.sheet_users.get_all_records()
                for i, r in enumerate(records):
                    if r['email'] == email:
                        # Return tuple to match SQLite format: (id, password, is_admin)
                        # Password in sheets should be stored as string, we might need to encode back to bytes for bcrypt
                        return (r['id'], r['password'].encode('latin-1'), r['is_admin']) 
                return None
            except:
                return None
        else:
            self.c.execute("SELECT id, password, is_admin FROM users WHERE email=?", (email,))
            return self.c.fetchone()

    def create_user(self, email, password_hash, is_admin=0):
        if self.mode == "gsheets":
            # Generate simple integer ID (max id + 1)
            records = self.sheet_users.get_all_records()
            new_id = len(records) + 1
            # Store password hash as latin-1 string
            self.sheet_users.append_row([new_id, email, password_hash.decode('latin-1'), is_admin])
            return new_id
        else:
            self.c.execute("INSERT OR IGNORE INTO users (email, password, is_admin) VALUES (?, ?, ?)", (email, password_hash, is_admin))
            self.conn.commit()
            return self.c.lastrowid
            
    def get_registration(self, user_id):
        if self.mode == "gsheets":
            records = self.sheet_regs.get_all_records()
            for r in records:
                if r['user_id'] == user_id:
                    # Return approved status. SQLite returns tuple, let's return object that behaves similarly or just the field
                    # The calling code expects: reg[0] == 1 (approved)
                    return (r['approved'],) 
            return None
        else:
            self.c.execute("SELECT approved FROM registrations WHERE user_id=?", (user_id,))
            return self.c.fetchone()
            
    def create_registration(self, data):
        if self.mode == "gsheets":
            # Add an ID column at start
            records = self.sheet_regs.get_all_records()
            new_id = len(records) + 1
            row = [new_id] + list(data)
            self.sheet_regs.append_row(row)
        else:
            self.c.execute("""INSERT INTO registrations (user_id, full_name, phone, address, city, state, zip_code, country, 
                              highest_degree, field_of_study, university, graduation_year, certifications, trading_duration, 
                              trading_style, markets, specializations, current_occupation, company, years_of_experience, 
                              linkedin, about_yourself, goals, "references", consent, approved) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""", data)
            self.conn.commit()

    def get_pending_registrations(self):
        if self.mode == "gsheets":
            records = self.sheet_regs.get_all_records()
            pending = []
            users = self.sheet_users.get_all_records()
            user_map = {u['id']: u['email'] for u in users}
            
            for r in records:
                if str(r['approved']) == '0':
                    # Need id, email, full_name, approved
                    email = user_map.get(r['user_id'], "Unknown")
                    pending.append((r['id'], email, r['full_name'], r['approved']))
            return pending
        else:
            self.c.execute("SELECT r.id, u.email, r.full_name, r.approved FROM registrations r JOIN users u ON r.user_id = u.id WHERE r.approved = 0")
            return self.c.fetchall()
            
    def approve_registration(self, reg_id):
        if self.mode == "gsheets":
            # Find row index. get_all_records is 0-indexed data headers.
            # gspread rows are 1-indexed. Header is row 1. First data is row 2.
            # Finding the row by ID is inefficient but works for small databases.
            cell = self.sheet_regs.find(str(reg_id), in_column=1) 
            if cell:
                # Approve column is last, let's find it's index or hardcode
                # approved is column 27 based on create_registration list
                self.sheet_regs.update_cell(cell.row, 27, 1)
        else:
            self.c.execute("UPDATE registrations SET approved=1 WHERE id=?", (reg_id,))
            self.conn.commit()

# Database setup
DB_FILE = "qrupees.db"
db = DBAdapter()

# Hardcode admin (for demo; change password in prod)
admin_email = "admin@qrupees.com"
admin_pass = bcrypt.hashpw("adminpass".encode(), bcrypt.gensalt())
# Only create if doesn't exist (handled inside create_user check ideally, but for now simple check)
if db.mode == "sqlite": # Simple optimization
    db.c.execute("SELECT * FROM users WHERE email=?", (admin_email,))
    if not db.c.fetchone():
        db.create_user(admin_email, admin_pass, 1)
else:
    if not db.get_user(admin_email):
        db.create_user(admin_email, admin_pass, 1)

# Helper functions
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(hashed, password):
    return bcrypt.checkpw(password.encode(), hashed)

def get_nepse_companies():
    url = "https://www.nepalstock.com/company"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        companies = []
        if table:
            for row in table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) > 1:
                    symbol = cols[2].text.strip()
                    name = cols[1].text.strip()
                    link = row.find('a')['href'] if row.find('a') else None
                    stock_id = link.split('/')[-1] if link else None
                    companies.append({'symbol': symbol, 'name': name, 'id': stock_id})
        return pd.DataFrame(companies)
    except Exception as e:
        st.error(f"Error fetching companies: {e}")
        return pd.DataFrame()

# Helper: Load Data (Cached)
@st.cache_data(ttl=60, show_spinner=False)
def get_today_prices():
    url = "https://www.nepalstock.com/today-price"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = requests.get(url, verify=False, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.content
        df = pd.read_html(html)[0]
        # Basic cleaning
        df = df.dropna(how='all')
        return df
    except Exception as e:
        # st.error(f"Data Fetch Error: {e}") # Suppress for cleaner UI, handle in caller
        return pd.DataFrame() # Return empty on failure

def get_historical_data(stock_id, start_date, end_date):
    url = f"https://www.nepalstock.com/company/transaction-history?stockId={stock_id}&startDate={start_date}&endDate={end_date}&_limit=5000"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        data = response.json()
        if 'hydra:member' in data:
            df = pd.DataFrame(data['hydra:member'])
            if not df.empty:
                df['businessDate'] = pd.to_datetime(df['businessDate'])
            return df
    except Exception as e:
        st.error(f"Error fetching historical data: {e}")
    return pd.DataFrame()

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

# Display Cover Photo (only on other pages if needed, but Home has it)
if 'page' in locals() and page != "Home":
    st.image("Cover Photo.png", use_container_width=True)

# Title & Header
st.title("📊 QRupees: Quant Finance in the Himalayas")
st.header("Empowering Nepse Traders with Advanced Analytics")

# Sidebar Navigation
with st.sidebar:
    st.header("Navigation")
    if st.session_state.authenticated:
        pages = ["Dashboard", "Stock Analysis", "Portfolio", "Community Insights", "Settings", "Logout"]
        if st.session_state.is_admin:
            pages.insert(4, "Admin Approvals")
        page = st.selectbox("Select Page", pages)
    else:
        # Public Pages
        page = st.selectbox("Select Page", [
            "Home", 
            "Features", 
            "Live Data", 
            "Pricing", 
            "About", 
            "Regulatory & Trust", 
            "Login", 
            "Trader Registration"
        ])
        
    st.divider()
    # Storage Status Indicator
    if db.mode == "gsheets":
        st.caption("🟢 Storage: Cloud (Persistent)")
    else:
        st.caption("🟡 Storage: Local (Temporary)")
        st.caption("Data may reset on restart.")

# Dynamic Footer Function
def render_footer():
    st.divider()
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.image("QRupees footer.png", width=100) if os.path.exists("QRupees footer.png") else None 
        st.markdown("<div style='text-align: center; color: grey;'><b>QRupees — Building Nepal’s Quantitative Market Infrastructure</b></div>", unsafe_allow_html=True)
        st.caption("© 2026 QRupees. Powered by xAI. Focused on Nepse Excellence.")
    
    # Facebook Link in center or right
    st.markdown(
        """<div style='text-align: center;'><a href="https://www.facebook.com/profile.php?id=61586221963929" target="_blank" style="text-decoration: none; color: #1877F2; font-size: 24px;"><br>🔵 Follow us on Facebook</a></div>""", 
        unsafe_allow_html=True
    )  

# Render Footer on all pages
render_footer()

# Home Page (Landing)
if page == "Home":
    st.image("Cover Photo.png", use_container_width=True)
    
    st.markdown("""
    <div style='text-align: center; padding: 20px 0;'>
        <h1>QRupees</h1>
        <h3><b>Nepal’s Quantitative Market Intelligence Platform</b></h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("""
    **Turn raw NEPSE data into clear, mathematical trading insights.**  
    *Built for Nepal. Designed for serious traders.*
    """)
    
    col_cta1, col_cta2 = st.columns(2)
    with col_cta1:
        if st.button("🚀 Explore Dashboard", use_container_width=True):
            st.session_state.page_selection = "Login"
            st.warning("Please login to access the Dashboard.")
    with col_cta2:
        if st.button("📊 View Live NEPSE Data", use_container_width=True):
            st.toast("Redirecting to Live Data...")
            # Ideally switch page, but showing info for now as simple nav is sidebar based
            st.info("Select 'Live Data' from the sidebar to view.")

    st.divider()

    # Why QRupees Section
    st.subheader("Why QRupees?")
    st.write("NEPSE is a unique market—defined by sector cycles, liquidity gaps, regulatory constraints, and sharp volatility.")
    st.write("**QRupees is engineered specifically for NEPSE, not adapted from foreign markets.**")
    
    c1, c2, c3 = st.columns(3)
    c1.success("✅ **Built exclusively for Nepal**")
    c2.success("✅ **Data-driven, not rumor-driven**")
    c3.success("✅ **Precision over noise**")

# Features Page
elif page == "Features":
    st.title("Platform Features")
    st.image("Cover Photo.png", use_container_width=True)
    
    st.subheader("1. Fundamental Analysis Engine")
    st.caption("Evaluate companies beyond price movements.")
    st.markdown("""
    *   **Company Health Scoring**: Using P/E, ROE, Debt-to-Equity to assess value.
    *   **Verified Trader Registry**: Research profiles & documented investment theses.
    *   **Live Sectoral Analysis**: Real-time capital-flow tracking across NEPSE sectors.
    """)
    
    st.divider()
    
    st.subheader("2. Technical Analysis Terminal")
    st.caption("A modern trading terminal for active NEPSE traders.")
    st.markdown("""
    *   **Advanced Quantitative Charting**: Deep price action history.
    *   **Algorithmic Watchlists**: Real-time updates on key stocks.
    *   **Secure Environment**: Encrypted strategy planning.
    """)

# Live Data Page
elif page == "Live Data":
    st.title("Live NEPSE Market Data")
    st.info("**QRupees operates a NEPSE-specific data engine built for speed and accuracy.**")
    
    # Refresh Button
    if st.button("🔄 Refresh Feed"):
        get_today_prices.clear()
        st.rerun()
    
    try:
        with st.spinner("Connecting to NEPSE Feed..."):
            df = get_today_prices()
            
        if not df.empty:
            # Flexible Column Handling for Metrics
            cols = df.columns.tolist()
            # Try to find Turnover/Volume columns by keyword
            turnover_col = next((c for c in cols if "amount" in c.lower() or "turnover" in c.lower()), None)
            vol_col = next((c for c in cols if "quantity" in c.lower() or "volume" in c.lower() or "shares" in c.lower()), None)
            
            # Metrics Dashboard
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Market Status", "🟢 Open" if len(df) > 10 else "🔴 Closed")
            m2.metric("Listed Scrips", len(df))
            
            if turnover_col:
                # Clean turnover data (remove commas, convert to float)
                try:
                    total_turnover = df[turnover_col].astype(str).str.replace(',', '').astype(float).sum()
                    m3.metric("Total Turnover", f"Rs. {total_turnover:,.0f}")
                except:
                    m3.metric("Total Turnover", "N/A")
            
            if vol_col:
                try:
                    total_vol = df[vol_col].astype(str).str.replace(',', '').astype(float).sum()
                    m4.metric("Total Volume", f"{total_vol:,.0f} Shares")
                except:
                    m4.metric("Total Volume", "N/A")

            st.markdown("### 📊 Market Movers")
            # Show top 5 by turnover if possible
            if turnover_col:
                top_active = df.sort_values(by=turnover_col, ascending=False).head(5)
                st.caption("Top Stocks by Turnover")
                st.dataframe(top_active, use_container_width=True, hide_index=True)
            else:
                st.dataframe(df.head(20), use_container_width=True)
                
        else:
            st.warning("Market data currently unavailable. The market might be closed.")
            st.button("Retry Connection", on_click=lambda: get_today_prices.clear())
            
    except Exception as e:
        st.error(f"Live feed disconnected: {e}")
        st.button("Retry Connection", on_click=lambda: get_today_prices.clear())

# Pricing Page
elif page == "Pricing":
    st.title("Pricing Plans")
    st.write("Choose the right level of intelligence for your trading journey.")
    
    p_col1, p_col2 = st.columns(2)
    p_col3, p_col4 = st.columns(2)
    
    with p_col1:
        st.markdown("### 🟢 Free — Market Viewer")
        st.caption("For students and beginners.")
        st.markdown("- Limited live data\n- Basic charts\n- Educational indicators")
        st.button("Current Plan", disabled=True)
        
    with p_col2:
        st.markdown("### 🔵 Pro — Active Trader")
        st.caption("For serious retail traders.")
        st.markdown("- Real-time NEPSE data\n- Advanced indicators\n- Algorithmic watchlists\n- Sector dashboards")
        st.markdown("**NPR 999–1,499 / month**")
        st.button("Upgrade to Pro")

    st.divider()

    with p_col3:
        st.markdown("### 🟣 Quant — Research")
        st.caption("For analysts and high-commitment traders.")
        st.markdown("- Tick replay & backtesting\n- NEPSE-optimized indicators\n- Strategy analytics\n- Data export & API access")
        st.markdown("**NPR 3,000–5,000 / month**")
        st.button("Contact Sales", key="quant")

    with p_col4:
        st.markdown("### ⚫ Institutional")
        st.caption("For funds and research firms.")
        st.markdown("- Dedicated data nodes\n- Custom analytics\n- Audit-ready reports\n- Priority support")
        st.markdown("**Custom Pricing**")
        st.button("Contact Sales", key="inst")

# About Page
elif page == "About":
    st.title("What is QRupees?")
    st.image("Cover Photo.png", use_container_width=True)
    st.markdown("""
    **QRupees is not a trading app.**
    
    It is a **quantitative market intelligence platform** built to bring discipline, transparency, and analytical depth to Nepal’s capital markets.

    Our mission is to empower traders and analysts with professional-grade tools—while remaining regulation-aware and ethically designed.
    """)

# Regulatory Page
elif page == "Regulatory & Trust":
    st.title("Regulatory & Trust")
    st.warning("Regulation-First Design")
    
    st.markdown("""
    QRupees is designed as:

    *   ✅ **Market analytics & decision-support software**
    *   ✅ **Read-only NEPSE data platform**
    *   ✅ **Educational and research-focused**
    *   ❌ **No auto-trading or execution**

    > *QRupees does **not** provide buy/sell recommendations or guarantee profits.*
    """)

# Logout
if page == "Logout":
    st.session_state.authenticated = False
    st.session_state.user_email = None
    st.session_state.is_admin = False
    st.success("Logged out successfully.")
    st.rerun()

# Login Page
if page == "Login" and not st.session_state.authenticated:
    st.subheader("Login to Access Features")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = db.get_user(email)
        if user and check_password(user[1], password):
            # user[0] is id, user[2] is is_admin
            reg = db.get_registration(user[0])
            # Check for admin (user[2]) or approved registration (reg[0])
            is_admin_flag = str(user[2]) == '1' # Handle int or string from sheets
            is_approved_flag = reg and str(reg[0]) == '1'
            
            if is_approved_flag or is_admin_flag: 
                st.session_state.authenticated = True
                st.session_state.user_email = email
                st.session_state.is_admin = is_admin_flag
                st.success(f"Welcome back, {email}!")
                st.rerun()
            else:
                st.error("Your registration is pending approval.")
        else:
            st.error("Invalid email or password.")

# Trader Registration Page
elif page == "Trader Registration":
    st.subheader("Nepse Trader Registration")
    st.write("Join our Himalayan quant community. Focus on Nepse stocks.")
    with st.form(key="registration_form"):
        # Personal Information
        st.markdown("### Personal Information")
        full_name = st.text_input("Full Name *", placeholder="Enter your full name")
        email = st.text_input("Email Address *", placeholder="your.email@example.com")
        password = st.text_input("Set Password *", type="password")
        phone = st.text_input("Phone Number *", placeholder="+1 (555) 000-0000")
        address = st.text_input("Address *", placeholder="Street address")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            city = st.text_input("City *", placeholder="City")
        with col2:
            state = st.text_input("State/Province", placeholder="State or Province")
        with col3:
            zip_code = st.text_input("ZIP/Postal Code", placeholder="ZIP or Postal Code")
        with col4:
            country = st.text_input("Country *", placeholder="Country")

        # Education & Qualifications
        st.markdown("### Education & Qualifications")
        highest_degree = st.selectbox("Highest Degree *", options=["Select your degree", "High School", "Associate Degree", "Bachelor's Degree", "Master's Degree", "Doctorate (Ph.D.)", "Professional Degree", "Other"])
        field_of_study = st.text_input("Field of Study", placeholder="e.g., Finance, Economics, Business")
        university = st.text_input("University/Institution", placeholder="Name of your institution")
        graduation_year = st.number_input("Graduation Year", min_value=1950, max_value=2030, value=None, placeholder="e.g., 2020")
        certifications = st.text_input("Professional Certifications", placeholder="e.g., CFA, CPA, CFP, Series 7 (comma separated)")

        # Trading Experience
        st.markdown("### Trading Experience")
        trading_duration = st.selectbox("How long have you been trading? *", options=["Select duration", "Less than 1 year", "1-2 years", "2-5 years", "5-10 years", "10+ years"])
        trading_style = st.selectbox("Primary Trading Style", options=["Select style", "Day Trading", "Swing Trading", "Position Trading", "Scalping", "Long-term Investing"])
        markets = st.multiselect("Markets You Trade In", options=["Stocks/Equities", "Options", "Futures", "Forex", "Cryptocurrency", "Commodities"])
        specializations = st.text_input("Areas of Specialization", placeholder="e.g., Technical Analysis, Fundamental Analysis, Algorithmic Trading")

        # Professional Background
        st.markdown("### Professional Background")
        current_occupation = st.text_input("Current Occupation", placeholder="Your current job title")
        company = st.text_input("Company/Firm", placeholder="Your current employer")
        years_of_experience = st.selectbox("Total Years of Professional Experience", options=["Select experience", "0-2 years", "2-5 years", "5-10 years", "10-15 years", "15+ years"])
        linkedin = st.text_input("LinkedIn Profile", placeholder="https://linkedin.com/in/yourprofile")

        # About Yourself
        st.markdown("### Tell Us About Yourself")
        about_yourself = st.text_area("About Yourself (150 words) *", placeholder="Share your trading journey, investment philosophy, key achievements...", max_chars=1500, height=200)
        st.caption(f"Word count: {len(about_yourself.split()) if about_yourself else 0} / 150")

        # Additional Information
        st.markdown("### Additional Information")
        goals = st.text_area("What are your goals in joining our community?", placeholder="Share what you hope to achieve...", height=100)
        references = st.text_area("Professional References", placeholder="Include name, title, company, and contact information (optional)", height=100)

        # Consent
        consent = st.checkbox("I confirm that all information provided is accurate and complete. I understand that this information will be used for professional networking and verification purposes. *")

        # Validation
        valid_email = re.match(r"[^@]+@[^@]+\.[^@]+", email)
        valid_phone = len(phone) >= 10 and phone.isdigit()
        
        if st.form_submit_button("Submit Registration"):
            if not full_name or not email or not phone:
                st.error("Please fill in all required fields (Name, Email, Phone).")
            elif not valid_email:
                st.error("Invalid Email format.")
            elif not valid_phone:
                st.error("Invalid Phone number (must be at least 10 digits).")
            elif not consent:
                st.error("You must agree to the terms.")
            elif len(about_yourself.split()) > 150:
                st.error("About Yourself section exceeds 150 words.")
            else:
                if db.get_user(email):
                    st.error("Email already registered.")
                else:
                    hashed = hash_password(password)
                    # Create user
                    user_id = db.create_user(email, hashed)
                    
                    markets_str = ', '.join(markets) if markets else ''
                    grad_year = int(graduation_year) if graduation_year else None
                    
                    # Create registration
                    db.create_registration((user_id, full_name, phone, address, city, state, zip_code, country, highest_degree, field_of_study, 
                               university, grad_year, certifications, trading_duration, trading_style, markets_str, specializations, 
                               current_occupation, company, years_of_experience, linkedin, about_yourself, goals, references, 1 if consent else 0))
                               
                    st.success("Registration submitted! Awaiting admin approval.")

# Protected Pages
if st.session_state.authenticated:
    if page == "Dashboard":
        st.subheader("Nepse Market Overview")
        prices = get_today_prices()
        if not prices.empty:
            st.dataframe(prices)
            # Try to find the difference column (could be 'Difference Rs.' or 'Change')
            diff_col = None
            name_col = None
            for col in ['Difference Rs.', 'Change', 'Point Change']:
                if col in prices.columns:
                    diff_col = col
                    break
            for col in ['Traded Companies', 'Symbol', 'Company']:
                if col in prices.columns:
                    name_col = col
                    break
            
            if diff_col and name_col:
                # Convert to numeric, handling any non-numeric values
                prices[diff_col] = pd.to_numeric(prices[diff_col], errors='coerce')
                fig = px.bar(prices.sort_values(diff_col, ascending=False).head(10), 
                             x=name_col, y=diff_col, title="Top Gainers")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Chart not available. Available columns: " + ", ".join(prices.columns))
        else:
            st.warning("Unable to fetch today's prices. Check your internet or try later.")

    elif page == "Stock Analysis":
        st.subheader("Nepse Stock Analysis")
        companies = get_nepse_companies()
        symbol = st.selectbox("Select Symbol", companies['symbol'].tolist())
        if symbol:
            stock = companies[companies['symbol'] == symbol].iloc[0]
            stock_id = stock['id']
            end_date = datetime.today().strftime('%Y-%m-%d')
            start_date = (datetime.today() - timedelta(days=365)).strftime('%Y-%m-%d')
            hist = get_historical_data(stock_id, start_date, end_date)
            if not hist.empty:
                st.dataframe(hist)
                fig = px.line(hist, x='businessDate', y='closingPrice', title=f"{symbol} Price Trend")
                st.plotly_chart(fig)
            else:
                st.warning("No historical data available.")

    elif page == "Portfolio":
        st.subheader("Nepse Portfolio Simulator")
        holdings = st.text_area("Enter Holdings (symbol:shares, one per line)", "ADBL:100\nNABIL:50")
        if st.button("Simulate"):
            portfolio = {line.split(':')[0].strip(): int(line.split(':')[1]) for line in holdings.split('\n') if line and ':' in line}
            prices = get_today_prices()
            if not prices.empty:
                values = []
                
                # Determine the correct column names
                symbol_col = None
                price_col = None
                
                for col in ['Symbol', 'Stock Symbol', 'Traded Companies', 'Company']:
                    if col in prices.columns:
                        symbol_col = col
                        break
                        
                for col in ['LTP', 'Closing Price', 'Close Price', 'Last Traded Price']:
                    if col in prices.columns:
                        price_col = col
                        break
                
                if not symbol_col or not price_col:
                    st.error(f"Cannot find required columns. Available: {', '.join(prices.columns)}")
                else:
                    for sym, shares in portfolio.items():
                        matching_rows = prices[prices[symbol_col].str.upper() == sym.upper()]
                        
                        if not matching_rows.empty:
                            price = pd.to_numeric(matching_rows[price_col].iloc[0], errors='coerce')
                            if pd.notna(price):
                                values.append({'Symbol': sym, 'Shares': shares, 'Value': price * shares, 'Price': price})
                    
                    if values:
                        df = pd.DataFrame(values)
                        st.success(f"Portfolio loaded with {len(values)} stocks")
                        st.dataframe(df)
                        fig = px.pie(df, values='Value', names='Symbol', title="Portfolio Allocation")
                        st.plotly_chart(fig)
                    else:
                        st.warning("No valid holdings found in Nepse data. Make sure symbols match exactly.")
            else:
                st.warning("Unable to fetch price data.")

    elif page == "Community Insights":
        st.subheader("Nepse Community Trends")
        # Placeholder trends; expand with real data if needed
        trends = {"Banks": 50, "Hydro": 30, "Microfinance": 20, "Insurance": 15, "Others": 10}
        fig = px.bar(x=list(trends.keys()), y=list(trends.values()), title="Popular Sectors")
        st.plotly_chart(fig)

    elif page == "Admin Approvals" and st.session_state.is_admin:
        st.subheader("Approve Registrations")
        pending = db.get_pending_registrations()
        
        if not pending:
            st.info("No pending registrations.")
            
        for reg in pending:
            # reg is (id, email, full_name, approved)
            st.write(f"Email: {reg[1]}, Name: {reg[2]}")
            if st.button("Approve", key=reg[0]):
                db.approve_registration(reg[0])
                st.success("Approved!")
                st.rerun()

    elif page == "Settings":
        st.subheader("App Settings")
        theme = st.selectbox("Theme", ["Dark", "Light"])
        # In prod, apply theme via session state or CSS

# Footer
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("Q logo.png", width=200)
    st.markdown("<p style='text-align: center;'>© 2026 QRupees. Focused on Nepse Excellence.</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'><a href='https://www.facebook.com/profile.php?id=61586221963929' target='_blank'>📘 Follow us on Facebook</a></p>", unsafe_allow_html=True)