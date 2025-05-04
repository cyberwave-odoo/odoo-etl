# Odoo ETL Example Module

This module provides a practical example of using the ETL functionality to import customer data from a SQLite database into Odoo.

## Database Setup

To generate the sample SQLite database, run:
```bash
python odoo_etl_example/db/create_sample_db.py
```

## Field Mapping Explanation

The demo configuration maps customer data from SQLite to Odoo's `res.partner` model:

1. **Name Field**: Combines `first_name` and `last_name` from the source
   ```python
   'name': {
       'type': 'lambda',
       'function': lambda self, record, **kwargs: f"{record['first_name']} {record['last_name']}"
   }
   ```

2. **Email Field**: Direct mapping from `email_address` column
   ```python
   'email': {
       'type': 'column',
       'column_name': 'email_address'
   }
   ```

3. **Country Field**: Joins with Odoo's `res.country` model using country names
   ```python
   'country_id': {
       'type': 'join',
       'lookup_table': 'res.country',
       'left_on': 'country',
       'right_on': 'name'
   }
   ```

The unique identifier for matching records is the email address. 
