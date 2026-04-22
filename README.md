# Bot de WhatsApp para Zender + WooCommerce

Guía completa, paso a paso y pensada para personas que nunca han trabajado con Python.

Este proyecto conecta:

- `Zender / UNO COBOL` para recibir y enviar mensajes de WhatsApp.
- `WooCommerce` para consultar productos, variaciones, precios, pedidos y notas.
- `Flask` para exponer los webhooks y ejecutar toda la lógica del bot.

---

## 1. Qué es este proyecto

Este software es una **app web hecha en Flask**.

Dicho más fácil:

- Es un programa en Python.
- Ese programa queda "escuchando" mensajes que llegan desde internet.
- Cuando alguien escribe por WhatsApp, Zender llama al bot.
- El bot consulta WooCommerce.
- El bot responde al cliente.
- Si el cliente compra, el bot crea el pedido en WooCommerce.

Además:

- puede aplicar descuentos por cantidad
- puede calcular envío
- puede notificar estados del pedido
- puede enviar notas al cliente al WhatsApp

---

## 2. Qué puede hacer el bot

Este bot puede:

- mostrar categorías
- listar productos desde WooCommerce en tiempo real
- encontrar productos por nombre exacto
- encontrar productos con frases naturales como `me interesa el taladro`
- mostrar foto, descripción, precio y link
- manejar productos con variaciones
- aplicar descuentos por cantidad
- calcular envío según ciudad
- crear pedidos en WooCommerce
- notificar estados del pedido por WhatsApp
- enviar notas al cliente por WhatsApp
- sugerir productos relacionados como upsell
- ignorar parte del ruido o mensajes irrelevantes

---

## 3. Si nunca has usado Python, empieza aquí

Si esta es tu primera vez con Python, no te preocupes. Lo mínimo que necesitas entender es esto:

### 3.1 Qué es Python

Python es el lenguaje en el que está escrito este bot.

### 3.2 Qué es Flask

Flask es una librería de Python que permite crear una app web.

En este proyecto, Flask sirve para crear estas rutas:

- `/`
- `/zender-webhook`
- `/woocommerce-webhook`

Estas rutas reciben mensajes y eventos desde Zender y WooCommerce.

### 3.3 Qué es `pip`

`pip` es el instalador de paquetes de Python.

Sirve para instalar dependencias como:

- `Flask`
- `requests`
- `gunicorn`

### 3.4 Qué es una terminal o consola

Es una ventana donde escribes comandos.

En Windows puede ser:

- `PowerShell`
- `CMD`

En macOS o Linux puede ser:

- `Terminal`

### 3.5 Qué es un entorno virtual

Es una carpeta especial donde Python guarda las dependencias de este proyecto sin mezclarlo con otros proyectos.

Normalmente se crea con:

```bash
python -m venv venv
```

---

## 4. Archivos importantes del proyecto

- [`app.py`](app.py)
  Archivo principal. Aquí vive toda la lógica del bot.

- [`passenger_wsgi.py`](passenger_wsgi.py)
  Archivo de arranque para hosting con Passenger.

- [`assenger_wsgi.py`](assenger_wsgi.py)
  Archivo gemelo de compatibilidad, por si tu hosting lo usa por configuración previa.

- [`deploy_cpanel.sh`](deploy_cpanel.sh)
  Script de despliegue para cPanel. Sirve para copiar el código del repositorio hacia la carpeta viva sin tocar tu `.env`, sin tocar la base en `tmp/` y corrigiendo permisos al final.

---

## 5. Desplegar en cPanel sin memorizar comandos raros

Si ya tienes tu repositorio clonado en el servidor dentro de una ruta como:

```bash
/mnt/jupiter/waonline/repositories/zender-webhook
```

y tu app viva está en:

```bash
/mnt/jupiter/waonline/public_html/zender-webhook
```

entonces puedes desplegar con un solo comando:

```bash
cd /mnt/jupiter/waonline/repositories/zender-webhook
bash deploy_cpanel.sh
```

Ese script hace esto por ti:

- hace `git pull`
- copia el código a la carpeta viva
- no toca `.env`
- no toca `tmp/`
- no toca `venv/` ni `virtualenv/`
- corrige permisos para que Apache y Passenger no den `403`
- reinicia la app tocando `tmp/restart.txt`

Si algún día quieres omitir el `git pull` y solo copiar lo que ya tienes en el repo, puedes hacer:

