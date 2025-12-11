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
        1. Limpiar las imágenes.
        2. Construir y realizar la llamada a la API.
        3. Procesar la respuesta y preparar los datos.
        4. Crear un *nuevo* asistente con los resultados y recargar la vista.
        5. Manejar errores de conexión o si no se encuentra el recurso.
        """
        # Limpia las imágenes al inicio de cada búsqueda.
        self.sprite_front = False
        self.sprite_back = False

        # Normaliza el término de búsqueda para que sea compatible con la API.
        query = self.search_name.strip().lower()

        # Construye la URL de la API basándose en el tipo de búsqueda.
        base_url = 'https://pokeapi.co/api/v2'
        endpoint = 'pokemon' if self.search_type == 'pokemon' else 'item'
        api_url = f'{base_url}/{endpoint}/{query}'

        try:
            # Realiza la llamada a la API.
            response = requests.get(api_url, timeout=10)

            # Manejo de errores de la respuesta HTTP.
            if response.status_code == 404:
                raise UserError(f"No se encontró nada con el nombre '{query}' en la categoría {self.search_type.capitalize()}.")
            if response.status_code != 200:
                raise UserError("Hubo un error de conexión con la PokeAPI.")

            # Convierte la respuesta a formato JSON.
            data = response.json()

            # 1. INICIALIZACIÓN Y LIMPIEZA
            # Se prepara un diccionario 'vals' que contendrá todos los datos del nuevo asistente.
            # Limpiar todos los campos es crucial para no mostrar datos de búsquedas anteriores.
            vals = {
                'sprite_front': False, 'sprite_back': False,
                'search_type': self.search_type,
                'search_name': self.search_name,
                'found': True,
                'result_name': data['name'].replace('-', ' ').title(),
                'result_id': data['id'],

                # Limpieza explícita de campos específicos de cada tipo.
                'height_cm': 0, 'weight_kg': 0, 'poke_types': False,
                'item_cost': 0, 'item_effect': False,
            }

            # 2. RELLENADO ESPECÍFICO
            # Dependiendo del tipo de búsqueda, se actualiza el diccionario 'vals' con los datos correspondientes.
            if self.search_type == 'pokemon':
                poke_types = ", ".join([t['type']['name'].capitalize() for t in data['types']])
                vals.update({
                    # En la lógica original, estas dos líneas se consideraron redundantes, ya que 'vals'
                    # ya contenía estos valores. Se incluyen aquí para mantener el código original intacto.
                    # Su propósito era asegurar que las imágenes estuvieran vacías antes de intentar obtener las nuevas.
                    'sprite_front': False,
                    'sprite_back': False,
                    'height_cm': data['height'] * 10,  # La API da la altura en decímetros.
                    'weight_kg': data['weight'] / 10.0,  # La API da el peso en hectogramos.
                    'poke_types': poke_types,
                    'sprite_front': self._fetch_image(data['sprites']['front_default']),
                    'sprite_back': self._fetch_image(data['sprites']['back_default']),
                })

            elif self.search_type == 'item':
                # Busca la descripción del efecto en español.
                effect_text = "Sin descripción"
                if 'effect_entries' in data and data['effect_entries']:
                    for entry in data['effect_entries']:
                        if entry['language']['name'] == 'es':
                            effect_text = entry['short_effect']

                vals.update({
                    'item_cost': data.get('cost', 0),
                    'item_effect': effect_text,
                    'sprite_front': self._fetch_image(data['sprites']['default']),
                })

            # 3. CREACIÓN Y RETORNO DE ACCIÓN
            # Se crea un nuevo registro del asistente con los datos recopilados.
            # Este enfoque (crear un nuevo wizard) es una forma de asegurar que la vista se
            # recargue completamente, evitando problemas de caché y mostrando siempre datos frescos.
            new_wizard = self.create(vals)

            # Se retorna una acción de ventana para abrir el nuevo asistente en un diálogo modal.
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'poke.wizard',
                'view_mode': 'form',
                'res_id': new_wizard.id,
                'target': 'new',
            }

        except requests.exceptions.RequestException as e:
            # Captura errores de red y los muestra al usuario.
            raise UserError(f"Error de red al conectar con PokeAPI: {e}")
