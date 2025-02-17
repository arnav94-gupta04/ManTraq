import streamlit as st
import sqlite3
import datetime
import io
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
from streamlit_js_eval import streamlit_js_eval


# =============================================================================
# DATABASE FUNCTIONS & INITIALIZATION
# =============================================================================

def get_db_connection():
    # Use check_same_thread=False for Streamlit’s multi-threaded environment.
    conn = sqlite3.connect("company.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row  # so we can access columns by name
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Create Employees table
    c.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        employee_id TEXT PRIMARY KEY,
        full_name TEXT,
        contact_number TEXT,
        email TEXT,
        aadhar TEXT,
        dob TEXT,
        address TEXT,
        photo BLOB,
        aadhar_photo BLOB,
        signature_photo BLOB,
        role TEXT,
        password TEXT,
        assigned_client_id TEXT,
        rate_per_hour REAL
    )
    ''')
    # Create Attendance table
    c.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT,
        check_in_time TEXT,
        check_in_location TEXT,
        check_in_selfie BLOB,
        check_out_time TEXT,
        check_out_location TEXT,
        working_hours REAL
    )
    ''')
    # Create Clients table
    c.execute('''
    CREATE TABLE IF NOT EXISTS clients (
        client_id TEXT PRIMARY KEY,
        org_name TEXT,
        description TEXT,
        requirements TEXT,
        company_contact TEXT,
        company_email TEXT,
        person_in_charge_name TEXT,
        person_in_charge_phone TEXT,
        person_in_charge_email TEXT,
        company_type TEXT,
        total_bill REAL,
        outstanding REAL
    )
    ''')
    # Create Installments table
    c.execute('''
    CREATE TABLE IF NOT EXISTS installments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id TEXT,
        amount_paid REAL,
        timestamp TEXT
    )
    ''')
    conn.commit()
    conn.close()

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_geolocation():
    location = streamlit_js_eval(js_expressions="navigator.geolocation.getCurrentPosition((pos) => pos.coords.latitude + ',' + pos.coords.longitude)", key="geo")
    return location


# =============================================================================
# EMPLOYEE MODULE
# =============================================================================

def register_employee(employee):
    """Insert a new employee record into the database."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
    INSERT INTO employees (employee_id, full_name, contact_number, email, aadhar, dob, address, photo, aadhar_photo, signature_photo, role, password, assigned_client_id, rate_per_hour)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        employee['employee_id'],
        employee['full_name'],
        employee['contact_number'],
        employee['email'],
        employee['aadhar'],
        employee['dob'],
        employee['address'],
        employee['photo'],
        employee['aadhar_photo'],
        employee['signature_photo'],
        employee['role'],
        employee['password'],
        employee.get('assigned_client_id', None),
        employee.get('rate_per_hour', None)
    ))
    conn.commit()
    conn.close()

def login_employee(employee_id, password):
    """Check credentials and return the employee record if valid."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM employees WHERE employee_id = ? AND password = ?', (employee_id, password))
    employee = c.fetchone()
    conn.close()
    return employee

