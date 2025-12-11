# -*- coding: utf-8 -*-
"""
Este módulo define un asistente (wizard) de Odoo para interactuar con la PokeAPI.
Permite a los usuarios buscar información sobre Pokémon y objetos/bayas directamente
desde la interfaz de Odoo y muestra los resultados en una ventana emergente.
"""
import requests
import base64
from odoo import models, fields, api
from odoo.exceptions import UserError

class PokeWizard(models.TransientModel):
    """
    Define el modelo de datos para el asistente de consulta a la PokeAPI.
    Al ser un 'TransientModel', los registros se almacenan temporalmente en la
    base de datos y se eliminan periódicamente. Es ideal para ventanas emergentes
    y diálogos que no necesitan persistir.
    """
    _name = 'poke.wizard'
    _description = 'Asistente de Consulta Pokémon y Objetos'

    def _get_default_type(self):
        """
        Retorna el valor por defecto para el campo 'search_type'.
        Esto asegura que la opción 'Pokémon' esté seleccionada al abrir el asistente.
        """
        return 'pokemon'

    # --- Campos del Modelo ---
    # Estos campos definen la estructura de datos del asistente.

    search_type = fields.Selection([
        ('pokemon', 'Pokémon'),
        ('item', 'Objeto / Baya')
    ], string='Tipo de Búsqueda', required=True, default=_get_default_type,
       help="Permite elegir entre buscar un Pokémon o un objeto/baya.")

    search_name = fields.Char(string='Nombre o ID', required=True,
                              help="Campo para introducir el nombre o el ID del Pokémon/objeto a buscar.")

    # Campos para controlar la visibilidad y mostrar resultados comunes
    found = fields.Boolean(string="Encontrado", default=False, readonly=True,
                           help="Indica si la búsqueda tuvo éxito. Se usa para mostrar/ocultar los resultados en la vista.")
    result_name = fields.Char(string='Nombre', readonly=True, help="Nombre del Pokémon u objeto encontrado.")
    result_id = fields.Integer(string='ID', readonly=True, help="ID oficial del Pokémon u objeto en la PokeAPI.")

    # Campos específicos para los datos de un Pokémon
    height_cm = fields.Float(string='Altura (cm)', readonly=True, help="Altura del Pokémon convertida a centímetros.")
    weight_kg = fields.Float(string='Peso (kg)', readonly=True, help="Peso del Pokémon convertido a kilogramos.")
    poke_types = fields.Char(string='Tipos', readonly=True, help="Tipos del Pokémon (ej. Fuego, Agua).")

    # Campos específicos para los datos de un objeto/baya
    item_cost = fields.Integer(string='Costo', readonly=True, help="Costo o valor del objeto en el juego.")
    item_effect = fields.Text(string='Efecto', readonly=True, help="Descripción corta del efecto del objeto.")

    # Campos para almacenar las imágenes en formato Base64
    sprite_front = fields.Binary(string='Vista Frontal', readonly=True, help="Imagen frontal del Pokémon u objeto.")
    sprite_back = fields.Binary(string='Vista Trasera', readonly=True, help="Imagen trasera del Pokémon. No aplica a objetos.")

    # --- Métodos de Comportamiento ---

    @api.onchange('search_type')
    def _onchange_search_type(self):
        """
        Se ejecuta automáticamente cuando el usuario cambia el 'Tipo de Búsqueda'.
        Limpia las imágenes para evitar mostrar una imagen que no corresponde
        con el tipo de búsqueda seleccionado.
        """
        self.sprite_front = False
        self.sprite_back = False

    def _fetch_image(self, url):
        """
        Descarga una imagen desde una URL y la convierte a formato Base64.

        Args:
            url (str): La URL de la imagen a descargar.

        Returns:
            bytes or False: Los datos de la imagen en Base64 si la descarga es exitosa,
                           o False si ocurre un error o la URL está vacía.
        """
        if not url:
            return False
        try:
            # Se realiza una petición GET a la URL de la imagen.
            response = requests.get(url, timeout=5)
            # Si la respuesta es exitosa (código 200 OK), se procesa el contenido.
            if response.status_code == 200:
                # El contenido de la imagen (en bytes) se codifica a Base64.
                return base64.b64encode(response.content)
        except requests.exceptions.RequestException:
            # Si hay un error de red (ej. timeout, sin conexión), se retorna False.
            return False
        return False

    def action_search_api(self):
        """
        Ejecuta la búsqueda en la PokeAPI cuando el usuario hace clic en el botón 'Consultar'.
        Esta función se encarga de:
        1. Limpiar los resultados anteriores.
        2. Construir y realizar la llamada a la API.
        3. Procesar la respuesta y actualizar los campos del asistente.
        4. Manejar errores de conexión o si no se encuentra el recurso.
        5. Recargar la vista para mostrar los nuevos resultados.
        """
        # Asegura que se está trabajando sobre un único registro. Es una buena práctica en Odoo.
        self.ensure_one()

        # Limpia los campos de resultados antes de cada nueva búsqueda para evitar mostrar datos anteriores.
        self.write({
            'found': False,
            'result_name': '', 'result_id': 0,
            'height_cm': 0, 'weight_kg': 0, 'poke_types': '',
            'item_cost': 0, 'item_effect': '',
            'sprite_front': False, 'sprite_back': False,
        })

        # Normaliza el término de búsqueda para que sea compatible con la API (minúsculas y sin espacios extra).
        query = self.search_name.strip().lower()
        if not query:
            # Si el campo de búsqueda está vacío, no se hace la llamada a la API.
            # Simplemente se recarga la vista para que el usuario vea los campos limpios.
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }

        # Construye la URL de la API basándose en el tipo de búsqueda seleccionado.
        base_url = 'https://pokeapi.co/api/v2'
        endpoint = 'pokemon' if self.search_type == 'pokemon' else 'item'
        api_url = f'{base_url}/{endpoint}/{query}'

        try:
            # Realiza la llamada a la API con un tiempo de espera para evitar que el sistema se bloquee.
            response = requests.get(api_url, timeout=10)

            # Si el recurso no se encuentra (código 404), informa al usuario de manera clara.
            if response.status_code == 404:
                raise UserError(f"No se encontró '{query}' en la categoría '{self.search_type}'.")

            # Lanza una excepción para otros errores HTTP (ej. 500 Internal Server Error, 403 Forbidden).
            response.raise_for_status()

            # Convierte la respuesta de la API (en formato texto) a un diccionario de Python.
            data = response.json()

            # Prepara un diccionario con los valores comunes obtenidos de la API.
            vals = {
                'found': True,
                'result_name': data.get('name', '').replace('-', ' ').title(),
                'result_id': data.get('id'),
            }

            # Si la búsqueda es de un Pokémon, extrae y procesa sus datos específicos.
            if self.search_type == 'pokemon':
                vals.update({
                    'height_cm': data.get('height', 0) * 10,  # La API da la altura en decímetros.
                    'weight_kg': data.get('weight', 0) / 10.0,  # La API da el peso en hectogramos.
                    'poke_types': ", ".join([t['type']['name'].capitalize() for t in data.get('types', [])]),
                    'sprite_front': self._fetch_image(data.get('sprites', {}).get('front_default')),
                    'sprite_back': self._fetch_image(data.get('sprites', {}).get('back_default')),
                })

            # Si la búsqueda es de un objeto o baya, extrae sus datos correspondientes.
            elif self.search_type == 'item':
                # Busca la descripción del efecto en español para una mejor experiencia de usuario.
                effect_text = "Sin descripción."
                for entry in data.get('effect_entries', []):
                    if entry.get('language', {}).get('name') == 'es':
                        effect_text = entry.get('short_effect', effect_text)
                        break

                vals.update({
                    'item_cost': data.get('cost', 0),
                    'item_effect': effect_text,
                    'sprite_front': self._fetch_image(data.get('sprites', {}).get('default')),
                })

            # Escribe todos los valores calculados en el asistente actual para mostrarlos en la vista.
            self.write(vals)

        except requests.exceptions.RequestException as e:
            # Captura errores de red (ej. sin conexión a internet) y los muestra al usuario.
            raise UserError(f"Error de red al conectar con PokeAPI: {e}")

        # Recarga la vista del asistente para asegurar que los cambios se muestren correctamente.
        # Este es el enfoque estándar en Odoo para actualizar la misma ventana modal.
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
