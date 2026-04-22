import hmac
import base64
import hashlib
import html
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import sqlite3
import threading
import time
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import requests
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_DIR = os.path.join(BASE_DIR, 'tmp')
DB_PATH = os.path.join(TMP_DIR, 'conversation_state.db')
LOG_PATH = os.path.join(BASE_DIR, 'webhook_debug.log')
os.makedirs(TMP_DIR, exist_ok=True)


def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip()


load_env_file(os.path.join(BASE_DIR, '.env'))

REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT_SECONDS', '20'))
PRODUCT_LIMIT = int(os.getenv('PRODUCT_LIST_LIMIT', '10'))
SESSION_TTL_SECONDS = int(os.getenv('SESSION_TTL_SECONDS', '21600'))
NOISE_LONG_TEXT_LENGTH = int(os.getenv('NOISE_LONG_TEXT_LENGTH', '220'))
NOISE_TOKEN_THRESHOLD = int(os.getenv('NOISE_TOKEN_THRESHOLD', '35'))
WEBHOOK_SECRET = os.getenv('ZENDER_WEBHOOK_SECRET', '')
UNO_API_BASE = os.getenv('UNO_API_BASE', 'https://uno.cobol.com.co/api').rstrip('/')
UNO_API_SECRET = os.getenv('UNO_API_SECRET', '')
UNO_WA_ACCOUNT = os.getenv('UNO_WA_ACCOUNT', '')
WC_BASE_URL = os.getenv('WC_BASE_URL', '').rstrip('/')
WC_CONSUMER_KEY = os.getenv('WC_CONSUMER_KEY', '')
WC_CONSUMER_SECRET = os.getenv('WC_CONSUMER_SECRET', '')
WC_API_VERSION = os.getenv('WC_API_VERSION', 'wc/v3')
WC_QUERY_STRING_AUTH = os.getenv('WC_QUERY_STRING_AUTH', '1').strip().lower() not in {'0', 'false', 'no'}
WC_WEBHOOK_SECRET = os.getenv('WC_WEBHOOK_SECRET', '').strip()
WC_UPSELL_LIMIT = max(0, int(os.getenv('WC_UPSELL_LIMIT', '2')))
DEFAULT_COUNTRY = os.getenv('DEFAULT_COUNTRY', 'CO')
PRICING_RULES_URL = os.getenv('PRICING_RULES_URL', '').strip()
PRICING_RULES_CACHE_SECONDS = int(os.getenv('PRICING_RULES_CACHE_SECONDS', '300'))
DB_LOCK = threading.Lock()
CATEGORY_CACHE = {}
PRICING_RULES_CACHE = {'expires_at': 0, 'value': None}
MONEY_PLACES = Decimal('0.01')
ORDER_STATUS_COPY = {
    'pending': {
        'emoji': '🟡',
        'label': 'Pendiente de confirmación',
        'body': 'Tu pedido fue recibido y quedó pendiente de confirmación. Te iré avisando cualquier novedad por aquí.',
    },
    'processing': {
        'emoji': '⚙️',
        'label': 'Procesando',
        'body': 'Tu pedido ya está en proceso. Estamos avanzando con la gestión para entregártelo lo antes posible.',
    },
    'on-hold': {
        'emoji': '⏸️',
        'label': 'En espera',
        'body': 'Tu pedido quedó en espera por el momento. En cuanto tengamos una novedad, te escribimos por aquí.',
    },
    'completed': {
        'emoji': '✅',
        'label': 'Completado',
        'body': 'Tu pedido fue completado. Gracias por comprar con nosotros.',
    },
    'cancelled': {
        'emoji': '❌',
        'label': 'Cancelado',
        'body': 'Tu pedido fue cancelado. Si quieres retomarlo o ver otras opciones, escríbeme MENU y te ayudo.',
    },
    'refunded': {
        'emoji': '💸',
        'label': 'Reembolsado',
        'body': 'Tu pedido fue reembolsado. Si quieres, también puedo ayudarte a encontrar otra opción.',
    },
}

CATEGORIES = {
    'tecnologia': {'label': '\U0001F4BB Tecnología', 'slug': 'tecnologia', 'aliases': ['tecnologia', 'tech', 'gadgets', 'electronica']},
    'hogar': {'label': '\U0001F3E0 Hogar', 'slug': 'hogar', 'aliases': ['hogar', 'casa', 'home']},
    'cuidado': {'label': '\U0001F9F4 Cuidado', 'slug': 'cuidado', 'aliases': ['cuidado', 'cuidado personal', 'belleza']},
    'herramientas': {'label': '\U0001F6E0 Herramientas', 'slug': 'herramientas', 'aliases': ['herramientas', 'herramienta', 'tool', 'tools']},
    'videojuegos': {'label': '\U0001F3AE Videojuegos', 'slug': 'videojuegos', 'aliases': ['videojuegos', 'videojuego', 'gaming', 'consola', 'consolas']},
    'salud': {'label': '\U0001FA7A Salud', 'slug': 'salud', 'aliases': ['salud', 'bienestar', 'health']},
}
MENU_WORDS = {'menu', 'inicio', 'hola', 'buenas', 'catalogo', 'categorias'}
RESET_WORDS = {'reiniciar', 'cancelar', 'salir'}
SKIP_WORDS = {'omitir', 'ninguno', 'ninguna', 'sin observaciones', 'na', 'n/a'}
BUY_WORDS = {'comprar', 'lo quiero', 'quiero este', 'pedir', 'checkout', 'si'}
COLOR_HINTS = {'color', 'colour', 'pa color', 'pa_color', 'colores'}
GREETING_TOKENS = {'hola', 'holi', 'hello', 'hi', 'buenas', 'buenos', 'dias', 'tardes', 'noches', 'ola', 'alo', 'hey'}
MENU_FILLER_TOKENS = GREETING_TOKENS | {'por', 'favor', 'menu', 'inicio', 'catalogo', 'categorias', 'categoria', 'productos', 'producto', 'bot', 'asesor'}
CHECKOUT_ABSOLUTE_QTY_WORDS = {'cantidad', 'cant', 'unidad', 'unidades', 'quiero', 'llevo', 'llevar', 'poner', 'ponlo', 'ponla', 'ponme', 'cambiar', 'cambialo', 'cambiala', 'dejalo', 'dejala', 'serian', 'seria'}
CHECKOUT_ADD_QTY_WORDS = {'agrega', 'agregar', 'suma', 'sumale', 'sube', 'subelo', 'subela', 'aumenta', 'aumentale', 'incrementa', 'incrementale', 'mas'}
CHECKOUT_REMOVE_QTY_WORDS = {'quita', 'quitar', 'resta', 'restale', 'baja', 'bajalo', 'bajala', 'reduce', 'reducelo', 'reducela', 'menos'}
CHECKOUT_REMOVE_PRODUCT_WORDS = {'no quiero', 'ya no quiero', 'quitar', 'quita', 'elimina', 'borra', 'cancela', 'descarta', 'sacar', 'saca'}
SEARCH_STOP_WORDS = {
    'a', 'al', 'con', 'de', 'del', 'el', 'en', 'esta', 'este', 'estos', 'esta', 'estas', 'favor', 'hola',
    'info', 'informacion', 'interesa', 'interesan', 'la', 'las', 'lo', 'los', 'me', 'mi', 'para', 'por',
    'producto', 'productos', 'que', 'quiero', 'quisiera', 'sobre', 'tienen', 'tienes', 'un', 'una', 'uno',
    'unas', 'unos', 'ver', 'verlo', 'verla', 'verlos', 'verlas', 'yo'
}
QUERY_PREFIX_PATTERNS = [
    r'^(quiero ver|quiero comprar|quiero pedir|me gustaria ver|me gustaria)\b',
    r'^(dame info de|dame informacion de|informacion de|info de|me podrias mostrar)\b',
    r'^(hola|holi|hello|hi|hey|ola|alo)\b',
    r'^(buenos dias|buenas tardes|buenas noches|buenas)\b',
    r'^(oye|ey|disculpa|por favor)\b',
    r'^(me interesa(n)?|estoy interesado(a)? en|estoy buscando|quiero|quisiera|busco|necesito)\b',
    r'^(tienes|tienen)\b',
]
CATALOG_PRODUCT_HINTS = [
    'Extractor de Jugos',
    'Estufa Electrica de Mesa',
    'Estufa Electrica de Mesa 2 Puestos',
    'Almohadas Ergonomicas',
    'Maquina de hacer palomitas',
    'Set de Cocina 19 Utensilios',
    'Aspiradora de Mano Potente',
    'Panalera Cuna Premium',
    'Canastilla de Esponjas para Platos',
    'Pocillo tipo Termo Stanley',
    'Licuadora Portatil',
    'Mini Wafflera',
    'Prensa Cafetera Francesa',
    'Termo para Camping',
    'Set de Especieros',
    'Portacajonera Portatil',
    'Afila Cuchillos',
    'Maquina para hacer Donas',
    'Hervidor de Huevos Electrico',
    'Bascula Digital',
    'Purificador de Agua',
    'Organizador de Pared',
    'Limpia Vidros Magnetico',
    'Android TV Stick',
    'Trampa LED Anti Mosquitos',
    'Intercomunicador Moto Q58 MAX',
    'Proyector HD con Control Remoto',
    'Adaptador Inalambrico CarPlay & Android Auto 2 en 1',
    'Kit de 2 Walkie Talkies Baofeng BF-888S',
    'Parlante para Ducha',
    'Altavoz LED con Cargador Inalambrico',
    'Secador de Cabello Profesional',
    'Masaje Gun + Accesorios',
    'Cepillo Electrico Multifuncion 5 en 1',
    'Combo Belleza 3 en 1',
    'Cepillo Alisador 5 Niveles',
    'Combo Cabello Perfecto',
    'Masajeador Facial Rejuvenecedor',
    'Kit Fortalecedor de Mano',
    'Cepillo Dental Electrico Sonico Recargable',
    'Compresor Portatil Digital Inalambrico Recargable',
    'Hidrolavadora Boquilla 6 En 1 Inalambrica Portatil Dos Baterias',
    'Combo Herramientas Taladro DeWalt Inalambrico 34 Piezas',
    'Taladro Inalambrico 48V Con Kit Destornillador 2 Baterias',
    'Combo Entretenimiento Proyector + 2 Mandos Inalambricos',
    'Rodillera Termica Electrica',
    'Oximetro Digital',
    'Oximetro Digital Pediatrico',
    'Balanza Digital Inteligente',
]
CATALOG_QUERY_ALIASES = {
    'palomitera': 'Maquina de hacer palomitas',
    'popcorn': 'Maquina de hacer palomitas',
    'stanley': 'Pocillo tipo Termo Stanley',
    'termo stanley': 'Pocillo tipo Termo Stanley',
    'speaker ducha': 'Parlante para Ducha',
    'parlante ducha': 'Parlante para Ducha',
    'walkie': 'Kit de 2 Walkie Talkies Baofeng BF-888S',
    'walkie talkie': 'Kit de 2 Walkie Talkies Baofeng BF-888S',
    'walkie talkies': 'Kit de 2 Walkie Talkies Baofeng BF-888S',
    'baofeng': 'Kit de 2 Walkie Talkies Baofeng BF-888S',
    'dewalt': 'Combo Herramientas Taladro DeWalt Inalambrico 34 Piezas',
    'taladro dewalt': 'Combo Herramientas Taladro DeWalt Inalambrico 34 Piezas',
    'carplay': 'Adaptador Inalambrico CarPlay & Android Auto 2 en 1',
    'android auto': 'Adaptador Inalambrico CarPlay & Android Auto 2 en 1',
    'medidor de oxigeno': 'Oximetro Digital',
    'saturacion': 'Oximetro Digital',
    'saturacion oxigeno': 'Oximetro Digital',
    'oximetro pediatrico': 'Oximetro Digital Pediatrico',
    'pesa': 'Bascula Digital',
    'bascula': 'Bascula Digital',
    'balanza': 'Balanza Digital Inteligente',
    'rodillera': 'Rodillera Termica Electrica',
    'hidrolavadora': 'Hidrolavadora Boquilla 6 En 1 Inalambrica Portatil Dos Baterias',
    'compresor': 'Compresor Portatil Digital Inalambrico Recargable',
}
CUSTOMER_SERVICE_TOKENS = {
    'precio', 'precios', 'valor', 'vale', 'cuesta', 'costo', 'costos', 'envio', 'entrega', 'domicilio',
    'catalogo', 'producto', 'productos', 'comprar', 'compra', 'quiero', 'interesa', 'pedido', 'pedir',
    'contra', 'pago', 'efectivo', 'disponible', 'disponibilidad', 'stock',
}
NUMBER_WORDS = {
    'un': 1, 'uno': 1, 'una': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5,
    'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10, 'once': 11,
    'doce': 12, 'trece': 13, 'catorce': 14, 'quince': 15, 'dieciseis': 16,
    'diecisiete': 17, 'dieciocho': 18, 'diecinueve': 19, 'veinte': 20,
}


