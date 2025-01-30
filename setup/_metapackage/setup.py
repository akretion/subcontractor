import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo-addons-akretion-subcontractor",
    description="Meta package for akretion-subcontractor Odoo addons",
    version=version,
    install_requires=[
        'odoo-addon-account_invoice_subcontractor>=16.0dev,<16.1dev',
        'odoo-addon-account_move_line_project>=16.0dev,<16.1dev',
        'odoo-addon-project_invoicing_subcontractor>=16.0dev,<16.1dev',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 16.0',
    ]
)
