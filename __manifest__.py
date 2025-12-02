# odoo_pokeapi/__manifest__.py
{
    'name': 'PokeAPI Wizard',
    'version': '18.0.1.2',
    'summary': 'Consulta información de Pokémon y Objetos desde Odoo',
    'category': 'Tools',
    'author': 'ESGD',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/poke_wizard_view.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}