def load_json_env(name, default):
    raw = os.getenv(name, '').strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        app.logger.warning('Invalid JSON in %s', name)
        return default


ACCOUNT_MAP = load_json_env('UNO_ACCOUNT_MAP_JSON', {})
CATEGORY_ID_MAP = load_json_env('WC_CATEGORY_IDS_JSON', {})
DEFAULT_PRICING_RULES = {
    'basis': 'current_price',
    'tiers': [
        {'min_qty': 2, 'max_qty': 2, 'discount_pct': 5},
        {'min_qty': 3, 'discount_pct': 10},
    ],
}
STATIC_PRICING_RULES = load_json_env('BOT_DISCOUNT_RULES_JSON', DEFAULT_PRICING_RULES)
DEFAULT_SHIPPING_RULES = {
    'bogota_cost': 8000,
    'principal_cost': 12000,
    'national_cost': 20000,
    'free_shipping_threshold': 200000,
    'free_shipping_regions': ['bogota', 'principal'],
    'bogota_aliases': ['bogota', 'bogota dc', 'bogota d.c', 'bogota d.c.'],
    'principal_cities': [
        'medellin', 'cali', 'barranquilla', 'cartagena', 'bucaramanga', 'cucuta',
        'pereira', 'manizales', 'santa marta', 'ibague', 'villavicencio', 'pasto',
        'armenia', 'monteria', 'neiva', 'soledad', 'bello'
    ],
}
STATIC_SHIPPING_RULES = load_json_env('BOT_SHIPPING_RULES_JSON', DEFAULT_SHIPPING_RULES)


def setup_logging():
    if app.logger.handlers:
        return
    handler = RotatingFileHandler(LOG_PATH, maxBytes=512000, backupCount=2)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def init_db():
    with DB_LOCK:
        connection = sqlite3.connect(DB_PATH)
        try:
            cur = connection.cursor()
            cur.execute('CREATE TABLE IF NOT EXISTS conversations (phone TEXT PRIMARY KEY, state TEXT NOT NULL, data TEXT NOT NULL, updated_at INTEGER NOT NULL)')
            cur.execute('CREATE TABLE IF NOT EXISTS processed_events (event_key TEXT PRIMARY KEY, processed_at INTEGER NOT NULL)')
            cur.execute('CREATE TABLE IF NOT EXISTS order_tracking (order_id TEXT PRIMARY KEY, last_status TEXT NOT NULL, last_note_key TEXT NOT NULL, updated_at INTEGER NOT NULL)')
            connection.commit()
        finally:
            connection.close()
    cleanup_expired_rows()


def db_conn():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def now_ts():
    return int(time.time())


def cleanup_expired_rows():
    if SESSION_TTL_SECONDS <= 0:
        return
    cutoff = now_ts() - SESSION_TTL_SECONDS
    with DB_LOCK:
        connection = db_conn()
        try:
            connection.execute('DELETE FROM conversations WHERE updated_at < ?', (cutoff,))
            connection.commit()
        finally:
            connection.close()


def default_session(phone):
    return {
        'state': 'idle',
        'category': None,
        'last_products': [],
        'last_variations': [],
        'product': None,
        'variation': None,
        'quantity': 1,
        'checkout': {'customer_phone': phone, 'full_name': '', 'city': '', 'address_1': '', 'address_2': '', 'notes': ''},
    }


def load_session(phone):
    with DB_LOCK:
        connection = db_conn()
        try:
            row = connection.execute('SELECT data, updated_at FROM conversations WHERE phone = ?', (phone,)).fetchone()
        finally:
            connection.close()
    if not row:
        return default_session(phone)
    if SESSION_TTL_SECONDS > 0 and row['updated_at'] < now_ts() - SESSION_TTL_SECONDS:
        return default_session(phone)
    try:
        session = json.loads(row['data'])
    except json.JSONDecodeError:
        return default_session(phone)
    session.setdefault('checkout', default_session(phone)['checkout'])
    session['checkout']['customer_phone'] = phone
    return session


def save_session(phone, session):
    payload = json.dumps(session, ensure_ascii=True)
    with DB_LOCK:
        connection = db_conn()
        try:
            connection.execute("INSERT INTO conversations (phone, state, data, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(phone) DO UPDATE SET state=excluded.state, data=excluded.data, updated_at=excluded.updated_at", (phone, session.get('state', 'idle'), payload, now_ts()))
            connection.commit()
        finally:
            connection.close()


def reset_session(phone):
    session = default_session(phone)
    save_session(phone, session)
    return session


def event_seen(key):
    if not key:
        return False
    with DB_LOCK:
        connection = db_conn()
        try:
            row = connection.execute('SELECT event_key FROM processed_events WHERE event_key = ?', (key,)).fetchone()
        finally:
            connection.close()
    return row is not None


def mark_event(key):
    if not key:
        return
    with DB_LOCK:
        connection = db_conn()
        try:
            connection.execute('INSERT OR REPLACE INTO processed_events (event_key, processed_at) VALUES (?, ?)', (key, now_ts()))
            connection.commit()
        finally:
            connection.close()


def order_tracking(order_id):
    if not order_id:
        return {'last_status': '', 'last_note_key': ''}
    with DB_LOCK:
        connection = db_conn()
        try:
            row = connection.execute('SELECT last_status, last_note_key FROM order_tracking WHERE order_id = ?', (str(order_id),)).fetchone()
        finally:
            connection.close()
    if not row:
        return {'last_status': '', 'last_note_key': ''}
    return {'last_status': row['last_status'] or '', 'last_note_key': row['last_note_key'] or ''}


def save_order_tracking(order_id, status=None, note_key=None):
    if not order_id:
        return
    current = order_tracking(order_id)
    last_status = current['last_status'] if status is None else clean(status)
    last_note_key = current['last_note_key'] if note_key is None else clean(note_key)
    with DB_LOCK:
        connection = db_conn()
        try:
            connection.execute(
                "INSERT INTO order_tracking (order_id, last_status, last_note_key, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(order_id) DO UPDATE SET last_status=excluded.last_status, last_note_key=excluded.last_note_key, updated_at=excluded.updated_at",
                (str(order_id), last_status, last_note_key, now_ts()),
            )
            connection.commit()
        finally:
            connection.close()


def norm(value):
    if not value:
        return ''
    text = unicodedata.normalize('NFKD', str(value))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', text.replace('_', ' ')).strip().lower()


def clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def tokens(value):
    return re.findall(r'[a-z0-9]+', norm(value))


def unique_texts(items):
    seen = set()
    values = []
    for item in items:
        text = clean(item)
        key = norm(text)
        if not key or key in seen:
            continue
        seen.add(key)
        values.append(text)
    return values


def strip_html(value):
    text = re.sub(r'<[^>]+>', ' ', str(value or ''))
    return re.sub(r'\s+', ' ', html.unescape(text)).strip()


def price_label(raw):
    if raw in (None, '', False):
        return 'Precio por confirmar'
    try:
        value = float(str(raw).replace(',', '.'))
    except ValueError:
        return str(raw)
    if value.is_integer():
        return f"${int(value):,}".replace(',', '.')
    return f"${value:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')


def money_decimal(raw):
    if raw in (None, '', False):
        return Decimal('0')
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def money_round(value):
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def money_string(value):
    return format(money_round(value), 'f')


