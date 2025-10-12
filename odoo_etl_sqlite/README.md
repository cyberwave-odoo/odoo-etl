# Odoo ETL - SQLite Connector

![Odoo](https://img.shields.io/badge/Odoo-18.0-blue)
![License](https://img.shields.io/badge/License-AGPL--3-green)
![Python](https://img.shields.io/badge/Python-3.10+-yellow)

## Overview

This module provides SQLite database connectivity for the Odoo ETL system. It allows you to connect to SQLite databases and use them as data sources for ETL operations.

## Features

- **Zero External Dependencies**: Uses Python's built-in `sqlite3` library (part of Python standard library)
- **Simple Configuration**: Just provide the path to your SQLite database file
- **Connection Testing**: Built-in connection test functionality
- **Table Discovery**: Automatically list tables and columns from the database
- **Seamless Integration**: Works perfectly with the `odoo_etl` module

## Installation

1. Make sure the `odoo_etl` module is installed
2. Copy this module to your Odoo addons directory
3. Update the app list in Odoo
4. Install the `odoo_etl_sqlite` module

## Configuration

1. Go to **ETL > Database Sources**
2. Click **Create**
3. Fill in the following fields:
   - **Name**: A descriptive name for your database source (e.g., "Legacy Database")
   - **Connector**: SQLite (automatically selected)
   - **Connection String**: Path to your SQLite database file

### Connection String Examples

**Linux/Mac:**
```
/home/user/data/database.db
```

**Windows:**
```
C:\Users\user\data\database.db
```

**SQLite URI format:**
```
sqlite:///path/to/database.db
```

4. Click **Test Connection** to verify the connection works

## Usage

Once configured, the database source can be used in your ETL model definitions:

1. Create or edit an ETL model
2. Select your SQLite database source
3. Configure field mappings as usual
4. Run the import

## Technical Details

### Model

- **Model Name**: `base.external.dbsource`
- **Database**: SQLite 3.x (via Python's sqlite3 module)

### Methods

The module provides the following key methods:

- `execute_sqlite(query, params, metadata)`: Execute SQL queries
- `connection_test()`: Test database connectivity
- `get_table_list()`: Retrieve list of tables
- `get_table_columns(table_name)`: Get columns for a specific table

## Requirements

- Python 3.10+ (with built-in sqlite3 support)
- Odoo 18.0
- odoo_etl module

## License

This project is licensed under the AGPL-3.0 License.

## Support

If you need assistance with integration or have specific requirements, visit [Cyberwave Contact Us](https://www.cyberwave.be/contactus) for professional support.

---

Made with ❤️ by Cyberwave