def get_employee_profile(employee_id):
    """Return the employee record and all attendance records."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM employees WHERE employee_id = ?', (employee_id,))
    employee = c.fetchone()
    c.execute('SELECT * FROM attendance WHERE employee_id = ?', (employee_id,))
    attendance_records = c.fetchall()
    conn.close()
    return employee, attendance_records

# =============================================================================
# ATTENDANCE MODULE
# =============================================================================

def check_in_attendance(employee_id, selfie_bytes):
    """Insert a new check-in record with timestamp, location, and selfie."""
    conn = get_db_connection()
    c = conn.cursor()

    check_in_time = datetime.datetime.now().isoformat()
    check_in_location = get_geolocation()

    c.execute('''
        INSERT INTO attendance (employee_id, check_in_time, check_in_location, check_in_selfie)
        VALUES (?, ?, ?, ?)
    ''', (employee_id, check_in_time, check_in_location, selfie_bytes))

    conn.commit()
    conn.close()

    return check_in_time

def check_out_attendance(employee_id):
    """Update the latest check-in record with checkout details and calculate working hours."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
    SELECT * FROM attendance 
    WHERE employee_id = ? AND check_out_time IS NULL 
    ORDER BY check_in_time DESC LIMIT 1
    ''', (employee_id,))
    record = c.fetchone()
    if record is None:
        conn.close()
        return None, "No check-in record found. Please check in first."
    check_in_time = datetime.datetime.fromisoformat(record['check_in_time'])
    check_out_time = datetime.datetime.now()
    check_out_location = get_geolocation()
    working_hours = (check_out_time - check_in_time).total_seconds() / 3600.0
    c.execute('''
    UPDATE attendance
    SET check_out_time = ?, check_out_location = ?, working_hours = ?
    WHERE id = ?
    ''', (check_out_time.isoformat(), check_out_location, working_hours, record['id']))
    conn.commit()
    conn.close()
    return working_hours, check_out_time.isoformat()

# =============================================================================
# SALARY MODULE
# =============================================================================

def calculate_salary(employee_id):
    """
    Calculate salary components for the current month.
    - base_salary = rate_per_hour * total_work_hours
    - retirement_benefits1 = 12% of base_salary
    - retirement_benefits2 = 13% of base_salary
    - insurance1 = 5% of base_salary
    - insurance2 = 5% of base_salary
    - actual_salary = base_salary - (retirement_benefits1 + insurance1)
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT rate_per_hour FROM employees WHERE employee_id = ?', (employee_id,))
    result = c.fetchone()
    if result is None or result['rate_per_hour'] is None:
        conn.close()
        return None
    rate_per_hour = result['rate_per_hour']
    now = datetime.datetime.now()
    start_month = datetime.datetime(now.year, now.month, 1).isoformat()
    c.execute('''
    SELECT SUM(working_hours) as total_hours FROM attendance
    WHERE employee_id = ? AND check_out_time IS NOT NULL AND check_in_time >= ?
    ''', (employee_id, start_month))
    result = c.fetchone()
    total_hours = result['total_hours'] if result['total_hours'] is not None else 0
    base_salary = rate_per_hour * total_hours
    retirement_benefits1 = 0.12 * base_salary
    retirement_benefits2 = 0.13 * base_salary
    insurance1 = 0.05 * base_salary
    insurance2 = 0.05 * base_salary
    actual_salary = base_salary - (retirement_benefits1 + insurance1)
    conn.close()
    return {
        'total_hours': total_hours,
        'base_salary': base_salary,
        'retirement_benefits1': retirement_benefits1,
        'retirement_benefits2': retirement_benefits2,
        'insurance1': insurance1,
        'insurance2': insurance2,
        'actual_salary': actual_salary
    }

# =============================================================================
# CLIENT MODULE
# =============================================================================

def register_client(client):
    """Insert a new client record into the database.
       Note: The outstanding amount is initialized equal to total_bill."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
    INSERT INTO clients (client_id, org_name, description, requirements, company_contact, company_email, person_in_charge_name, person_in_charge_phone, person_in_charge_email, company_type, total_bill, outstanding)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        client['client_id'],
        client['org_name'],
        client['description'],
        client['requirements'],
        client['company_contact'],
        client['company_email'],
        client['person_in_charge_name'],
        client['person_in_charge_phone'],
        client['person_in_charge_email'],
        client['company_type'],
        client['total_bill'],
        client['total_bill']  # outstanding initially equal to total bill
    ))
    conn.commit()
    conn.close()

def assign_employee_to_client(employee_id, client_id, rate_per_hour):
    """
    When the CEO assigns an employee to a client, update the employee record
    with the client ID and the rate per hour.
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
    UPDATE employees SET assigned_client_id = ?, rate_per_hour = ? WHERE employee_id = ?
    ''', (client_id, rate_per_hour, employee_id))
    conn.commit()
    conn.close()