def percent_string(value):
    try:
        numeric = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    text = format(numeric.normalize(), 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def normalize_pricing_rules(raw_rules):
    rules = raw_rules if isinstance(raw_rules, dict) else DEFAULT_PRICING_RULES
    tiers = []
    for raw_tier in rules.get('tiers', []):
        if not isinstance(raw_tier, dict):
            continue
        min_qty = raw_tier.get('min_qty')
        if min_qty in (None, ''):
            continue
        try:
            min_qty = int(min_qty)
            max_qty = int(raw_tier['max_qty']) if raw_tier.get('max_qty') not in (None, '') else None
            discount_pct = Decimal(str(raw_tier.get('discount_pct', 0)))
        except (ValueError, InvalidOperation):
            continue
        tiers.append({'min_qty': min_qty, 'max_qty': max_qty, 'discount_pct': discount_pct})
    if not tiers:
        tiers = normalize_pricing_rules(DEFAULT_PRICING_RULES)['tiers']
    return {'basis': rules.get('basis', 'current_price'), 'tiers': sorted(tiers, key=lambda item: item['min_qty'])}


def pricing_rules():
    if PRICING_RULES_URL:
        now = now_ts()
        cached = PRICING_RULES_CACHE.get('value')
        if cached and PRICING_RULES_CACHE.get('expires_at', 0) > now:
            return cached
        try:
            response = requests.get(PRICING_RULES_URL, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            cached = normalize_pricing_rules(response.json())
            PRICING_RULES_CACHE['value'] = cached
            PRICING_RULES_CACHE['expires_at'] = now + PRICING_RULES_CACHE_SECONDS
            return cached
        except Exception as exc:
            app.logger.warning('Could not refresh pricing rules from %s: %s', PRICING_RULES_URL, exc)
            if cached:
                return cached
    return normalize_pricing_rules(STATIC_PRICING_RULES)


def discount_for_quantity(quantity):
    applicable = Decimal('0')
    for tier in pricing_rules()['tiers']:
        max_qty = tier.get('max_qty')
        if quantity >= tier['min_qty'] and (max_qty is None or quantity <= max_qty):
            applicable = tier['discount_pct']
    return applicable


def pricing_for(product, variation=None, quantity=1):
    base_product = product or {}
    chosen = variation or base_product
    base_unit = money_decimal(chosen.get('price') or chosen.get('regular_price') or base_product.get('price'))
    discount_pct = discount_for_quantity(quantity)
    discount_multiplier = Decimal('1') - (discount_pct / Decimal('100'))
    discounted_unit = money_round(base_unit * discount_multiplier)
    subtotal = money_round(base_unit * quantity)
    total = money_round(discounted_unit * quantity)
    savings = money_round(subtotal - total)
    return {
        'base_unit': base_unit,
        'discount_pct': discount_pct,
        'discounted_unit': discounted_unit,
        'subtotal': subtotal,
        'total': total,
        'savings': savings,
    }


def pricing_note():
    parts = []
    for tier in pricing_rules()['tiers']:
        if tier.get('max_qty') and tier['max_qty'] == tier['min_qty']:
            label = f"{tier['min_qty']} unidades"
        else:
            label = f"{tier['min_qty']} o más"
        parts.append(f"{label}: {percent_string(tier['discount_pct'])}% OFF")
    if not parts:
        return ''
    return '🎁 Promo por cantidad sobre el precio rebajado vigente: ' + ' | '.join(parts)


def shipping_rules():
    rules = STATIC_SHIPPING_RULES if isinstance(STATIC_SHIPPING_RULES, dict) else DEFAULT_SHIPPING_RULES
    merged = dict(DEFAULT_SHIPPING_RULES)
    merged.update(rules)
    merged['free_shipping_regions'] = list(merged.get('free_shipping_regions', []))
    merged['bogota_aliases'] = [norm(item) for item in merged.get('bogota_aliases', [])]
    merged['principal_cities'] = [norm(item) for item in merged.get('principal_cities', [])]
    return merged


def shipping_region(city):
    normalized_city = norm(city)
    rules = shipping_rules()
    if normalized_city in rules['bogota_aliases']:
        return 'bogota'
    if normalized_city in rules['principal_cities']:
        return 'principal'
    return 'national'


def shipping_method_title(region):
    if region == 'bogota':
        return 'Envío Bogotá'
    if region == 'principal':
        return 'Envío Ciudades Principales'
    return 'Envío Nacional'


def shipping_note():
    rules = shipping_rules()
    threshold = price_label(rules['free_shipping_threshold'])
    return (
        f"🚚 Envío: Bogotá {price_label(rules['bogota_cost'])}, "
        f"ciudades principales {price_label(rules['principal_cost'])}, "
        f"nacional {price_label(rules['national_cost'])}. "
        f"Gratis desde {threshold} solo en Bogotá y ciudades principales."
    )


def shipping_for_city(city, products_total):
    rules = shipping_rules()
    region = shipping_region(city)
    if region == 'bogota':
        cost = Decimal(str(rules['bogota_cost']))
    elif region == 'principal':
        cost = Decimal(str(rules['principal_cost']))
    else:
        cost = Decimal(str(rules['national_cost']))

    threshold = Decimal(str(rules['free_shipping_threshold']))
    free_shipping = region in set(rules['free_shipping_regions']) and products_total >= threshold
    final_cost = Decimal('0') if free_shipping else cost
    return {
        'region': region,
        'method_title': shipping_method_title(region),
        'base_cost': money_round(cost),
        'cost': money_round(final_cost),
        'free_shipping': free_shipping,
        'threshold': threshold,
    }


def quote_totals(product, variation=None, quantity=1, city=''):
    pricing = pricing_for(product, variation=variation, quantity=quantity)
    shipping = shipping_for_city(city, pricing['total'])
    grand_total = money_round(pricing['total'] + shipping['cost'])
    return pricing, shipping, grand_total


def count_value_from_text(text):
    digit_match = re.search(r'\b(\d{1,2})\b', text or '')
    if digit_match:
        return int(digit_match.group(1))
    for token in tokens(text):
        if token in NUMBER_WORDS:
            return NUMBER_WORDS[token]
    return None


def qty_from(text):
    value = count_value_from_text(text)
    if value is None:
        return None
    return value if 1 <= value <= 99 else None


def choice_from(text):
    message = norm(text)
    if not message:
        return None
    match = re.match(r'^(?:(?:la|el)\s+)?(?:(?:opcion|numero|num|item|producto|referencia|color|variante|variacion)\s+)?#?\s*(\d{1,2})\s*[.)-]?$', message)
    if not match:
        return None
    value = int(match.group(1))
    return value if 1 <= value <= 99 else None


def checkout_quantity_update(text, current_quantity=1, allow_plain=False):
    message = norm(text)
    value = qty_from(text)
    if not message or value is None:
        return None
    if allow_plain and re.fullmatch(r'\d{1,2}', message):
        return value
    if re.search(r'\b(?:a|en)\s+(?:\d{1,2}|' + '|'.join(NUMBER_WORDS.keys()) + r')\b', message) and (
        any(word in message for word in CHECKOUT_ADD_QTY_WORDS)
        or any(word in message for word in CHECKOUT_REMOVE_QTY_WORDS)
        or any(word in message for word in CHECKOUT_ABSOLUTE_QTY_WORDS)
    ):
        return value
    if any(word in message for word in CHECKOUT_ADD_QTY_WORDS):
        return min(99, current_quantity + value)
    if any(word in message for word in CHECKOUT_REMOVE_QTY_WORDS):
        return max(1, current_quantity - value)
    if re.search(r'\b(unidad|unidades|cantidad)\b', message):
        return value
    if any(word in message for word in CHECKOUT_ABSOLUTE_QTY_WORDS):
        return value
    return None


def wants_remove_current_item(text, session):
    message = norm(text)
    if not message:
        return False
    if qty_from(text) is not None and any(word in message for word in CHECKOUT_REMOVE_QTY_WORDS):
        return False
    if not any(phrase in message for phrase in CHECKOUT_REMOVE_PRODUCT_WORDS):
        return False
    product = session.get('product') or {}
    variation = session.get('variation') or {}
    if 'producto' in message or 'pedido' in message or 'carrito' in message or 'este' in message or 'eso' in message:
        return True
    if product.get('name') and norm(product['name']) in message:
        return True
    if variation.get('label') and norm(variation['label']) in message:
        return True
    return message in CHECKOUT_REMOVE_PRODUCT_WORDS or message.startswith('no quiero')


def split_name(full_name):
    parts = clean(full_name).split()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], ' '.join(parts[1:])


def billing_email_for(checkout):
    raw_email = clean(checkout.get('email', ''))
    if raw_email and re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', raw_email):
        return raw_email
    phone_digits = re.sub(r'\D+', '', checkout.get('customer_phone', ''))
    if not phone_digits:
        phone_digits = f"guest{now_ts()}"
    return f"wa-{phone_digits}@bot.invalid"


def meta_value(meta_data, key, default=''):
    for item in meta_data or []:
        if clean(item.get('key')) == key:
            return item.get('value', default)
    return default


def category_key_for_product(product):
    reverse_map = {}
    if isinstance(CATEGORY_ID_MAP, dict):
        for key, value in CATEGORY_ID_MAP.items():
            try:
                reverse_map[int(value)] = key
            except (TypeError, ValueError):
                continue
    for category_id in product.get('category_ids', []):
        if category_id in reverse_map:
            return reverse_map[category_id]
    category_names = product.get('categories') or []
    for name in category_names:
        normalized_name = norm(name)
        for key, meta in CATEGORIES.items():
            if normalized_name == norm(meta['label']) or normalized_name == norm(meta['slug']):
                return key
    return None


def upsell_candidates(product, category_key=None, limit=None):
    limit = WC_UPSELL_LIMIT if limit is None else limit
    if limit <= 0 or not product:
        return []
    current_id = product.get('id')
    current_price = money_decimal(product.get('price'))
    preferred_keys = []
    for key in [category_key, category_key_for_product(product)]:
        if key and key not in preferred_keys:
            preferred_keys.append(key)
    candidates = []
    for key in preferred_keys:
        try:
            candidates = merge_products(candidates + list_products(key))
        except Exception as exc:
            app.logger.warning('Could not load upsell products for %s: %s', key, exc)
    candidates = [item for item in candidates if item.get('id') != current_id]
    if not candidates:
        return []

    target_price = current_price * Decimal('1.15') if current_price > 0 else Decimal('0')

    def sort_key(item):
        price = money_decimal(item.get('price'))
        if current_price > 0:
            above_current = 0 if price >= current_price else 1
            distance = abs(price - target_price)
            return (above_current, distance, -price)
        return (0, Decimal('0'), -price)

    return sorted(candidates, key=sort_key)[:limit]


def upsell_lines(product, category_key=None, limit=None, mode='browse'):
    suggestions = upsell_candidates(product, category_key=category_key, limit=limit)
    if not suggestions:
        return []
    if mode == 'post_purchase':
        lines = ['', '✨ También podría interesarte:']
    else:
        lines = ['', '✨ También podría interesarte:']
    for item in suggestions:
        lines.append(f"• {item['name']} - {item['price_label']}")
    if mode == 'post_purchase':
        lines.append('Si quieres ver alguno, escríbeme MENU y te muestro más opciones.')
    return lines


def order_phone(order):
    if not isinstance(order, dict):
        return ''
    meta_data = order.get('meta_data') or []
    for key in ['_zender_customer_phone', '_billing_phone']:
        value = clean(meta_value(meta_data, key))
        if value:
            return value
    billing = order.get('billing') or {}
    return clean(billing.get('phone') or '')


def order_number(order):
    if not isinstance(order, dict):
        return ''
    return clean(order.get('number') or order.get('id') or '')


def order_product_summary(order):
    items = order.get('line_items') or []
    names = [clean(item.get('name')) for item in items if clean(item.get('name'))]
    if not names:
        return ''
    if len(names) == 1:
        return names[0]
    return f"{names[0]} y {len(names) - 1} producto(s) más"


def order_status_message(order, status):
    info = ORDER_STATUS_COPY.get(status)
    if not info:
        return ''
    number = order_number(order)
    product_summary = order_product_summary(order)
    payment_title = clean(order.get('payment_method_title') or '')
    total = price_label(order.get('total'))
    lines = [
        f"{info['emoji']} Actualización de tu pedido #{number}",
        f"📌 Estado: {info['label']}",
    ]
    if product_summary:
        lines.append(f"📦 Pedido: {product_summary}")
    if total:
        lines.append(f"💰 Total: {total}")
    if payment_title:
        lines.append(f"💵 Pago: {payment_title}")
    lines.append(info['body'])
    if status in {'completed', 'cancelled', 'refunded'}:
        lines.append('✨ Si quieres ver más productos o retomar otra compra, escríbeme MENU.')
    return '\n'.join(lines)


def customer_note_message(order_number_value, note_text):
    lines = [
        f"📝 Novedad sobre tu pedido #{order_number_value}",
        strip_html(note_text),
        'Si necesitas ayuda adicional, puedes responder por este mismo chat.',
    ]
    return '\n'.join(line for line in lines if clean(line))


def category_for(message):
    text = norm(message)
    for key, meta in CATEGORIES.items():
        for alias in meta['aliases']:
            alias_text = norm(alias)
            if text == alias_text or alias_text in text:
                return key
    return None


def is_menu_request(message):
    text = norm(message)
    if not text or text in MENU_WORDS:
        return True
    message_tokens = tokens(text)
    return bool(message_tokens) and all(token in MENU_FILLER_TOKENS for token in message_tokens)


def has_sales_signal(message):
    text = clean(message)
    normalized = norm(text)
    if not normalized:
        return False
    if is_menu_request(text):
        return True
    if category_for(text):
        return True
    if any(word in normalized for word in BUY_WORDS):
        return True
    if any(token in tokens(text) for token in CUSTOMER_SERVICE_TOKENS):
        return True
    compact = compact_search_query(text)
    compact_text = norm(compact)
    for alias in CATALOG_QUERY_ALIASES:
        alias_text = norm(alias)
        if alias_text and (alias_text in normalized or alias_text in compact_text):
            return True
    for hint in CATALOG_PRODUCT_HINTS:
        hint_text = norm(hint)
        if hint_text and (hint_text in normalized or hint_text in compact_text):
            return True
    return False


def is_likely_noise_message(message, attachment=''):
    text = clean(message)
    if not text:
        return False
    if has_sales_signal(text):
        return False
    token_count = len(tokens(text))
    char_count = len(text)
    line_breaks = str(message or '').count('\n')
    has_url = bool(re.search(r'https?://|www\.', text, re.IGNORECASE))
    if has_url and (char_count >= NOISE_LONG_TEXT_LENGTH or line_breaks >= 2):
        return True
    if token_count >= NOISE_TOKEN_THRESHOLD and char_count >= NOISE_LONG_TEXT_LENGTH:
        return True
    if attachment and (has_url or token_count >= NOISE_TOKEN_THRESHOLD):
        return True
    return False


def strip_query_prefixes(message):
    text = norm(message)
    previous = None
    while text and text != previous:
        previous = text
        for pattern in QUERY_PREFIX_PATTERNS:
            text = re.sub(pattern, '', text).strip(" ,.-:;")
    return text


def compact_search_query(message):
    base = strip_query_prefixes(message)
    if not base:
        return ''
    filtered = [token for token in tokens(base) if token not in SEARCH_STOP_WORDS]
    if filtered:
        return ' '.join(filtered)
    return base


def catalog_alias_candidates(message):
    text = norm(message)
    compact = compact_search_query(message)
    query_tokens = [token for token in tokens(compact or text) if token not in SEARCH_STOP_WORDS]
    if not query_tokens:
        return []

    alias_hits = []
    for alias, target in CATALOG_QUERY_ALIASES.items():
        alias_text = norm(alias)
        alias_tokens = tokens(alias_text)
        if alias_text in text or alias_text in compact:
            alias_hits.append(target)
            continue
        if alias_tokens and all(token in text for token in alias_tokens):
            alias_hits.append(target)

    scored_hints = []
    for hint in CATALOG_PRODUCT_HINTS:
        hint_text = norm(hint)
        hint_tokens = set(tokens(hint))
        overlap = [token for token in query_tokens if token in hint_tokens]
        if compact and (compact in hint_text or hint_text in compact):
            score = 100 + len(overlap)
        elif overlap and (len(overlap) >= len(query_tokens) or len(overlap) >= 2 or any(len(token) >= 5 for token in overlap)):
            score = len(overlap) * 10 + sum(len(token) for token in overlap)
        else:
            continue
        scored_hints.append((score, hint))

    scored_hints.sort(key=lambda item: item[0], reverse=True)
    hint_hits = [hint for _, hint in scored_hints[:3]]
    return unique_texts(alias_hits + hint_hits)


def search_candidates(message):
    raw_text = clean(message)
    stripped = strip_query_prefixes(message)
    compact = compact_search_query(message)
    return unique_texts([raw_text, stripped, compact, *catalog_alias_candidates(message)])


def menu_text():
    lines = [
        'Hola, soy tu asistente virtual de ventas.',
        'Estoy aquí para ayudarte a encontrar productos, resolver dudas y tomar tu pedido en pocos pasos.',
        '',
        '🗂️ Categorías disponibles:',
    ]
    for key in CATEGORIES:
        lines.append(f"• {CATEGORIES[key]['label']}")
    lines.extend([
        '',
        'Puedes escribirme una categoría como Tecnología o el nombre del producto que viste en la publicidad.',
        'En cualquier momento escribe MENU para volver al inicio.',
    ])
    return '\n'.join(lines)

class IntegrationError(RuntimeError):
    pass


def outbound_account(hint=None):
    if hint and isinstance(ACCOUNT_MAP, dict) and ACCOUNT_MAP.get(hint):
        return ACCOUNT_MAP[hint]
    return UNO_WA_ACCOUNT or hint or ''


def require_wc():
    if not WC_BASE_URL:
        raise IntegrationError('WC_BASE_URL is missing.')
    if not WC_CONSUMER_KEY or not WC_CONSUMER_SECRET:
        raise IntegrationError('WooCommerce credentials are missing.')


def wc_auth_params(params=None):
    merged = dict(params or {})
    merged['consumer_key'] = WC_CONSUMER_KEY
    merged['consumer_secret'] = WC_CONSUMER_SECRET
    return merged


def require_uno(hint=None):
    if not UNO_API_SECRET:
        raise IntegrationError('UNO_API_SECRET is missing.')
    if not outbound_account(hint):
        raise IntegrationError('UNO_WA_ACCOUNT is missing.')


def wc_request(method, path, params=None, payload=None):
    require_wc()
    url = f"{WC_BASE_URL}/wp-json/{WC_API_VERSION}/{path.lstrip('/')}"
    request_params = dict(params or {})
    auth = None if WC_QUERY_STRING_AUTH else (WC_CONSUMER_KEY, WC_CONSUMER_SECRET)
    if WC_QUERY_STRING_AUTH:
        request_params = wc_auth_params(request_params)
    response = requests.request(method=method, url=url, params=request_params, json=payload, auth=auth, timeout=REQUEST_TIMEOUT)
    if response.status_code in {401, 403} and not WC_QUERY_STRING_AUTH:
        fallback_params = wc_auth_params(params)
        response = requests.request(method=method, url=url, params=fallback_params, json=payload, timeout=REQUEST_TIMEOUT)
    if response.status_code >= 400:
        raise IntegrationError(f"WooCommerce error {response.status_code}: {response.text[:250]}")
    return response.json() if response.text.strip() else {}


def uno_send(recipient, message, hint=None, image_url=None):
    require_uno(hint)
    account = outbound_account(hint)
    fields = [
        ('secret', (None, UNO_API_SECRET)),
        ('account', (None, account)),
        ('recipient', (None, recipient)),
        ('message', (None, message)),
        ('priority', (None, '1')),
    ]
    if image_url:
        fields.extend([('type', (None, 'media')), ('media_url', (None, image_url)), ('media_type', (None, 'image'))])
    else:
        fields.append(('type', (None, 'text')))
    response = requests.post(f"{UNO_API_BASE}/send/whatsapp", files=fields, timeout=REQUEST_TIMEOUT)
    if response.status_code >= 400:
        raise IntegrationError(f"UNO send error {response.status_code}: {response.text[:250]}")
    payload = response.json()
    if payload.get('status') != 200:
        raise IntegrationError(payload.get('message') or 'UNO send failed.')
    return payload


def category_id(key):
    if key in CATEGORY_CACHE:
        return CATEGORY_CACHE[key]

    configured_id = None
    if isinstance(CATEGORY_ID_MAP, dict):
        configured_id = CATEGORY_ID_MAP.get(key)

    if configured_id not in (None, ''):
        try:
            value = int(configured_id)
        except (TypeError, ValueError):
            raise IntegrationError(f"Invalid WooCommerce category ID for '{key}'.")
        CATEGORY_CACHE[key] = value
        return value

    data = wc_request('GET', 'products/categories', params={'slug': CATEGORIES[key]['slug'], 'per_page': 1})
    value = data[0]['id'] if data else None
    CATEGORY_CACHE[key] = value
    return value


def product_from(raw):
    return {
        'id': raw.get('id'),
        'name': raw.get('name', 'Producto'),
        'type': raw.get('type', 'simple'),
        'price': raw.get('price') or raw.get('regular_price') or '',
        'price_label': price_label(raw.get('price') or raw.get('regular_price')),
        'permalink': raw.get('permalink', ''),
        'image': (raw.get('images') or [{}])[0].get('src', ''),
        'stock_status': raw.get('stock_status', ''),
        'short_description': strip_html(raw.get('short_description') or raw.get('description') or ''),
        'category_ids': [item.get('id') for item in (raw.get('categories') or []) if item.get('id')],
        'categories': [clean(item.get('name')) for item in (raw.get('categories') or []) if clean(item.get('name'))],
    }


def list_products(category_key):
    params = {'status': 'publish', 'per_page': PRODUCT_LIMIT}
    cat_id = category_id(category_key)
    if cat_id:
        params['category'] = cat_id
    data = wc_request('GET', 'products', params=params)
    products = [product_from(item) for item in data]
    return [item for item in products if item['stock_status'] != 'outofstock']


def search_products(query):
    data = wc_request('GET', 'products', params={'status': 'publish', 'search': query, 'per_page': PRODUCT_LIMIT})
    products = [product_from(item) for item in data]
    return [item for item in products if item['stock_status'] != 'outofstock']


def merge_products(items):
    merged = []
    seen = set()
    for item in items:
        product_id = item.get('id')
        if not product_id or product_id in seen:
            continue
        seen.add(product_id)
        merged.append(item)
    return merged


def strong_product_match(text, items):
    if not items:
        return None
    raw_text = clean(text)
    raw_norm = norm(raw_text)
    stripped = strip_query_prefixes(text)
    stripped_norm = norm(stripped)
    compact = compact_search_query(text)
    compact_norm = norm(compact)
    compact_tokens = [token for token in tokens(compact_norm) if token not in SEARCH_STOP_WORDS]

    for item in items:
        name_norm = norm(item.get('name'))
        if raw_norm and raw_norm == name_norm:
            return item
        if stripped_norm and stripped_norm == name_norm:
            return item
        if compact_norm and compact_norm == name_norm:
            return item

    if len(items) == 1 and (len(compact_tokens) >= 2 or len(stripped_norm) >= 12 or len(raw_norm) >= 16):
        return items[0]

    if len(compact_tokens) >= 3:
        for item in items:
            name_tokens = set(tokens(item.get('name')))
            if all(token in name_tokens for token in compact_tokens):
                return item

    return None


def direct_product_match(text):
    merged = []
    for candidate in search_candidates(text):
        if len(norm(candidate)) < 3:
            continue
        products = search_products(candidate)
        if not products:
            continue
        merged = merge_products(merged + products)
        picked = strong_product_match(text, products)
        if picked:
            return picked, merged
    picked = strong_product_match(text, merged)
    return picked, merged


def get_product(product_id):
    return product_from(wc_request('GET', f'products/{product_id}'))


def variation_name(raw):
    values = [item.get('option') for item in (raw.get('attributes') or []) if item.get('option')]
    return ' / '.join(values) if values else f"Variación {raw.get('id')}"


def variation_color(raw):
    for item in raw.get('attributes') or []:
        if norm(item.get('name') or item.get('slug') or '') in COLOR_HINTS:
            return item.get('option')
    return None


def get_variations(product_id):
    data = wc_request('GET', f'products/{product_id}/variations', params={'per_page': 50})
    items = []
    for raw in data:
        if raw.get('stock_status') == 'outofstock':
            continue
        items.append({
            'id': raw.get('id'),
            'label': variation_name(raw),
            'color': variation_color(raw),
            'price': raw.get('price') or raw.get('regular_price') or '',
            'price_label': price_label(raw.get('price') or raw.get('regular_price')),
            'image': (raw.get('image') or {}).get('src', ''),
        })
    return items


def list_text(title, products):
    lines = [title, '']
    for index, item in enumerate(products, start=1):
        lines.append(f"{index}. {item['name']} - {item['price_label']}")
    lines.extend([
        '',
        'Escribe el número del producto que te interesa.',
        'Si prefieres, también puedes escribirme el nombre del producto.',
        'También puedes escribir MENU para volver al inicio.',
    ])
    return '\n'.join(lines)


def variation_text(items):
    lines = ['🎨 Este producto tiene estas opciones disponibles:', '']
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item['label']} - {item['price_label']}")
    lines.extend(['', 'Escribe el número de la opción o el nombre del color para continuar.'])
    return '\n'.join(lines)


