import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo8-addons-akretion-connector-amazon",
    description="Meta package for akretion-connector-amazon Odoo addons",
    version=version,
    install_requires=[
        'odoo8-addon-connector_amazon',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 8.0',
    ]
)
