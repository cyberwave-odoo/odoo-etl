import sqlite3
import os
from datetime import datetime

def create_sample_database():
    # Create the database directory if it doesn't exist
    db_dir = os.path.dirname(__file__)
    print(f"Creating database directory at: {db_dir}")
    os.makedirs(db_dir, exist_ok=True)
    
    # Connect to SQLite database (creates it if it doesn't exist)
    db_path = os.path.join(db_dir, 'customers.db')
    print(f"Connecting to database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print("Successfully connected to database")
        
        # Create customers table
        print("Creating customers table...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email_address TEXT,
            contact_number TEXT,
            address TEXT,
            city TEXT,
            country TEXT,
            created_date TEXT,
            customer_type TEXT
        )
        ''')
        print("Customers table created successfully")
        
        # Sample customer data
        customers = [
            (1, 'John', 'Doe', 'john.doe@example.com', '+1234567890', '123 Main St', 'New York', 'United States', 
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'regular'),
            (2, 'Jane', 'Smith', 'jane.smith@example.com', '+1987654321', '456 Oak Ave', 'London', 'United States',
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'premium'),
            (3, 'Bob', 'Johnson', 'bob.johnson@example.com', '+1122334455', '789 Pine Rd', 'Toronto', 'United States',
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'regular'),
            (4, 'Alice', 'Brown', 'alice.brown@example.com', '+1555666777', '321 Elm St', 'Sydney', 'United States',
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'premium'),
        ]
        
        # Insert sample data
        print("Inserting sample customer data...")
        cursor.executemany('''
        INSERT OR REPLACE INTO customers 
        (customer_id, first_name, last_name, email_address, contact_number, address, city, country, created_date, customer_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', customers)
        print(f"Inserted {len(customers)} customer records")
        
        # Create users table for authentication
        print("Creating users table...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        ''')
        print("Users table created successfully")
        
        # Sample user data (in a real application, passwords should be hashed)
        users = [
            ('admin123', 'admin123', 'admin'),
            ('user', 'user123', 'user'),
        ]
        
        print("Inserting sample user data...")
        cursor.executemany('''
        INSERT OR REPLACE INTO users (username, password, role)
        VALUES (?, ?, ?)
        ''', users)
        print(f"Inserted {len(users)} user records")
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        print(f"Database created and populated successfully at {db_path}!")
        
    except Exception as e:
        print(f"Error creating database: {str(e)}")
        raise

if __name__ == '__main__':
    create_sample_database() 