def card_text(product, variation=None, prompt=None, category_key=None):
    lines = [
        f"🛍️ Producto: {product['name']}",
        f"💸 Precio: {variation['price_label'] if variation else product['price_label']}",
    ]
    if variation and variation.get('label'):
        lines.append(f"🎨 Variación: {variation['label']}")
    if product.get('short_description'):
        lines.append(f"📝 Descripción: {product['short_description'][:220]}")
    promo = pricing_note()
    if promo:
        lines.append(promo)
    lines.append(shipping_note())
    if product.get('permalink'):
        lines.append(f"🔗 Comprar aquí: {product['permalink']}")
    if prompt:
        lines.append(prompt)
    lines.extend(upsell_lines(product, category_key=category_key, mode='browse'))
    return '\n'.join(lines)


def checkout_edit_hint():
    return "✏️ Si quieres ajustar tu pedido, puedes escribir por ejemplo 'quiero 3 unidades', 'súbelo a 5' o 'no quiero este producto'."


def checkout_summary_text(session, city=''):
    product = session.get('product')
    if not product:
        return ''
    variation = session.get('variation')
    quantity = session.get('quantity', 1)
    pricing, shipping, grand_total = quote_totals(product, variation=variation, quantity=quantity, city=city)
    lines = ['🧾 Resumen del pedido:']
    lines.append(f"📦 Producto: {product['name']}")
    if variation and variation.get('label'):
        lines.append(f"🎨 Variación: {variation['label']}")
    lines.append(f"🔢 Cantidad: {quantity}")
    if pricing['discount_pct'] > 0:
        lines.append(f"🏷️ Precio por unidad con descuento: {price_label(pricing['discounted_unit'])}")
        lines.append(f"📚 Subtotal antes del descuento: {price_label(pricing['subtotal'])}")
        lines.append(f"🛍️ Subtotal productos: {price_label(pricing['total'])}")
        if pricing['savings'] > 0:
            lines.append(f"✨ Ahorro: {price_label(pricing['savings'])}")
    else:
        lines.append(f"🏷️ Precio por unidad: {price_label(pricing['base_unit'])}")
        lines.append(f"🛍️ Subtotal productos: {price_label(pricing['total'])}")
    if city:
        if shipping['free_shipping']:
            lines.append('🚚 Envío: gratis')
        else:
            lines.append(f"🚚 Envío: {price_label(shipping['cost'])} ({shipping['method_title']})")
        lines.append(f"💰 Total estimado: {price_label(grand_total)}")
    return '\n'.join(lines)


