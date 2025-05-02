# -*- coding: utf-8 -*-
{
    'name': "odoo-etl",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Cyberwave",
    'website': "https://www.cyberwave.be",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '16.0.1',
    'license': 'AGPL-3',
    # any module necessary for this one to work correctly
    'depends': ['base', 'base_external_dbsource_sqlite'],
    "external_dependencies": {"python": ["polars"]},
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/etl_view.xml',
        'views/menu.xml',
        
        
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odoo_etl/static/src/*/*',
        ],
    },
    'images': ['static/description/icon.png'],
}
