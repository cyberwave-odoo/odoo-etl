# -*- coding: utf-8 -*-
{
    'name': "Odoo ETL Framework (Extract, Transform, Load)",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Cyberwave",
    'website': "https://www.cyberwave.be",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/18.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '18.0.1.0',
    'license': 'AGPL-3',
    # any module necessary for this one to work correctly
    'depends': ['base', 'odoo_etl_sqlite'],
    "external_dependencies": {"python": ["polars"]},
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/etl_view.xml',
        'views/etl_log_view.xml',
        'views/menu.xml',
        'wizard/etl_mapping_wizard_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'images': ['static/description/icon.png'],
}