def prompt_after_quantity_update(state, session):
    checkout = session.get('checkout', {})
    city = checkout.get('city', '')
    lines = [f"✅ Listo, actualicé la cantidad a {session.get('quantity', 1)} unidad(es).", checkout_summary_text(session, city=city)]
    if state == 'name':
        lines.extend(['', '🙋 Ahora escríbeme tu nombre completo.'])
    elif state == 'city':
        lines.extend(['', '📍 ¿En qué ciudad recibirás el pedido?'])
    elif state == 'address1':
        lines.extend(['', f"🏠 ¿Cuál es tu dirección principal en {city or 'tu ciudad'}?"])
    elif state == 'address2':
        lines.extend(['', '📌 Barrio, torre o referencia. Si no aplica, escribe OMITIR.'])
    elif state == 'notes':
        lines.extend(['', '📝 Observaciones para la entrega. Si no tienes, escribe OMITIR.'])
    lines.extend(['', checkout_edit_hint()])
    return '\n'.join(line for line in lines if line is not None)


def remove_current_item(phone, hint, session):
    session['product'] = None
    session['variation'] = None
    session['quantity'] = 1
    session['checkout']['full_name'] = ''
    session['checkout']['city'] = ''
    session['checkout']['address_1'] = ''
    session['checkout']['address_2'] = ''
    session['checkout']['notes'] = ''
    if session.get('last_products'):
        session['state'] = 'pick_product'
        save_session(phone, session)
        send_message(phone, hint, list_text('✅ Quité ese producto de tu pedido. Estos son los productos que estabas viendo:', session['last_products']))
        return
    reset_session(phone)
    send_message(phone, hint, menu_text())


