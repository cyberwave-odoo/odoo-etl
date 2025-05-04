import os

# Database configuration
DB_CONFIG = {
    'type': 'sqlite',
    'host': 'localhost',
    'database': os.path.join(os.path.dirname(__file__), 'db/customers.db'),
    'user': 'admin',
    'password': 'admin123',
}