```bash
cd /mnt/jupiter/waonline/repositories/zender-webhook
SKIP_PULL=1 bash deploy_cpanel.sh
```

- [`requeriments.txt`](requeriments.txt)
  Lista de dependencias de Python.

  Importante: el nombre del archivo es `requeriments.txt`, así como está escrito en este proyecto.

- [`.env.example`](.env.example)
  Plantilla de variables de entorno.

- [`.env`](.env)
  Variables reales del proyecto.

- [`pricing_rules.example.json`](pricing_rules.example.json)
  Ejemplo de reglas de descuento.

- [`shipping_rules.example.json`](shipping_rules.example.json)
  Ejemplo de reglas de envío.

- [`woocommerce_discount_snippet.php`](woocommerce_discount_snippet.php)
  Snippet PHP para aplicar descuentos por cantidad en WooCommerce.

- [`woocommerce_customer_note_snippet.php`](woocommerce_customer_note_snippet.php)
  Snippet PHP para enviar notas al cliente desde WooCommerce al bot.

- [`LEER.txt`](LEER.txt)
  Archivo corto que redirige a esta guía.

---

## 5. Dependencias del proyecto

## 5.1 Dependencias que instala Python

Se instalan desde [`requeriments.txt`](requeriments.txt):

- `Flask`
- `requests`
- `gunicorn`

## 5.2 Librerías que ya vienen con Python

No necesitas instalarlas aparte:

- `sqlite3`
- `json`
- `hmac`
- `hashlib`
- `base64`
- `logging`
- `threading`
- `decimal`
- `re`
- `os`

## 5.3 Servicios externos obligatorios

Este proyecto también depende de:

- una tienda `WooCommerce`
- una cuenta `Zender / UNO COBOL`
- una cuenta de `WhatsApp` conectada en UNO/Zender
- un hosting con soporte para Python

---

## 6. Instalación local paso a paso para principiantes

Esta parte es para alguien que quiere probar el bot en su computador.

## 6.1 Instalar Python

### En Windows

