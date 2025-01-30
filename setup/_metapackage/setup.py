import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo12-addons-akretion-subcontractor",
    description="Meta package for akretion-subcontractor Odoo addons",
    version=version,
    install_requires=[
        'odoo12-addon-account_invoice_subcontractor',
        'odoo12-addon-project_invoicing_subcontractor',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 12.0',
    ]
)