def post_purchase_message(session, order_number, city=''):
    product = session.get('product')
    if not product:
        return f"🙏 Gracias por tu compra. Tu pedido #{order_number} ya fue creado."
    variation = session.get('variation')
    pricing, shipping, grand_total = quote_totals(
        product,
        variation=variation,
        quantity=session.get('quantity', 1),
        city=city,
    )
    lines = [
        '🙏 Gracias por tu compra. Ya dejé tu pedido listo.',
        f'🧾 Pedido: #{order_number}',
        f'📦 Producto: {product["name"]}',
    ]
    if variation and variation.get('label'):
        lines.append(f'🎨 Variación: {variation["label"]}')
    lines.append(f'🔢 Cantidad: {session.get("quantity", 1)}')
    if pricing['discount_pct'] > 0:
        lines.append(f'🏷️ Descuento aplicado: {percent_string(pricing["discount_pct"])}% sobre el precio rebajado actual')
    lines.append(f'🛍️ Subtotal productos: {price_label(pricing["total"])}')
    if shipping['free_shipping']:
        lines.append('🚚 Envío: gratis')
    else:
        lines.append(f'🚚 Envío: {price_label(shipping["cost"])}')
    lines.append('💵 Pago: contra entrega en efectivo')
    lines.append(f'💰 Total final: {price_label(grand_total)}')
    if product.get('permalink'):
        lines.append(f'🔗 Link del producto: {product["permalink"]}')
    category_key = session.get('category')
    if category_key in CATEGORIES:
        lines.append(f'✨ Si quieres, también te puedo mostrar más productos de {CATEGORIES[category_key]["label"]} o de otras categorías. Escribe MENU cuando quieras seguir comprando.')
    else:
        lines.append('✨ Si quieres, también te puedo mostrar productos parecidos o de otras categorías. Escribe MENU cuando quieras seguir comprando.')
    lines.extend(upsell_lines(product, category_key=category_key, mode='post_purchase'))
    return '\n'.join(lines)


def open_product_detail(phone, hint, session, product):
    latest = get_product(product['id'])
    resolved_category = category_key_for_product(latest) or session.get('category')
    session['category'] = resolved_category
    session['product'] = latest
    session['variation'] = None
    session['quantity'] = 1
    if latest.get('type') == 'variable':
        vars_ = get_variations(latest['id'])
        if len(vars_) == 1:
            session['variation'] = vars_[0]
            session['state'] = 'confirm_buy'
            session['last_variations'] = vars_
            save_session(phone, session)
            send_message(phone, hint, card_text(latest, vars_[0], '✅ Si deseas continuar con este producto, escribe COMPRAR.', category_key=resolved_category), vars_[0].get('image') or latest.get('image'))
            return
        if vars_:
            session['state'] = 'pick_variation'
            session['last_variations'] = vars_
            save_session(phone, session)
            send_message(phone, hint, card_text(latest, prompt='👇 Te muestro las opciones disponibles para que elijas la que más te guste.', category_key=resolved_category), latest.get('image'))
            send_message(phone, hint, variation_text(vars_))
            return
    session['state'] = 'confirm_buy'
    session['last_variations'] = []
    save_session(phone, session)
    send_message(phone, hint, card_text(latest, prompt='✅ Si deseas continuar con este producto, escribe COMPRAR.', category_key=resolved_category), latest.get('image'))


def create_order(session):
    product = session.get('product')
    if not product:
        raise IntegrationError('No product selected.')
    checkout = session.get('checkout', {})
    first_name, last_name = split_name(checkout.get('full_name', ''))
    billing = {
        'first_name': first_name,
        'last_name': last_name,
        'phone': checkout.get('customer_phone', ''),
        'email': billing_email_for(checkout),
        'address_1': checkout.get('address_1', ''),
        'address_2': checkout.get('address_2', ''),
        'city': checkout.get('city', ''),
        'country': DEFAULT_COUNTRY,
    }
    quantity = session.get('quantity', 1)
    line_item = {'product_id': product['id'], 'quantity': quantity}
    variation = session.get('variation')
    if variation and variation.get('id'):
        line_item['variation_id'] = variation['id']
    pricing = pricing_for(product, variation=variation, quantity=quantity)
    shipping = shipping_for_city(checkout.get('city', ''), pricing['total'])
    line_item['subtotal'] = money_string(pricing['subtotal'])
    line_item['total'] = money_string(pricing['total'])
    payload = {
        'payment_method': 'cod',
        'payment_method_title': 'Contra entrega',
        'set_paid': False,
        'billing': billing,
        'shipping': billing,
        'line_items': [line_item],
        'shipping_lines': [
            {
                'method_id': 'flat_rate',
                'method_title': shipping['method_title'],
                'total': money_string(shipping['cost']),
            }
        ],
        'customer_note': checkout.get('notes', ''),
        'meta_data': [
            {'key': '_zender_channel', 'value': 'whatsapp_bot'},
            {'key': '_zender_customer_phone', 'value': checkout.get('customer_phone', '')},
            {'key': '_bot_discount_pct', 'value': percent_string(pricing['discount_pct'])},
            {'key': '_bot_discount_basis', 'value': pricing_rules().get('basis', 'current_price')},
            {'key': '_bot_shipping_region', 'value': shipping['region']},
            {'key': '_bot_shipping_cost', 'value': money_string(shipping['cost'])},
            {'key': '_bot_free_shipping', 'value': 'yes' if shipping['free_shipping'] else 'no'},
        ],
    }
    return wc_request('POST', 'orders', payload=payload)


def pick_number(text, items):
    if not items:
        return None
    value = choice_from(text)
    if value is None:
        return None
    index = value - 1
    return items[index] if 0 <= index < len(items) else None


def pick_variation(text, items):
    selected = pick_number(text, items)
    if selected:
        return selected
    message = norm(text)
    for item in items:
        if norm(item.get('label')) == message:
            return item
        if item.get('color') and norm(item['color']) in message:
            return item
    return None


def pick_product(text, items):
    selected = pick_number(text, items)
    if selected:
        return selected
    message = norm(text)
    if not message:
        return None
    for item in items:
        name = norm(item.get('name'))
        if message == name or message in name or name in message:
            return item
    query_tokens = [token for token in tokens(compact_search_query(text)) if token not in SEARCH_STOP_WORDS]
    if not query_tokens:
        return None
    for item in items:
        name_tokens = set(tokens(item.get('name')))
        if all(token in name_tokens for token in query_tokens):
            return item
    return None


def send_message(phone, account_hint, message, image_url=None):
    try:
        uno_send(phone, message, hint=account_hint, image_url=image_url)
    except Exception as exc:
        if image_url:
            app.logger.warning('Image send failed, retrying text-only message: %s', exc)
            uno_send(phone, message, hint=account_hint, image_url=None)
            return
        app.logger.exception('WhatsApp send failed: %s', exc)
        raise


def handle_idle(phone, hint, text, session):
    message = norm(text)
    if is_menu_request(text):
        session['state'] = 'idle'
        save_session(phone, session)
        send_message(phone, hint, menu_text())
        return
    if len(message) >= 6:
        direct_product, matched_products = direct_product_match(text)
        if direct_product:
            session['category'] = category_for(text)
            session['last_products'] = matched_products or [direct_product]
            open_product_detail(phone, hint, session, direct_product)
            return
    category_key = category_for(text)
    if category_key:
        products = list_products(category_key)
        if not products:
            send_message(phone, hint, f"Por ahora no encontré productos disponibles en {CATEGORIES[category_key]['label']}. Si quieres, prueba con otra categoría o escríbeme el nombre del producto.")
            return
        session['state'] = 'pick_product'
        session['category'] = category_key
        session['last_products'] = products
        session['last_variations'] = []
        session['product'] = None
        session['variation'] = None
        save_session(phone, session)
        send_message(phone, hint, list_text(f"Estos son algunos productos de {CATEGORIES[category_key]['label']}:", products))
        return
    if len(message) >= 3:
        for candidate in search_candidates(text):
            if len(norm(candidate)) < 3:
                continue
            products = search_products(candidate)
            if not products:
                continue
            session['state'] = 'pick_product'
            session['category'] = None
            session['last_products'] = products
            session['last_variations'] = []
            session['product'] = None
            session['variation'] = None
            save_session(phone, session)
            label = candidate if norm(candidate) != norm(text) else clean(text)
            send_message(phone, hint, list_text(f"🔎 Encontré estos productos para '{label}':", products))
            return
    send_message(phone, hint, 'No logré identificar esa categoría o ese producto. Escribe MENU para ver categorías o prueba con el nombre exacto del producto.')


def handle_product(phone, hint, text, session):
    product = pick_product(text, session.get('last_products', []))
    if not product:
        category_key = category_for(text)
        if category_key:
            session['state'] = 'idle'
            save_session(phone, session)
            handle_idle(phone, hint, text, session)
            return
        direct_product, matched_products = direct_product_match(text)
        if direct_product:
            session['last_products'] = matched_products or [direct_product]
            open_product_detail(phone, hint, session, direct_product)
            return
        for candidate in search_candidates(text):
            if len(norm(candidate)) < 3:
                continue
            products = search_products(candidate)
            if not products:
                continue
            session['state'] = 'pick_product'
            session['category'] = None
            session['last_products'] = products
            session['last_variations'] = []
            session['product'] = None
            session['variation'] = None
            save_session(phone, session)
            send_message(phone, hint, list_text(f"🔎 También encontré estos productos para '{candidate}':", products))
            return
        send_message(phone, hint, 'Escribe el número del producto que quieres ver, por ejemplo 1 o 2, o envíame el nombre del producto.')
        return
    open_product_detail(phone, hint, session, product)


def handle_variation(phone, hint, text, session):
    selected = pick_variation(text, session.get('last_variations', []))
    if not selected:
        send_message(phone, hint, 'No pude identificar la variación. Escríbeme el número de la opción o el color que prefieres.')
        return
    session['variation'] = selected
    session['state'] = 'confirm_buy'
    save_session(phone, session)
    send_message(phone, hint, card_text(session['product'], selected, '✅ Si deseas continuar con este producto, escribe COMPRAR.'), selected.get('image') or session['product'].get('image'))


def begin_checkout(phone, hint, text, session):
    quantity = checkout_quantity_update(text, session.get('quantity', 1), allow_plain=True)
    if quantity:
        session['quantity'] = quantity
        session['state'] = 'name'
        save_session(phone, session)
        pricing = pricing_for(session.get('product'), variation=session.get('variation'), quantity=quantity)
        lines = [f"✅ Perfecto. Vas con {quantity} unidad(es)."]
        if pricing['discount_pct'] > 0:
            lines.append(f"🏷️ Descuento aplicado: {percent_string(pricing['discount_pct'])}% sobre el precio rebajado actual.")
            lines.append(f"💸 Valor por unidad: {price_label(pricing['discounted_unit'])}")
            lines.append(f"🛍️ Subtotal productos: {price_label(pricing['total'])}")
        else:
            lines.append(f"🛍️ Subtotal productos: {price_label(pricing['total'])}")
        lines.append('🚚 El envío se calcula según tu ciudad.')
        lines.append('🙋 Escríbeme tu nombre completo para crear el pedido.')
        lines.append(checkout_edit_hint())
        send_message(phone, hint, '\n'.join(lines))
        return
    session['state'] = 'qty'
    save_session(phone, session)
    lines = ['¿Cuántas unidades deseas? Escribe solo un número, por ejemplo 1 o 2.']
    promo = pricing_note()
    if promo:
        lines.append(promo)
    send_message(phone, hint, '\n'.join(lines))