def get_client_profile(client_id):
    """
    Return the client record, all installments, and list of assigned employees.
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM clients WHERE client_id = ?', (client_id,))
    client = c.fetchone()
    c.execute('SELECT * FROM installments WHERE client_id = ?', (client_id,))
    installments = c.fetchall()
    c.execute('SELECT * FROM employees WHERE assigned_client_id = ?', (client_id,))
    employees = c.fetchall()
    conn.close()
    return client, installments, employees

def record_installment(client_id, amount):
    """
    Record an installment payment. Deduct the amount from the outstanding.
    """
    conn = get_db_connection()
    c = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    c.execute('''
    INSERT INTO installments (client_id, amount_paid, timestamp)
    VALUES (?, ?, ?)
    ''', (client_id, amount, timestamp))
    # Update outstanding amount
    c.execute('SELECT outstanding FROM clients WHERE client_id = ?', (client_id,))
    result = c.fetchone()
    if result:
        new_outstanding = result['outstanding'] - amount
        c.execute('UPDATE clients SET outstanding = ? WHERE client_id = ?', (new_outstanding, client_id))
    conn.commit()
    conn.close()

# =============================================================================
# FINANCIAL SUMMARY FOR PLOTTING
# =============================================================================

def get_financial_summary():
    """
    Get summary data for plotting.
    - Total outstanding from all clients.
    - Total base salary (calculated from attendance) for all employees for the current month.
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT SUM(outstanding) as total_outstanding FROM clients')
    total_outstanding = c.fetchone()['total_outstanding'] or 0
    now = datetime.datetime.now()
    start_month = datetime.datetime(now.year, now.month, 1).isoformat()
    c.execute('''
    SELECT employee_id, SUM(working_hours) as total_hours FROM attendance
    WHERE check_out_time IS NOT NULL AND check_in_time >= ?
    GROUP BY employee_id
    ''', (start_month,))
    salary_data = c.fetchall()
    total_salary = 0
    for row in salary_data:
        c.execute('SELECT rate_per_hour FROM employees WHERE employee_id = ?', (row['employee_id'],))
        rate = c.fetchone()['rate_per_hour']
        if rate:
            total_salary += rate * (row['total_hours'] or 0)
    conn.close()
    return total_outstanding, total_salary

# =============================================================================
# STREAMLIT APPLICATION
# =============================================================================

