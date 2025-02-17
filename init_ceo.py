import sqlite3
import datetime
import os

DB_PATH = "company.db"

def get_db_connection():
    """Create and return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    """Initialize the database and create the employees table if it doesn't exist."""
    conn = get_db_connection()
    c = conn.cursor()
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
    conn.commit()
    conn.close()

def read_file_as_bytes(filepath):
    """
    Read the file at the given path as bytes.
    Return None if the filepath is empty or file does not exist.
    """
    if filepath and os.path.exists(filepath):
        with open(filepath, "rb") as file:
            return file.read()
    return None

def register_ceo():
    """Prompt the user for CEO details and register the CEO into the database."""
    print("=== Register CEO ===")
    employee_id = input("Enter Employee ID: ").strip()
    full_name = input("Enter Full Name: ").strip()
    contact_number = input("Enter Contact Number: ").strip()
    email = input("Enter Email: ").strip()
    aadhar = input("Enter Aadhar Card Number: ").strip()
    dob = input("Enter Date of Birth (YYYY-MM-DD): ").strip()
    address = input("Enter Residential Address: ").strip()
    
    print("\n(For image fields, enter the file path or leave blank to skip.)")
    photo_path = input("Enter path to Photo: ").strip()
    aadhar_photo_path = input("Enter path to Aadhar Card Photo: ").strip()
    signature_photo_path = input("Enter path to Signature Photo: ").strip()
    
    password = input("Enter Password: ").strip()

    # Read files as binary data if provided
    photo_bytes = read_file_as_bytes(photo_path) if photo_path else None
    aadhar_photo_bytes = read_file_as_bytes(aadhar_photo_path) if aadhar_photo_path else None
    signature_photo_bytes = read_file_as_bytes(signature_photo_path) if signature_photo_path else None

    # For CEO, we fix the role as "CEO" and leave assigned_client_id and rate_per_hour as None.
    role = "CEO"
    assigned_client_id = None
    rate_per_hour = None

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO employees (
                employee_id, full_name, contact_number, email, aadhar, dob, address, 
                photo, aadhar_photo, signature_photo, role, password, assigned_client_id, rate_per_hour
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            employee_id,
            full_name,
            contact_number,
            email,
            aadhar,
            dob,
            address,
            photo_bytes,
            aadhar_photo_bytes,
            signature_photo_bytes,
            role,
            password,
            assigned_client_id,
            rate_per_hour
        ))
        conn.commit()
        print("\nCEO registered successfully.")
    except Exception as e:
        print(f"\nError registering CEO: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()  # Ensure the database and table are created
    register_ceo()
