# -*- coding: utf-8 -*-
{
    'name': "Odoo ETL - SQLite Connector",

    'summary': """
        SQLite database connector for Odoo ETL module""",

    'description': """
        This module provides SQLite database connectivity for the Odoo ETL system.
        It allows you to connect to SQLite databases and use them as data sources
        for ETL operations using Python's built-in sqlite3 library (no external dependencies).
    """,

    'author': "Cyberwave",
    'website': "https://www.cyberwave.be",

    'category': 'Tools',
    'version': '17.0.1.0.0',
    'license': 'AGPL-3',

    'depends': ['base'],

    'data': [
        'security/ir.model.access.csv',
        'views/base_external_dbsource_view.xml',
        'views/menu.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,

    'images': ['static/description/icon.png'],
}