def main():
    st.title("Manpower Management System")
    
    # If the user has not logged in yet, only the Login option is available.
    menu = ["Login"]
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    # After login, the menu changes based on role.
    if st.session_state.logged_in:
        if st.session_state.role == "CEO":
            menu = ["Dashboard", "Register Employee", "Register Client", "Assign Employee", "Search Employee", "Search Client", "Financial Plots", "View All Attendance","NLP mode (Upcoming)", "Logout"]
        else:
            menu = ["Profile", "Logout"]

    choice = st.sidebar.selectbox("Menu", menu)

    # --------------------------
    # LOGIN PAGE
    # --------------------------
    if choice == "Login":
        st.subheader("Employee Login")
        employee_id = st.text_input("Employee ID")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            employee = login_employee(employee_id, password)
            if employee:
                st.success("Logged In as {}".format(employee['full_name']))
                st.session_state.logged_in = True
                st.session_state.employee_id = employee['employee_id']
                st.session_state.role = employee['role']
                st.rerun()
            else:
                st.error("Invalid credentials")

    # --------------------------
    # LOGOUT
    # --------------------------
    elif choice == "Logout":
        st.session_state.logged_in = False
        st.session_state.pop("employee_id", None)
        st.session_state.pop("role", None)
        st.success("Logged out")
        st.rerun()

    # --------------------------
    # EMPLOYEE PROFILE (for non-CEO)
    # --------------------------
    elif choice == "Profile":
        st.subheader("Employee Profile")
        employee, attendance_records = get_employee_profile(st.session_state.employee_id)
        st.write("**Employee ID:**", employee["employee_id"])
        st.write("**Full Name:**", employee["full_name"])
        st.write("**Contact Number:**", employee["contact_number"])
        st.write("**Email:**", employee["email"])
        st.write("**Role:**", employee["role"])
        st.write("**Assigned Client:**", employee["assigned_client_id"] if employee["assigned_client_id"] else "None")
        
        # Display salary details (computed for current month)
        salary = calculate_salary(st.session_state.employee_id)
        if salary:
            st.write("**Assigned Client:**", employee["assigned_client_id"] if employee["assigned_client_id"] else "None")
        if employee["photo"]:
            st.image(Image.open(io.BytesIO(employee["photo"])), caption="Photo", use_container_width=True)
        if employee["aadhar_photo"]:
            st.image(Image.open(io.BytesIO(employee["aadhar_photo"])), caption="Aadhar Card", use_container_width=True)
        if employee["signature_photo"]:
            st.image(Image.open(io.BytesIO(employee["signature_photo"])), caption="Signature", use_container_width=True)
            st.write("**Base Salary:**", round(salary["base_salary"], 2))
            st.write("**Retirement Benefit 1 (12%):**", round(salary["retirement_benefits1"], 2))
            st.write("**Retirement Benefit 2 (13%):**", round(salary["retirement_benefits2"], 2))
            st.write("**Insurance 1 (5%):**", round(salary["insurance1"], 2))
            st.write("**Insurance 2 (5%):**", round(salary["insurance2"], 2))
            st.write("**Actual Salary:**", round(salary["actual_salary"], 2))
        
        st.write("### Attendance Records")
        if attendance_records:
            # Convert attendance records to a DataFrame
            df = pd.DataFrame([dict(rec) for rec in attendance_records])
            st.dataframe(df)
        else:
            st.write("No attendance records found.")

        st.write("### Attendance Actions")
        # --- Check In Section ---
        st.markdown("**Check In:**")
        # Note: Because file uploaders work best outside of buttons,
        # we show the uploader first.
        checkin_selfie = st.file_uploader("Upload Selfie for Check In", type=["png", "jpg", "jpeg"], key="checkin_selfie")
        if st.button("Check In"):
            if checkin_selfie is not None:
                selfie_bytes = checkin_selfie.read()
                check_in_time = check_in_attendance(st.session_state.employee_id, selfie_bytes)
                st.success("Checked in at {}".format(check_in_time))
            else:
                st.warning("Please upload a selfie to check in.")
                
        # --- Check Out Section ---
        st.markdown("**Check Out:**")
        if st.button("Check Out"):
            working_hours, checkout_time = check_out_attendance(st.session_state.employee_id)
            if working_hours is None:
                st.error(checkout_time)
            else:
                st.success("Checked out at {}. Working hours: {:.2f}".format(checkout_time, working_hours))

    # --------------------------
    # CEO DASHBOARD & FUNCTIONS
    # --------------------------
    elif choice == "Dashboard":
        st.subheader("CEO Dashboard")
        st.write("Welcome, CEO! Use the sidebar to access various functionalities.")

    elif choice == "Register Employee":
        st.subheader("Register New Employee")
        with st.form("employee_form"):
            employee_id = st.text_input("Employee ID")
            full_name = st.text_input("Full Name")
            contact_number = st.text_input("Contact Number")
            email = st.text_input("Email")
            aadhar = st.text_input("Aadhar Card Number")
            dob = st.date_input("Date of Birth")
            address = st.text_area("Residential Address")
            photo = st.file_uploader("Upload Photo", type=["png", "jpg", "jpeg"], key="photo")
            aadhar_photo = st.file_uploader("Upload Aadhar Card Photo", type=["png", "jpg", "jpeg"], key="aadhar_photo")
            signature_photo = st.file_uploader("Upload Signature Photo", type=["png", "jpg", "jpeg"], key="signature_photo")
            role = st.selectbox("Role", ["Employee", "CEO"])
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Register Employee")
            if submitted:
                employee = {
                    "employee_id": employee_id,
                    "full_name": full_name,
                    "contact_number": contact_number,
                    "email": email,
                    "aadhar": aadhar,
                    "dob": dob.isoformat(),
                    "address": address,
                    "photo": photo.read() if photo is not None else None,
                    "aadhar_photo": aadhar_photo.read() if aadhar_photo is not None else None,
                    "signature_photo": signature_photo.read() if signature_photo is not None else None,
                    "role": role,
                    "password": password,
                    "assigned_client_id": None,
                    "rate_per_hour": None
                }
                register_employee(employee)
                st.success("Employee registered successfully.")

    elif choice == "Register Client":
        st.subheader("Register New Client")
        with st.form("client_form"):
            client_id = st.text_input("Client ID")
            org_name = st.text_input("Organization Name")
            description = st.text_area("Description")
            requirements = st.text_area("Requirements")
            company_contact = st.text_input("Company Contact Number")
            company_email = st.text_input("Company Email")
            person_in_charge_name = st.text_input("Person in Charge Name")
            person_in_charge_phone = st.text_input("Person in Charge Phone Number")
            person_in_charge_email = st.text_input("Person in Charge Email")
            company_type = st.selectbox("Type of Company", ["GEM", "NON-GEM"])
            total_bill = st.number_input("Total Bill Amount", min_value=0.0, format="%.2f")
            submitted = st.form_submit_button("Register Client")
            if submitted:
                client = {
                    "client_id": client_id,
                    "org_name": org_name,
                    "description": description,
                    "requirements": requirements,
                    "company_contact": company_contact,
                    "company_email": company_email,
                    "person_in_charge_name": person_in_charge_name,
                    "person_in_charge_phone": person_in_charge_phone,
                    "person_in_charge_email": person_in_charge_email,
                    "company_type": company_type,
                    "total_bill": total_bill
                }
                register_client(client)
                st.success("Client registered successfully.")

    elif choice == "Assign Employee":
        st.subheader("Assign Employee to Client")
        with st.form("assign_form"):
            employee_id = st.text_input("Employee ID")
            client_id = st.text_input("Client ID")
            rate_per_hour = st.number_input("Rate per Hour", min_value=0.0, format="%.2f")
            submitted = st.form_submit_button("Assign")
            if submitted:
                assign_employee_to_client(employee_id, client_id, rate_per_hour)
                st.success("Employee {} assigned to Client {} with rate {}".format(employee_id, client_id, rate_per_hour))
    
    elif choice == "Record Installment":
        st.subheader("Record Installment Payment for Client")
        with st.form("installment_form"):
            client_id = st.text_input("Client ID")
            amount = st.number_input("Installment Amount", min_value=0.0, format="%.2f")
            submitted = st.form_submit_button("Record Payment")
            if submitted:
                record_installment(client_id, amount)
                st.success(f"Recorded installment of {amount} for client {client_id}.")

    elif choice == "Search Employee":
        st.subheader("Search Employee")
        search_term = st.text_input("Enter Employee ID or Name")
        if st.button("Search"):
            conn = get_db_connection()
            c = conn.cursor()
            query = "SELECT * FROM employees WHERE employee_id LIKE ? OR full_name LIKE ?"
            c.execute(query, (f"%{search_term}%", f"%{search_term}%"))
            results = c.fetchall()
            conn.close()
            if results:
                for emp in results:
                    st.write("### Employee ID:", emp["employee_id"])
                    st.write("**Full Name:**", emp["full_name"])
                    st.write("**Contact Number:**", emp["contact_number"])
                    st.write("**Email:**", emp["email"])
                    st.write("**Role:**", emp["role"])
                    st.markdown("---")
            else:
                st.write("No results found.")

    elif choice == "Search Client":
        st.subheader("Search Client")
        search_term = st.text_input("Enter Client ID or Organization Name")
        if st.button("Search"):
            conn = get_db_connection()
            c = conn.cursor()
            query = "SELECT * FROM clients WHERE client_id LIKE ? OR org_name LIKE ?"
            c.execute(query, (f"%{search_term}%", f"%{search_term}%"))
            results = c.fetchall()
            conn.close()
            if results:
                for client in results:
                    st.write("### Client ID:", client["client_id"])
                    st.write("**Organization Name:**", client["org_name"])
                    st.write("**Contact:**", client["company_contact"])
                    st.write("**Outstanding:**", client["outstanding"])
                    st.markdown("---")
            else:
                st.write("No results found.")

    elif choice == "Financial Plots":
        st.subheader("Financial Summary Plots")
        total_outstanding, total_salary = get_financial_summary()
        st.write("**Total Outstanding from Clients:**", total_outstanding)
        st.write("**Total Base Salary for Employees (this month):**", total_salary)
        fig, ax = plt.subplots()
        categories = ["Outstanding", "Base Salary"]
        values = [total_outstanding, total_salary]
        ax.bar(categories, values, color=["red", "green"])
        ax.set_ylabel("Amount")
        st.pyplot(fig)
    
    elif choice == "View All Attendance":
        st.subheader("Attendance Records for All Employees")
        conn = get_db_connection()
        c = conn.cursor()
        query = """
        SELECT a.employee_id, e.full_name, a.check_in_time, a.check_in_location, 
            a.check_out_time, a.check_out_location, a.working_hours
        FROM attendance a
        JOIN employees e ON a.employee_id = e.employee_id
        ORDER BY a.check_in_time DESC
        """
        c.execute(query)
        records = c.fetchall()
        if records:
            df = pd.DataFrame([dict(r) for r in records])
            st.dataframe(df)
        else:
            st.write("No attendance records found.")


if __name__ == "__main__":
    init_db()  # Initialize (or create) the database and tables on app start
    main()
