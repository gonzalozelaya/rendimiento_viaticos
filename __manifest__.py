# -*- coding: utf-8 -*-
{
    'name': "Modificaciones Viaticos",

    'summary': "Modificaciones Viaticos",
    
    'description': """
         
    """,

    'author': "OutsourceArg",
    'website': "https://www.outsourcearg.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['hr_expense'],
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/hr_expense.xml',
    ],
    # only loaded in demonstration mode
    'installable':True,
    'application':False,
}