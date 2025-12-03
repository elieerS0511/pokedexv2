# odoo_pokeapi/models/poke_wizard.py
import requests
import base64
from odoo import models, fields, api
from odoo.exceptions import UserError

class PokeWizard(models.TransientModel):
    _name = 'poke.wizard'
    _description = 'Asistente de Consulta Pokémon y Objetos'

    # Define el valor por defecto para el campo 'search_type'.
    def _get_default_type(self):
        return 'pokemon'

    search_type = fields.Selection([
        ('pokemon', 'Pokémon'),
        ('item', 'Objeto / Baya')
    ], string='Tipo de Búsqueda', required=True, default=_get_default_type)

    search_name = fields.Char(string='Nombre o ID', required=True)

    found = fields.Boolean(default=False)
    result_name = fields.Char(string='Nombre', readonly=True)
    result_id = fields.Integer(string='ID', readonly=True)

    # Datos de Pokémon
    height_cm = fields.Float(string='Altura (cm)', readonly=True)
    weight_kg = fields.Float(string='Peso (kg)', readonly=True)
    poke_types = fields.Char(string='Tipos', readonly=True)

    # Datos de Objetos
    item_cost = fields.Integer(string='Costo', readonly=True)
    item_effect = fields.Text(string='Efecto', readonly=True)

    # Imágenes
    sprite_front = fields.Binary(string='Vista Frontal', readonly=True)
    sprite_back = fields.Binary(string='Vista Trasera', readonly=True)

    # Se activa al cambiar el tipo de búsqueda y limpia las imágenes anteriores.
    @api.onchange('search_type')
    def _onchange_search_type(self):
        self.sprite_front = False
        self.sprite_back = False

    # Descarga una imagen desde una URL y la convierte a formato Base64.
    def _fetch_image(self, url):
        if not url:
            return False
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return base64.b64encode(response.content)
        except requests.exceptions.RequestException:
            return False
        return False

    # Realiza la búsqueda en la PokeAPI y actualiza los campos del asistente.
    def action_search_api(self):
        query = self.search_name.strip().lower()
        base_url = 'https://pokeapi.co/api/v2'
        endpoint = 'pokemon' if self.search_type == 'pokemon' else 'item'
        api_url = f'{base_url}/{endpoint}/{query}'

        try:
            response = requests.get(api_url, timeout=10)
            if response.status_code == 404:
                raise UserError(f"No se encontró '{query}' en la categoría {self.search_type.capitalize()}.")
            if response.status_code != 200:
                raise UserError("Error de conexión con la PokeAPI.")

            data = response.json()

            # Prepara los valores base para el nuevo asistente.
            vals = {
                'search_type': self.search_type,
                'search_name': self.search_name,
                'found': True,
                'result_name': data['name'].replace('-', ' ').title(),
                'result_id': data['id'],
            }

            # Añade campos específicos según el tipo de búsqueda.
            if self.search_type == 'pokemon':
                vals.update({
                    'height_cm': data['height'] * 10,
                    'weight_kg': data['weight'] / 10.0,
                    'poke_types': ", ".join(t['type']['name'].capitalize() for t in data['types']),
                    'sprite_front': self._fetch_image(data['sprites'].get('front_default')),
                    'sprite_back': self._fetch_image(data['sprites'].get('back_default')),
                })
            elif self.search_type == 'item':
                effect_text = "Sin descripción."
                if 'effect_entries' in data and data['effect_entries']:
                    for entry in data['effect_entries']:
                        if entry['language']['name'] == 'es':
                            effect_text = entry['short_effect']
                            break

                vals.update({
                    'item_cost': data.get('cost', 0),
                    'item_effect': effect_text,
                    'sprite_front': self._fetch_image(data['sprites'].get('default')),
                })

            # Crea un nuevo asistente para mostrar los resultados.
            new_wizard = self.create(vals)

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'poke.wizard',
                'view_mode': 'form',
                'res_id': new_wizard.id,
                'target': 'new',
            }

        except requests.exceptions.RequestException as e:
            raise UserError(f"Error de red al conectar con PokeAPI: {e}")