def handle_confirm(phone, hint, text, session):
    message = norm(text)
    if is_menu_request(text):
        reset_session(phone)
        send_message(phone, hint, menu_text())
        return
    if wants_remove_current_item(text, session):
        remove_current_item(phone, hint, session)
        return
    quantity = checkout_quantity_update(text, session.get('quantity', 1), allow_plain=False)
    if quantity:
        begin_checkout(phone, hint, str(quantity), session)
        return
    if message in BUY_WORDS or message.startswith('comprar'):
        begin_checkout(phone, hint, text, session)
        return
    send_message(phone, hint, 'Si quieres cerrar la compra, escribe COMPRAR. Si prefieres volver al inicio, escribe MENU.')


def handle_checkout(phone, hint, text, session):
    message = norm(text)
    checkout = session['checkout']
    if wants_remove_current_item(text, session):
        remove_current_item(phone, hint, session)
        return
    if session['state'] != 'qty':
        quantity = checkout_quantity_update(text, session.get('quantity', 1), allow_plain=False)
        if quantity:
            session['quantity'] = quantity
            save_session(phone, session)
            send_message(phone, hint, prompt_after_quantity_update(session['state'], session))
            return
    if session['state'] == 'qty':
        quantity = qty_from(text)
        if not quantity:
            send_message(phone, hint, 'Necesito un número válido de unidades, por ejemplo 1 o 2.')
            return
        session['quantity'] = quantity
        session['state'] = 'name'
        save_session(phone, session)
        pricing = pricing_for(session.get('product'), variation=session.get('variation'), quantity=quantity)
        lines = [f"✅ Perfecto. Vas con {quantity} unidad(es)."]
        if pricing['discount_pct'] > 0:
            lines.append(f"🏷️ Descuento aplicado: {percent_string(pricing['discount_pct'])}% sobre el precio rebajado actual.")
            lines.append(f"💸 Valor por unidad: {price_label(pricing['discounted_unit'])}")
            lines.append(f"🛍️ Subtotal productos: {price_label(pricing['total'])}")
        else:
            lines.append(f"🛍️ Subtotal productos: {price_label(pricing['total'])}")
        lines.append('🚚 El envío se calcula según tu ciudad.')
        lines.append('🙋 Ahora escríbeme tu nombre completo.')
        lines.append(checkout_edit_hint())
        send_message(phone, hint, '\n'.join(lines))
        return
    if session['state'] == 'name':
        if len(clean(text)) < 3:
            send_message(phone, hint, 'Necesito un nombre un poco más completo para continuar.')
            return
        checkout['full_name'] = clean(text)
        session['state'] = 'city'
        save_session(phone, session)
        send_message(phone, hint, '📍 ¿En qué ciudad recibirás el pedido?')
        return
    if session['state'] == 'city':
        if len(clean(text)) < 2:
            send_message(phone, hint, 'Escríbeme la ciudad para continuar.')
            return
        checkout['city'] = clean(text)
        session['state'] = 'address1'
        save_session(phone, session)
        pricing, shipping, grand_total = quote_totals(
            session.get('product'),
            variation=session.get('variation'),
            quantity=session.get('quantity', 1),
            city=checkout['city'],
        )
        lines = [f"🏠 ¿Cuál es tu dirección principal en {checkout['city']}?", '', checkout_summary_text(session, city=checkout['city'])]
        if shipping['free_shipping']:
            lines.append('🎁 Tu pedido aplica para envío gratis.')
        lines.append(checkout_edit_hint())
        send_message(phone, hint, '\n'.join(lines))
        return
    if session['state'] == 'address1':
        if len(clean(text)) < 6:
            send_message(phone, hint, 'Escríbeme una dirección más completa, por favor.')
            return
        checkout['address_1'] = clean(text)
        session['state'] = 'address2'
        save_session(phone, session)
        send_message(phone, hint, '📌 Barrio, torre o referencia. Si no aplica, escribe OMITIR.\n\n' + checkout_summary_text(session, city=checkout.get('city', '')))
        return
    if session['state'] == 'address2':
        checkout['address_2'] = '' if message in SKIP_WORDS else clean(text)
        session['state'] = 'notes'
        save_session(phone, session)
        send_message(phone, hint, '📝 Observaciones para la entrega. Si no tienes, escribe OMITIR.\n\n' + checkout_summary_text(session, city=checkout.get('city', '')))
        return
    if session['state'] == 'notes':
        checkout['notes'] = '' if message in SKIP_WORDS else clean(text)
        session['state'] = 'creating'
        save_session(phone, session)
        try:
            order = create_order(session)
        except Exception as exc:
            app.logger.exception('Order creation failed: %s', exc)
            session['state'] = 'confirm_buy'
            save_session(phone, session)
            send_message(phone, hint, 'No pude crear el pedido en WooCommerce en este momento. Escribe COMPRAR para intentarlo de nuevo o MENU para empezar otra vez.')
            return
        number = order.get('number') or order.get('id')
        send_message(phone, hint, post_purchase_message(session, number, city=checkout.get('city', '')))
        reset_session(phone)


def handle_whatsapp(data):
    phone = clean(data.get('phone') or data.get('sender') or '')
    hint = clean(data.get('wid') or data.get('account') or '')
    text = clean(data.get('message') or '')
    attachment = clean(data.get('attachment') or '')
    if not phone:
        raise IntegrationError('Incoming WhatsApp payload does not include a phone number.')
    session = load_session(phone)
    message = norm(text)
    if message in RESET_WORDS:
        reset_session(phone)
        send_message(phone, hint, menu_text())
        return
    if text and is_menu_request(text):
        reset_session(phone)
        send_message(phone, hint, menu_text())
        return
    if not text and attachment:
        send_message(phone, hint, 'Recibí tu archivo. Por ahora puedo ayudarte mejor con texto. Escribe MENU para ver categorías.')
        return
    if session['state'] in {'idle', ''} and is_likely_noise_message(text, attachment=attachment):
        app.logger.info('Ignoring likely noise message from %s: %s', phone, text[:160])
        return
    if session['state'] in {'idle', ''}:
        handle_idle(phone, hint, text, session)
        return
    if session['state'] == 'pick_product':
        handle_product(phone, hint, text, session)
        return
    if session['state'] == 'pick_variation':
        handle_variation(phone, hint, text, session)
        return
    if session['state'] == 'confirm_buy':
        handle_confirm(phone, hint, text, session)
        return
    if session['state'] in {'qty', 'name', 'city', 'address1', 'address2', 'notes', 'creating'}:
        handle_checkout(phone, hint, text, session)
        return
    reset_session(phone)
    send_message(phone, hint, menu_text())


def parse_woocommerce_payload():
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return payload
    return {key: value for key, value in request.values.items()}


def valid_wc_webhook(signature, payload_secret, raw_body):
    if not WC_WEBHOOK_SECRET:
        app.logger.warning('WC_WEBHOOK_SECRET is not configured.')
        return True
    if signature:
        expected = base64.b64encode(hmac.new(WC_WEBHOOK_SECRET.encode('utf-8'), raw_body, hashlib.sha256).digest()).decode('utf-8')
        return hmac.compare_digest(str(signature), expected)
    if payload_secret:
        return hmac.compare_digest(str(payload_secret), WC_WEBHOOK_SECRET)
    return False


def extract_order_payload(payload):
    if not isinstance(payload, dict):
        return None
    candidates = [payload.get('order'), payload.get('data'), payload]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if candidate.get('id') and (
            candidate.get('status') is not None
            or candidate.get('billing')
            or candidate.get('meta_data')
            or candidate.get('line_items')
            or candidate.get('number')
        ):
            return candidate
    return None


def fetch_order(order_id):
    if not order_id:
        return {}
    return wc_request('GET', f'orders/{order_id}')


def fetch_order_notes(order_id):
    if not order_id:
        return []
    return wc_request('GET', f'orders/{order_id}/notes', params={'type': 'customer', 'per_page': 20})


def latest_customer_note(order_id):
    try:
        notes = fetch_order_notes(order_id)
    except Exception as exc:
        app.logger.warning('Could not fetch WooCommerce notes for order %s: %s', order_id, exc)
        return None
    customer_notes = [note for note in notes if note.get('customer_note')]
    if not customer_notes:
        return None
    return customer_notes[-1]


def maybe_send_latest_customer_note(order):
    order_id = clean(order.get('id') or '')
    if not order_id:
        return False
    note = latest_customer_note(order_id)
    if not note:
        return False
    note_key = clean(note.get('id') or '')
    tracked = order_tracking(order_id)
    if note_key and tracked['last_note_key'] == note_key:
        return False
    phone = order_phone(order)
    if not phone:
        app.logger.info('Skipping latest customer note for order %s because no phone was found.', order_id)
        return False
    send_message(phone, '', customer_note_message(order_number(order) or order_id, note.get('note') or ''))
    save_order_tracking(order_id, note_key=note_key)
    return True


def process_wc_order_event(topic, order):
    order_id = clean(order.get('id') or '')
    status = clean(order.get('status') or '').lower()
    if not order_id or not status:
        return False
    tracked = order_tracking(order_id)
    previous_status = tracked['last_status']
    save_order_tracking(order_id, status=status)
    if previous_status == status:
        return False
    if status not in ORDER_STATUS_COPY:
        return False
    if not previous_status and status == 'pending':
        return False
    phone = order_phone(order)
    if not phone:
        app.logger.info('Skipping WooCommerce status update for order %s because no phone was found.', order_id)
        return False
    send_message(phone, '', order_status_message(order, status))
    return True


