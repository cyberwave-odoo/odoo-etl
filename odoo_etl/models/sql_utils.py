from odoo import models
import polars as pl
import logging


_logger = logging.getLogger(__name__)

class PolarsSQLTypeMapper(models.AbstractModel):
    _name = 'polars.sql.type.mapper'
    _description = 'Polars SQL Type Mapper'
    
    def _get_polars_type(self, dtype):
        """
        Map SQLite data types to Polars data types.
        Handles SQLite types such as BIGINT, VARCHAR(n), etc.
        """

        # Normalize the type for easier comparison (remove constraints like size)
        normalized_dtype = dtype.upper()
        
        if "VARCHAR" in normalized_dtype or "TEXT" in normalized_dtype:
            return pl.Utf8  # Polars equivalent of TEXT
        elif normalized_dtype in ["BIGINT", "SMALLINT", "INTEGER"]:
            return pl.Int64  # Polars equivalent of INTEGER
        elif normalized_dtype in ["REAL", "FLOAT", "DOUBLE"]:
            return pl.Float64  # Polars equivalent of REAL
        elif normalized_dtype in ["BOOLEAN", "BOOL"]:
            return pl.Boolean  # Polars equivalent of BOOLEAN
        elif normalized_dtype == ["DATE","TIME"]:
            return pl.Utf8  # Polars equivalent of DATE
        elif normalized_dtype in ["DATETIME", "TIMESTAMP"]:
            return pl.Utf8  # Polars equivalent of DATETIME/TIMESTAMP
        else:
            return None
    
    def _get_sql_type(self, dtype, col):
        """
        Map Polars data types to SQL data types.
        """
        if dtype == pl.Utf8:
            return "TEXT"
        elif dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64]:
            return "INTEGER"
        elif dtype in [pl.Float32, pl.Float64]:
            return "REAL"
        elif dtype == pl.Boolean:
            return "BOOLEAN"
        elif dtype == pl.Date:
            return "DATE"
        elif dtype == pl.Datetime:
            return "TIMESTAMP"
        else:
            raise ValueError(f"Unsupported Polars dtype: {dtype} for {col}")
        
    def _populate_sql_table(self, new_table_name, new_table):
        
        query = f"DROP TABLE IF EXISTS {new_table_name};"
        self.env['etl.model'].execute_query(query, (), metadata=False, sqlite_guess=False)

        # Generate CREATE TABLE statement dynamically based on Polars schema
        
        column_definitions = [
            f"{col} {self._get_sql_type(dtype, col)}"
            for col, dtype in zip(new_table.columns, new_table.dtypes)
        ]
        
        create_table_query = f"""
        CREATE TABLE {new_table_name} (
            {', '.join(column_definitions)}
        );
        """
        
        self.env['etl.model'].execute_query(create_table_query, (), metadata=False, sqlite_guess=False)

        # Insert data into 'horaires_join'
        data = new_table.rows()
        batch_size = 5000  # Adjust batch size if needed for performance

        data_batches = [data[i:i + batch_size] for i in range(0, len(data), batch_size)]

        for batch in data_batches:
            # Prepare the values for the batch
            values = ', '.join(map(str, batch)).replace("None", "NULL")
            
            insert_query = f"""
            INSERT INTO {new_table_name} ({', '.join(new_table.columns)})
            VALUES {values};
            """
            
            # Execute the batch insert query
            self.env['etl.model'].execute_query(insert_query, (), metadata=False, sqlite_guess=False)

        _logger.info(f"{new_table_name} table successfully populated with joined data.")


        
