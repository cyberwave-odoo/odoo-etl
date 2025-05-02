# Odoo ETL Project

![Odoo](https://img.shields.io/badge/Odoo-16.0-blue)
![License](https://img.shields.io/badge/License-AGPL--3-green)
![Python](https://img.shields.io/badge/Python-3.9+-yellow)

## Overview

This project is an ETL (Extract, Transform, Load) solution built on top of Odoo 16.0. It provides tools and modules to facilitate data import, transformation, and synchronization between external databases and Odoo models. The project is designed to handle complex data mappings and transformations using the Polars library and SQLAlchemy.

## Features

- **ETL Models**: Define and manage ETL processes for various Odoo models.
- **Data Transformation**: Use Polars for efficient data manipulation and transformation.
- **Database Integration**: Supports SQLite and other external databases.
- **Custom Import Logic**: Extend and customize import logic for specific use cases.
- **Batch Processing**: Handle large datasets with batch processing capabilities.

## Example Usage

Here is an example of how to use the `ETLModel` to import data into Odoo with different mapping options:

1. **Define the ETL Model**:
   - Create an ETL model record in Odoo with the following fields:
     - `name`: Name of the external table (e.g., `external_table`).
     - `odoo_name`: Name of the Odoo model (e.g., `res.partner`).
     - `field_mapping`: A dictionary defining how fields are mapped between the external table and Odoo.

2. **Field Mapping Options**:
   - **Column Mapping**: Directly map a column from the external table to an Odoo field.
   - **Lambda Mapping**: Use a Python function to transform data before importing.
   - **Join Mapping**: Perform a lookup in another Odoo model to map values.
   - **Object Lambda Mapping**: Use a function that returns complex objects.

3. **Example Field Mapping**:
   ```python
   {
       "name": {"type": "column", "column_name": "external_name"},
       "email": {"type": "lambda", "function": lambda self, row, **kwargs: row["email"].lower()},
       "country_id": {
           "type": "join",
           "lookup_table": "res.country",
           "left_on": "country_code",
           "right_on": "code",
           "model_field": "id"
       },
       "tags": {
           "type": "object_lambda",
           "function": lambda self, row, **kwargs: [{"name": tag} for tag in row["tags"].split(",")]
       }
   }
   ```

4. **Trigger the Import**:
   - Call the `import_table_records` method to start the import process:
     ```python
     etl_model = env['etl.model'].search([('name', '=', 'external_table')], limit=1)
     etl_model.import_table_records()
     ```

5. **Custom Import Logic**:
   - If `custom_import` is enabled, implement the `custom_import` method in the corresponding Odoo model to handle specific import logic.

6. **Understanding Unique Identifiers**:
   - The `unique_identifier_tuple` field in the ETL model defines how records are matched between the external database and Odoo.
   - It is a tuple with two elements:
     1. **Odoo Unique Identifier**: The field in the Odoo model used to uniquely identify records (e.g., `odoo_id` or `external_id`).
     2. **External Unique Identifier**: The field(s) in the external database used to uniquely identify records. This can be a single column or a combination of columns.
   - During the import process:
     - The external unique identifier is used to deduplicate records from the external database.
     - The Odoo unique identifier is used to check if a record already exists in Odoo.
   - Example:
     ```python
     unique_identifier_tuple = ("odoo_id", ("external_id", "external_code"))
     ```
     - Here, `odoo_id` is the Odoo unique identifier, and `external_id` and `external_code` are combined to form the unique identifier for the external database.

## Dependencies

This project depends on the following external repository:

- [OCA/server-backend](https://github.com/OCA/server-backend): Provides essential backend tools and utilities for Odoo.

Make sure to clone and include this repository in your Odoo addons path.

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/your-repo/odoo-etl.git
   ```

2. Clone the `server-backend` repository:
   ```bash
   git clone https://github.com/OCA/server-backend.git
   ```

3. Add both repositories to your Odoo addons path.

4. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Start your Odoo instance and install the `odoo-etl` module.

## Usage

- Navigate to the **ETL** menu in Odoo to manage ETL models and processes.
- Configure external database connections and field mappings.
- Run import/export jobs to synchronize data.

## Need Help with Integration?

If you need assistance with integrating this ETL solution into your Odoo environment or have specific requirements, feel free to reach out to us. Visit [Cyberwave Contact Us](https://www.cyberwave.be/contactus) for professional support and guidance.

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Submit a pull request with a detailed description of your changes.

## License

This project is licensed under the AGPL-3.0 License. See the LICENSE file for details.

---

Happy ETLing! 🚀