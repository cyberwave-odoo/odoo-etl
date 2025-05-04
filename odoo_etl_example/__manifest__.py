{
    'name': 'ETL Example',
    'version': '16.0',
    'category': 'Tools',
    'summary': 'Example module demonstrating ETL functionality',
    'description': """
        This module provides an example of how to use the ETL functionality
        to import customer data from a SQLite database into Odoo.
    """,
    'license': 'AGPL-3',
    'depends': ['odoo_etl'],
    'data': [
        'views/etl_example_views.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
} 