def extract_customer_note_payload(payload):
    if not isinstance(payload, dict):
        return {}
    candidates = [payload.get('data'), payload]
    merged = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key in ['type', 'order_id', 'order_number', 'phone', 'note', 'customer_note', 'note_id', 'id', 'secret']:
            if key in candidate and key not in merged:
                merged[key] = candidate.get(key)
    note_text = clean(merged.get('note') or merged.get('customer_note') or '')
    return {
        'type': clean(merged.get('type')),
        'order_id': clean(merged.get('order_id') or ''),
        'order_number': clean(merged.get('order_number') or ''),
        'phone': clean(merged.get('phone') or ''),
        'note': note_text,
        'note_key': clean(merged.get('note_id') or merged.get('id') or (hashlib.sha1(note_text.encode('utf-8')).hexdigest() if note_text else '')),
    }


def process_wc_customer_note(topic, payload):
    note_payload = extract_customer_note_payload(payload)
    order = extract_order_payload(payload) or {}
    order_id = note_payload['order_id'] or clean(order.get('id') or '')
    note_text = strip_html(note_payload['note'])
    if not order_id or not note_text:
        return False
    tracked = order_tracking(order_id)
    note_key = note_payload['note_key']
    if note_key and tracked['last_note_key'] == note_key:
        return False
    if not order:
        try:
            order = fetch_order(order_id)
        except Exception as exc:
            app.logger.warning('Could not fetch WooCommerce order %s for customer note: %s', order_id, exc)
            order = {}
    phone = note_payload['phone'] or order_phone(order)
    if not phone:
        app.logger.info('Skipping WooCommerce note for order %s because no phone was found.', order_id)
        return False
    number = note_payload['order_number'] or order_number(order) or order_id
    send_message(phone, '', customer_note_message(number, note_text))
    save_order_tracking(order_id, note_key=note_key)
    return True


def process_woocommerce_webhook(topic, payload):
    topic_text = clean(topic).lower()
    if 'note' in topic_text or extract_customer_note_payload(payload).get('note'):
        return process_wc_customer_note(topic_text, payload)
    order = extract_order_payload(payload)
    if not order:
        return False
    status_handled = process_wc_order_event(topic_text, order)
    note_handled = maybe_send_latest_customer_note(order)
    return status_handled or note_handled


def nested_data(values):
    data = {}
    for key in values.keys():
        match = re.fullmatch(r'data\[([^\]]+)\]', key)
        if match:
            data[match.group(1)] = values.get(key)
    return data


def parse_payload():
    payload = request.get_json(silent=True)
    values = request.values
    secret = None
    payload_type = None
    data = {}
    if isinstance(payload, dict):
        secret = payload.get('secret')
        payload_type = payload.get('type')
        if isinstance(payload.get('data'), dict):
            data = payload['data']
        elif isinstance(payload.get('data'), str):
            try:
                data = json.loads(payload['data'])
            except json.JSONDecodeError:
                data = {}
    if not data:
        data = nested_data(values)
    if not data and values.get('data'):
        try:
            data = json.loads(values.get('data'))
        except (TypeError, json.JSONDecodeError):
            data = {}
    if secret is None:
        secret = values.get('secret')
    if payload_type is None:
        payload_type = values.get('type')
    if not data:
        data = {key: value for key, value in values.items() if key not in {'secret', 'type'}}
    return {'secret': secret, 'type': payload_type, 'data': data}


def valid_secret(secret):
    if not WEBHOOK_SECRET:
        app.logger.warning('ZENDER_WEBHOOK_SECRET is not configured.')
        return True
    return bool(secret) and hmac.compare_digest(str(secret), WEBHOOK_SECRET)


def prefers_html_response():
    accept = (request.headers.get('Accept') or '').lower()
    return 'text/html' in accept or 'application/xhtml+xml' in accept


def render_status_page(title, subtitle, endpoint_path, accent='#37f0c2'):
    safe_title = html.escape(title)
    safe_subtitle = html.escape(subtitle)
    safe_endpoint = html.escape(endpoint_path)
    banner = (
        "__        __   _     _                 _    \n"
        "\\ \\      / /__| |__ | |__   ___   ___ | | __\n"
        " \\ \\ /\\ / / _ \\ '_ \\| '_ \\ / _ \\ / _ \\| |/ /\n"
        "  \\ V  V /  __/ |_) | | | | (_) | (_) |   < \n"
        "   \\_/\\_/ \\___|_.__/|_| |_|\\___/ \\___/|_|\\_\\"
    )
    safe_banner = html.escape(banner)
    page = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    :root {{
      --bg: #08111f;
      --panel: rgba(9, 18, 34, 0.92);
      --line: rgba(255, 255, 255, 0.10);
      --text: #ecf7ff;
      --muted: #9ab0c3;
      --accent: {accent};
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Consolas, "Courier New", monospace;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(55, 240, 194, 0.18), transparent 30%),
        radial-gradient(circle at top right, rgba(83, 161, 255, 0.16), transparent 26%),
        linear-gradient(180deg, #050b15 0%, #0a1322 100%);
      display: grid;
      place-items: center;
      padding: 24px;
    }}
    .panel {{
      width: min(920px, 100%);
      border: 1px solid var(--line);
      border-radius: 22px;
      background: var(--panel);
      box-shadow: 0 24px 70px rgba(0, 0, 0, 0.35);
      overflow: hidden;
    }}
    .header {{
      padding: 22px 24px 12px;
      border-bottom: 1px solid var(--line);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.04);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}
    .dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 18px var(--accent);
    }}
    .content {{
      padding: 24px;
      display: grid;
      gap: 22px;
    }}
    pre {{
      margin: 0;
      padding: 20px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(0, 0, 0, 0.24);
      color: var(--accent);
      font-size: clamp(11px, 1.8vw, 16px);
      line-height: 1.28;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(28px, 5vw, 46px);
      line-height: 1.04;
    }}
    p {{
      margin: 0;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.7;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      background: rgba(255, 255, 255, 0.03);
    }}
    .label {{
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}
    .value {{
      font-size: 16px;
      font-weight: 700;
      word-break: break-word;
    }}
    code {{
      color: var(--accent);
      font-size: 14px;
    }}
    .footer {{
      padding: 0 24px 24px;
      color: var(--muted);
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main class="panel">
    <div class="header">
      <span class="badge"><span class="dot"></span>Servicio activo</span>
    </div>
    <div class="content">
      <pre>{safe_banner}</pre>
      <div>
        <h1>{safe_title}</h1>
        <p>{safe_subtitle}</p>
      </div>
      <div class="grid">
        <section class="card">
          <span class="label">Estado</span>
          <div class="value">OK</div>
        </section>
        <section class="card">
          <span class="label">Endpoint</span>
          <div class="value"><code>{safe_endpoint}</code></div>
        </section>
        <section class="card">
          <span class="label">Método esperado</span>
          <div class="value">POST</div>
        </section>
      </div>
    </div>
    <div class="footer">
      Si ves esta pantalla en el navegador, la app está encendida y lista para recibir webhooks.
    </div>
  </main>
</body>
</html>"""
    return Response(page, mimetype='text/html')


@app.route('/', methods=['GET', 'POST'])
@app.route('/zender-webhook', methods=['GET', 'POST'])
def zender_webhook():
    if request.method == 'GET':
        if prefers_html_response():
            return render_status_page(
                'Zender WooCommerce Bot',
                'La app está corriendo y lista para recibir mensajes de WhatsApp desde Zender.',
                '/zender-webhook',
            )
        return jsonify({'status': 'ok', 'message': 'Zender WooCommerce bot is running.'})
    payload = parse_payload()
    app.logger.info('Incoming payload type=%s data=%s', payload.get('type'), payload.get('data'))
    if not valid_secret(payload.get('secret')):
        return jsonify({'error': 'Invalid webhook secret'}), 403
    payload_type = payload.get('type')
    payload_data = payload.get('data') or {}
    event_id = payload_data.get('id')
    event_key = f"{payload_type}:{event_id}" if payload_type and event_id else None
    if event_seen(event_key):
        return jsonify({'status': 'duplicate'}), 200
    try:
        if payload_type == 'whatsapp':
            handle_whatsapp(payload_data)
        else:
            app.logger.info('Ignoring unsupported payload type: %s', payload_type)
    except IntegrationError as exc:
        app.logger.exception('Webhook processing error: %s', exc)
        return jsonify({'error': str(exc)}), 500
    except Exception as exc:
        app.logger.exception('Unexpected webhook error: %s', exc)
        return jsonify({'error': 'Internal server error'}), 500
    mark_event(event_key)
    return jsonify({'status': 'processed'}), 200


@app.route('/woocommerce-webhook', methods=['GET', 'POST'])
def woocommerce_webhook():
    if request.method == 'GET':
        if prefers_html_response():
            return render_status_page(
                'WooCommerce Webhook',
                'El endpoint está listo para recibir actualizaciones de pedidos y notas al cliente.',
                '/woocommerce-webhook',
                accent='#63a9ff',
            )
        return jsonify({'status': 'ok', 'message': 'WooCommerce webhook endpoint is running.'})
    raw_body = request.get_data() or b''
    payload = parse_woocommerce_payload()
    signature = clean(request.headers.get('X-WC-Webhook-Signature') or '')
    topic = clean(request.headers.get('X-WC-Webhook-Topic') or payload.get('topic') or payload.get('type') or '')
    delivery_id = clean(
        request.headers.get('X-WC-Webhook-Delivery-ID')
        or request.headers.get('X-WC-Delivery-ID')
        or payload.get('delivery_id')
        or ''
    )
    if not valid_wc_webhook(signature, payload.get('secret'), raw_body):
        return jsonify({'error': 'Invalid WooCommerce webhook signature'}), 403
    event_key = f"wc:{delivery_id}" if delivery_id else None
    if event_seen(event_key):
        return jsonify({'status': 'duplicate'}), 200
    try:
        handled = process_woocommerce_webhook(topic, payload)
    except IntegrationError as exc:
        app.logger.exception('WooCommerce webhook processing error: %s', exc)
        return jsonify({'error': str(exc)}), 500
    except Exception as exc:
        app.logger.exception('Unexpected WooCommerce webhook error: %s', exc)
        return jsonify({'error': 'Internal server error'}), 500
    mark_event(event_key)
    return jsonify({'status': 'processed', 'handled': handled}), 200


setup_logging()
init_db()


if __name__ == '__main__':
    port = int(os.getenv('PORT', os.getenv('APP_PORT', '5001')))
    app.run(host='0.0.0.0', port=port)