1. Ve a [python.org](https://www.python.org/downloads/)
2. Descarga Python 3.11 o 3.10
3. Durante la instalación, marca la casilla:
   - `Add Python to PATH`
4. Termina la instalación

### En macOS o Linux

Instala Python 3.10+ desde el método normal de tu sistema.

## 6.2 Abrir la carpeta del proyecto

Pon el proyecto dentro de una carpeta, por ejemplo:

```text
zender-webhook
```

Luego abre una terminal dentro de esa carpeta.

### En Windows

Una forma fácil:

1. Entra a la carpeta en el explorador
2. Haz clic derecho
3. Abre `PowerShell` o `Terminal` allí

## 6.3 Crear el entorno virtual

En la terminal, ejecuta:

### Windows

```powershell
python -m venv venv
```

Si `python` no funciona:

```powershell
py -3.11 -m venv venv
```

### macOS / Linux

```bash
python3 -m venv venv
```

## 6.4 Activar el entorno virtual

### Windows PowerShell

```powershell
.\venv\Scripts\Activate.ps1
```

### Windows CMD

```cmd
venv\Scripts\activate.bat
```

### macOS / Linux

```bash
source venv/bin/activate
```

Cuando el entorno virtual está activo, normalmente verás algo como:

```text
(venv)
```

al principio de la línea.

## 6.5 Instalar dependencias

Con el entorno virtual activado:

```bash
pip install -r requeriments.txt
```

## 6.6 Crear tu archivo `.env`

Duplica [`.env.example`](.env.example) y llámalo `.env`.

Si estás en terminal:

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### macOS / Linux

```bash
cp .env.example .env
```

## 6.7 Editar el `.env`

Abre [`.env`](.env) con un editor de texto y completa los valores reales.

## 6.8 Ejecutar la app localmente

Con el entorno virtual activado:

### Windows / macOS / Linux

```bash
python app.py
```

Si tu sistema necesita `python3`:

```bash
python3 app.py
```

## 6.9 Probar si arrancó

Abre en navegador:

```text
http://127.0.0.1:5001/
```

o:

```text
http://localhost:5001/
```

Debe responder algo como:

```json
{"status":"ok","message":"Zender WooCommerce bot is running."}
```

---

## 7. Instalación en hosting con Python App / Passenger

Si vas a ponerlo en un hosting tipo cPanel o similar:

## 7.1 Configuración típica

Normalmente el panel te pide:

- `Python version`
- `Application root`
- `Application URL`
- `Application startup file`
- `Application entry point`

Configuración recomendada:

- `Python version`: `3.10` o `3.11`
- `Application root`: carpeta donde subiste el proyecto
- `Application URL`: `/zender-webhook`
- `Application startup file`: `passenger_wsgi.py`
- `Application entry point`: `application`

## 7.2 Instalar dependencias en hosting

Si tu panel tiene botón para instalar dependencias:

- apunta a [`requeriments.txt`](requeriments.txt)

Si tienes shell:

```bash
cd /ruta/de/tu/proyecto
pip install -r requeriments.txt
```

## 7.3 Reiniciar la app

Después de cambiar `app.py` o `.env`, reinicia la app desde el panel o por el mecanismo de tu hosting.

## 7.4 Verificar que la app está viva

Abre la URL pública de tu app.

Ejemplo:

```text
https://tu-dominio.com/zender-webhook/
```

Debe responder:

```json
{"status":"ok","message":"Zender WooCommerce bot is running."}
```

---

## 8. Variables de entorno explicadas una por una

Todas estas variables van en [`.env`](.env).

## 8.1 Variables obligatorias

### `ZENDER_WEBHOOK_SECRET`

Para qué sirve:

- Protege el webhook que recibe mensajes desde Zender.

De dónde sale:

- Lo defines o lo copias desde la configuración del webhook en Zender.

Debe coincidir exactamente entre:

- Zender
- tu archivo `.env`

Ejemplo:

```env
ZENDER_WEBHOOK_SECRET=mi_secret_de_zender
```

### `UNO_API_BASE`

Para qué sirve:

- Es la URL base de la API de UNO/Zender.

Valor normal:

```env
UNO_API_BASE=https://uno.cobol.com.co/api
```

### `UNO_API_SECRET`

Para qué sirve:

- Autoriza al bot a enviar mensajes por UNO/Zender.

Cómo obtenerlo:

1. Entra al panel de UNO/Zender
2. Crea o revisa una API key
3. Copia el `secret`

Ejemplo:

```env
UNO_API_SECRET=tu_secret_real_de_uno
```

### `UNO_WA_ACCOUNT`

Para qué sirve:

- Le dice al bot desde qué cuenta de WhatsApp debe enviar.

Cómo obtenerlo:

- Busca el `unique ID` de la cuenta WhatsApp conectada en UNO/Zender.

Importante:

- No es el número de teléfono
- No es `+57...`
- Es el identificador interno de la cuenta

Ejemplo:

```env
UNO_WA_ACCOUNT=1775526971c4ca4238a0b923820dcc509a6f75849b69d4643b43d7d
```

### `WC_BASE_URL`

Para qué sirve:

- Es la URL base de tu tienda.

Ejemplo:

```env
WC_BASE_URL=https://onlinecomprafacil.com
```

### `WC_CONSUMER_KEY`

### `WC_CONSUMER_SECRET`

Para qué sirven:

- Permiten consultar productos y crear pedidos por la API REST de WooCommerce.

Cómo obtenerlos:

1. Entra a WordPress
2. Ve a `WooCommerce > Settings > Advanced > REST API`
3. Pulsa `Create an API key`
4. Elige un usuario con permisos suficientes
5. Dale permisos `Read/Write`
6. Guarda
7. Copia:
   - `Consumer Key`
   - `Consumer Secret`

Ejemplo:

```env
WC_CONSUMER_KEY=ck_xxxxxxxxxxxxx
WC_CONSUMER_SECRET=cs_xxxxxxxxxxxxx
```

### `WC_WEBHOOK_SECRET`

Para qué sirve:

- Protege el webhook que recibe eventos desde WooCommerce.

Cómo obtenerlo:

- Tú mismo lo inventas cuando creas el webhook en WooCommerce.

Importante:

- Debe ser exactamente el mismo valor:
  - en el webhook de WooCommerce
  - en [`.env`](.env)

Ejemplo:

```env
WC_WEBHOOK_SECRET=mi_secret_wc_2026
```

## 8.2 Variables recomendadas

### `WC_API_VERSION`

Normalmente:

```env
WC_API_VERSION=wc/v3
```

### `WC_QUERY_STRING_AUTH`

Para qué sirve:

- Hace que el bot autentique la API de WooCommerce por query string.

Por qué existe:

- Muchos hostings compartidos bloquean Basic Auth.

Valor recomendado:

```env
WC_QUERY_STRING_AUTH=1
```

### `WC_CATEGORY_IDS_JSON`

Para qué sirve:

- Mapea las categorías del bot con los IDs reales de WooCommerce.

Ejemplo:

```env
WC_CATEGORY_IDS_JSON={"tecnologia":24,"hogar":20,"cuidado":23,"herramientas":22,"videojuegos":29,"salud":30}
```

Cómo sacar esos IDs:

1. En WordPress entra a editar una categoría de producto
2. Mira la URL del navegador
3. Verás algo como:

```text
tag_ID=24
```

Ese número es el ID.

### `WC_UPSELL_LIMIT`

Para qué sirve:

- Define cuántos productos relacionados puede sugerir el bot.

Ejemplo:

```env
WC_UPSELL_LIMIT=2
```

## 8.3 Variables de descuentos

### `BOT_DISCOUNT_RULES_JSON`

Para qué sirve:

- Define los descuentos por cantidad del bot.

Ejemplo:

```env
BOT_DISCOUNT_RULES_JSON={"basis":"current_price","tiers":[{"min_qty":2,"max_qty":2,"discount_pct":5},{"min_qty":3,"discount_pct":10}]}
```

Qué significa:

- 2 unidades = 5%
- 3 o más = 10%
- sobre el precio rebajado vigente

### `PRICING_RULES_URL`

Para qué sirve:

- Si algún día quieres que el bot lea las reglas desde una URL externa en JSON.

Si no la usas:

```env
PRICING_RULES_URL=
```

### `PRICING_RULES_CACHE_SECONDS`

Para qué sirve:

- Tiempo de cache de esa URL externa.

## 8.4 Variables de envío

### `BOT_SHIPPING_RULES_JSON`

Para qué sirve:

- Configura cuánto cuesta enviar a Bogotá, ciudades principales o nivel nacional.

Ejemplo:

```env
BOT_SHIPPING_RULES_JSON={"bogota_cost":8000,"principal_cost":12000,"national_cost":20000,"free_shipping_threshold":200000,"free_shipping_regions":["bogota","principal"],"bogota_aliases":["bogota","bogota dc","bogota d.c","bogota d.c."],"principal_cities":["medellin","cali","barranquilla","cartagena","bucaramanga","cucuta","pereira","manizales","santa marta","ibague","villavicencio","pasto","armenia","monteria","neiva","soledad","bello"]}
```

Qué significa:

- Bogotá = `8000`
- ciudades principales = `12000`
- nacional = `20000`
- envío gratis desde `200000`
- solo en Bogotá y ciudades principales

## 8.5 Variables operativas

### `UNO_ACCOUNT_MAP_JSON`

Para qué sirve:

- Solo si manejas múltiples cuentas WhatsApp.

Si usas una sola:

```env
UNO_ACCOUNT_MAP_JSON={}
```

### `DEFAULT_COUNTRY`

Ejemplo:

```env
DEFAULT_COUNTRY=CO
```

### `REQUEST_TIMEOUT_SECONDS`

Para qué sirve:

- Tiempo máximo de espera para llamadas HTTP.

### `PRODUCT_LIST_LIMIT`

Para qué sirve:

- Cuántos productos se muestran por lista.

Ejemplo:

```env
PRODUCT_LIST_LIMIT=10
```

### `SESSION_TTL_SECONDS`

Para qué sirve:

- Tiempo de vida de una sesión de conversación.

Ejemplo:

```env
SESSION_TTL_SECONDS=21600
```

### `NOISE_LONG_TEXT_LENGTH`

Para qué sirve:

- Ayuda a ignorar mensajes muy largos que parecen ruido.

### `NOISE_TOKEN_THRESHOLD`

Para qué sirve:

- Ayuda a ignorar mensajes con demasiadas palabras y poca intención comercial.

### `APP_PORT`

Para qué sirve:

- Puerto local de Flask.

Ejemplo:

```env
APP_PORT=5001
```

---

## 9. Ejemplo completo de `.env`

```env
ZENDER_WEBHOOK_SECRET=tu_secret_de_zender
UNO_API_BASE=https://uno.cobol.com.co/api
UNO_API_SECRET=tu_secret_de_uno
UNO_WA_ACCOUNT=tu_unique_id_de_whatsapp
UNO_ACCOUNT_MAP_JSON={}
WC_BASE_URL=https://tu-tienda.com
WC_CONSUMER_KEY=ck_xxxxxxxxx
WC_CONSUMER_SECRET=cs_xxxxxxxxx
WC_API_VERSION=wc/v3
WC_QUERY_STRING_AUTH=1
WC_WEBHOOK_SECRET=tu_secret_de_woocommerce
WC_CATEGORY_IDS_JSON={"tecnologia":24,"hogar":20,"cuidado":23,"herramientas":22,"videojuegos":29,"salud":30}
WC_UPSELL_LIMIT=2
BOT_DISCOUNT_RULES_JSON={"basis":"current_price","tiers":[{"min_qty":2,"max_qty":2,"discount_pct":5},{"min_qty":3,"discount_pct":10}]}
BOT_SHIPPING_RULES_JSON={"bogota_cost":8000,"principal_cost":12000,"national_cost":20000,"free_shipping_threshold":200000,"free_shipping_regions":["bogota","principal"],"bogota_aliases":["bogota","bogota dc","bogota d.c","bogota d.c."],"principal_cities":["medellin","cali","barranquilla","cartagena","bucaramanga","cucuta","pereira","manizales","santa marta","ibague","villavicencio","pasto","armenia","monteria","neiva","soledad","bello"]}
PRICING_RULES_URL=
PRICING_RULES_CACHE_SECONDS=300
DEFAULT_COUNTRY=CO
REQUEST_TIMEOUT_SECONDS=20
PRODUCT_LIST_LIMIT=10
SESSION_TTL_SECONDS=21600
NOISE_LONG_TEXT_LENGTH=220
NOISE_TOKEN_THRESHOLD=35
APP_PORT=5001
```

---

## 10. Cómo configurar Zender

## 10.1 Webhook principal

En Zender:

1. Ve a `Tools > Webhooks`
2. Crea el webhook
3. Usa la URL pública de tu bot
4. Usa el mismo secret que pusiste en `ZENDER_WEBHOOK_SECRET`

Ejemplo de URL:

```text
https://tu-dominio.com/zender-webhook/
```

## 10.2 Qué no deberías activar al inicio

Para evitar respuestas duplicadas, al principio evita:

- IA interna
- respuestas automáticas por keyword
- hooks adicionales que respondan al mismo mensaje

Primero deja solo el webhook principal.

---

## 11. Cómo configurar WooCommerce

## 11.1 REST API

Necesaria para:

- listar productos
- consultar variaciones
- crear pedidos
- revisar notas

Se conecta con:

- `WC_CONSUMER_KEY`
- `WC_CONSUMER_SECRET`

## 11.2 Webhook de estados del pedido

Ve a:

- `WooCommerce > Settings > Advanced > Webhooks`

Crea un webhook así:

- `Name`: `Bot WhatsApp - Estados`
- `Status`: `Active`
- `Topic`: `Order updated`
- `Delivery URL`: URL pública del webhook WooCommerce del bot
- `Secret`: el mismo valor de `WC_WEBHOOK_SECRET`
- `API version`: `WP REST API Integration v3`

Ejemplo de URL:

```text
https://tu-dominio.com/zender-webhook/woocommerce-webhook
```

## 11.3 Webhook opcional para pedido creado

Puedes crear otro igual con:

- `Topic`: `Order created`

## 11.4 Notas al cliente

Tienes dos caminos:

### Opción A. Probar con webhook / action

Si tu WooCommerce permite tema tipo `Action`, puedes probar:

- `Action`: `woocommerce_new_customer_note`

### Opción B. Usar el snippet PHP

Esta es la opción más segura.

Usa:

- [`woocommerce_customer_note_snippet.php`](woocommerce_customer_note_snippet.php)

Ese archivo toma la nota al cliente y la envía al bot directamente.

---

## 12. Snippet PHP para descuentos en WooCommerce

Si quieres que la tienda web también aplique los descuentos por cantidad, usa:

- [`woocommerce_discount_snippet.php`](woocommerce_discount_snippet.php)

Qué hace:

- 2 unidades de la misma referencia = 5%
- 3 o más unidades = 10%
- sobre el precio actual del producto

Si quieres cambiar los valores:

- edita la función `wc_bot_discount_tiers()`

---

## 13. Snippet PHP para notas al cliente

Si quieres enviar notas al cliente al bot por WhatsApp, usa:

- [`woocommerce_customer_note_snippet.php`](woocommerce_customer_note_snippet.php)

Antes de pegarlo en WordPress:

- reemplaza `WC_BOT_WEBHOOK_URL`
- reemplaza `WC_BOT_WEBHOOK_SECRET`

Y asegúrate de que `WC_BOT_WEBHOOK_SECRET` sea igual a:

- `WC_WEBHOOK_SECRET` del `.env` del bot

---

## 14. Cómo funciona el descuento

El bot trabaja con JSON de reglas.

Ejemplo:

```json
{
  "basis": "current_price",
  "tiers": [
    { "min_qty": 2, "max_qty": 2, "discount_pct": 5 },
    { "min_qty": 3, "discount_pct": 10 }
  ]
}
```

Significado:

- 2 unidades = 5%
- 3 o más = 10%
- por la misma referencia
- sobre el precio rebajado vigente

---

## 15. Cómo funciona el envío

El bot revisa la ciudad y decide si es:

- Bogotá
- ciudad principal
- nacional

Luego calcula:

- costo de envío
- si aplica envío gratis
- total final

En este proyecto, el envío gratis se evalúa **después del descuento**.

---

## 16. Cómo probar el bot

## 16.1 Pruebas básicas

Prueba mensajes como:

- `Hola`
- `Tecnología`
- `Hogar`
- `Salud`
- `Me interesa el taladro`
- `Me interesa el Combo Herramientas Taladro DeWalt Inalámbrico 34 Piezas`

## 16.2 Pruebas de compra

Haz una compra real de prueba:

1. selecciona producto
2. escribe `COMPRAR`
3. define cantidad
4. nombre
5. ciudad
6. dirección
7. referencia
8. observaciones

## 16.3 Pruebas de descuentos

- 1 unidad
- 2 unidades
- 3 unidades

## 16.4 Pruebas de envío

- Bogotá
- ciudad principal
- ciudad nacional

## 16.5 Pruebas de estados del pedido

Cambia un pedido a:

- `Processing`
- `On hold`
- `Completed`
- `Cancelled`
- `Refunded`

y revisa si llega el WhatsApp.

## 16.6 Prueba de nota al cliente

Agrega una nota al cliente en un pedido y revisa si llega por WhatsApp.

---

## 17. Errores comunes

### `Invalid webhook secret`

Revisa:

- `ZENDER_WEBHOOK_SECRET`
- `WC_WEBHOOK_SECRET`

### WooCommerce `401 cannot_view`

Suele ser:

- API key mal creada
- permisos insuficientes
- hosting bloqueando Basic Auth

En este proyecto normalmente se corrige con:

```env
WC_QUERY_STRING_AUTH=1
```

### El pedido no se crea por email inválido

El bot ya genera un email técnico si el cliente no da correo.

### El webhook de WooCommerce devuelve `403`

Suele significar que:

- `WC_WEBHOOK_SECRET` no coincide con el secret del webhook creado en WooCommerce

### La nota al cliente no llega

Prueba:

1. revisar el secret
2. revisar la URL del webhook
3. usar [`woocommerce_customer_note_snippet.php`](woocommerce_customer_note_snippet.php)

### Las categorías están cruzadas

Corrige:

- `WC_CATEGORY_IDS_JSON`

---

## 18. Recomendaciones para producción

- nunca publiques tu `.env`
- no reutilices secrets
- si compartiste secrets en chats o tickets, rótalos
- prueba compra, estados y notas antes de abrir al público
- mantén `WC_QUERY_STRING_AUTH=1` si tu hosting lo necesita

---

## 19. Checklist final antes de lanzar

- [ ] Python app funcionando
- [ ] Dependencias instaladas
- [ ] `.env` completo
- [ ] Webhook de Zender funcionando
- [ ] WooCommerce REST API funcionando
- [ ] Categorías correctas
- [ ] Descuentos correctos
- [ ] Envío correcto
- [ ] Pedido entrando en WooCommerce
- [ ] Estado del pedido llegando a WhatsApp
- [ ] Nota al cliente llegando a WhatsApp

---

## 20. Enlaces oficiales útiles

- [WooCommerce REST API keys](https://woocommerce.com/document/woocommerce-rest-api/)
- [WooCommerce webhooks](https://developer.woocommerce.com/docs/best-practices/urls-and-routing/webhooks/)
- [WooCommerce REST API docs](https://woocommerce.github.io/woocommerce-rest-api-docs/)
- [Python downloads](https://www.python.org/downloads/)

---

## 21. Resumen ultra corto

Si no quieres leer todo aún:

1. Instala Python
2. Crea entorno virtual
3. Instala dependencias
4. Llena `.env`
5. Arranca `app.py`
6. Conecta Zender
7. Conecta WooCommerce
8. Prueba compra, estados y notas

Y listo.
