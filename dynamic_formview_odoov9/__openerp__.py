{
    'name': 'Dynamic FormView advance Odoo 9',
    'summary': 'Dynamic FormView advance Odoo 9',
    'version': '1.0',
    'category': 'Web',
    'description': """
        Dynamic FormView advance Odoo 9
    """,
    'author': "Odoo Good",
    'depends': ['web'],
    'data': ['templates.xml'],
    'qweb': ['static/src/xml/formview.xml',
             'security/show_fields_security.xml',
             'security/ir.model.access.csv'],
    'images': ['images/main_screen.jpg'],
    'price': 100,
    'currency': 'EUR',
    'installable': True,
    'auto_install': False,
    'application': False,
}
