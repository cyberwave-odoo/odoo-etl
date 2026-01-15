# -*- coding: utf-8 -*-
# Copyright 2024 Cyberwave
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import sqlite3
import os
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BaseExternalDbsource(models.Model):
    _name = 'base.external.dbsource'
    _description = 'External Database Source - SQLite Support'

    name = fields.Char('Datasource name', required=True)
    conn_string = fields.Text('Connection string', required=True,
                             help='Path to SQLite database file, e.g., /path/to/database.db or C:\\path\\to\\database.db')
    connector = fields.Selection([('sqlite', 'SQLite')], string='Connector', default='sqlite', required=True)
    password = fields.Char('Password')  # Not used for SQLite but kept for compatibility
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    def _get_sqlite_path(self):
        """Extract and validate the SQLite database path from conn_string"""
        self.ensure_one()

        # Handle various connection string formats
        conn_str = self.conn_string.strip()

        # Remove sqlite:/// prefix if present
        if conn_str.startswith('sqlite:///'):
            db_path = conn_str.replace('sqlite:///', '', 1)
        else:
            db_path = conn_str

        # Validate path exists
        if not os.path.exists(db_path):
            raise ValidationError(f"SQLite database file not found: {db_path}")

        return db_path

    def execute_sqlite(self, query, params=None, metadata=True):
        """
        Execute a SQL query on the SQLite database

        Args:
            query: SQL query to execute (string or text object with .text attribute)
            params: Tuple/dict of parameters for the query
            metadata: If True, return (results, column_names), else return (results, None)

        Returns:
            Tuple of (results, column_names) if metadata=True
            Tuple of (results, None) if metadata=False
        """
        self.ensure_one()

        if self.connector != 'sqlite':
            raise ValidationError(f"This method only works with SQLite connector, current connector is: {self.connector}")

        # Get the database path
        db_path = self._get_sqlite_path()

        # Convert text object to string if needed
        if hasattr(query, 'text'):
            query_str = str(query)
        else:
            query_str = query

        params = params or ()

        connection = None
        try:
            # Connect to the database
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row  # Enable column name access
            cursor = connection.cursor()

            # Execute the query
            if isinstance(params, dict):
                cursor.execute(query_str, params)
            else:
                cursor.execute(query_str, params)

            # Fetch results
            rows = cursor.fetchall()

            # Commit if query modifies data
            if query_str.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'DROP', 'ALTER')):
                connection.commit()

            # Get column names if metadata requested
            cols = None
            if metadata and cursor.description:
                cols = [description[0] for description in cursor.description]

            # Convert Row objects to tuples
            results = [tuple(row) for row in rows]

            return results, cols

        except sqlite3.Error as e:
            _logger.error("SQLite error executing query: %s", str(e))
            raise ValidationError(f"Query execution failed: {str(e)}")
        except Exception as e:
            _logger.error("Error executing SQLite query: %s", str(e))
            raise ValidationError(f"Query execution failed: {str(e)}")
        finally:
            if connection:
                connection.close()

    def connection_test(self):
        """Test the database connection"""
        self.ensure_one()

        try:
            # Get the database path (this validates it exists)
            db_path = self._get_sqlite_path()

            # Try to connect and execute a simple query
            connection = sqlite3.connect(db_path)
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            connection.close()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Test Successful',
                    'message': f'Successfully connected to the SQLite database at: {db_path}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise ValidationError(f"Connection test failed: {str(e)}")

    def get_table_list(self):
        """Get list of tables in the database"""
        self.ensure_one()

        db_path = self._get_sqlite_path()

        try:
            connection = sqlite3.connect(db_path)
            cursor = connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = [row[0] for row in cursor.fetchall()]
            connection.close()
            return tables
        except Exception as e:
            _logger.error("Error getting table list: %s", str(e))
            raise ValidationError(f"Failed to get table list: {str(e)}")

    def get_table_columns(self, table_name):
        """Get columns for a specific table"""
        self.ensure_one()

        db_path = self._get_sqlite_path()

        try:
            connection = sqlite3.connect(db_path)
            cursor = connection.cursor()
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = [row[1] for row in cursor.fetchall()]  # Column name is at index 1
            connection.close()
            return columns
        except Exception as e:
            _logger.error("Error getting table columns: %s", str(e))
            raise ValidationError(f"Failed to get table columns: {str(e)}")
