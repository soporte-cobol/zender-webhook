# 🤖 Bot de Ventas de WhatsApp (Para Principiantes)

¡Hola! Si estás aquí, probablemente quieras instalar tu bot de ventas automático que conecta WhatsApp con tu tienda WooCommerce. No te preocupes si no sabes programar o si palabras como "Python" o "Webhooks" te suenan a chino. Esta guía está diseñada **paso a paso** para que cualquier persona pueda configurarlo de manera muy fácil.

---

## 🌟 ¿Qué hace este bot?

Este bot actúa como un vendedor virtual estrella para tu tienda. Hace que las ventas ocurran en piloto automático:

1. **Catálogo y Búsqueda Inteligente:** Si alguien escribe "quiero los zapatos rojos", el bot busca en tu tienda WooCommerce y le responde. Además, gracias a la Inteligencia Artificial (Gemini), el bot **aprende sinónimos automáticamente** cada vez que creas un producto en tu tienda.
2. **Respuestas muy Naturales:** La Inteligencia Artificial reescribe los mensajes para que suenen amigables, persuasivos y como si hablara un vendedor humano real. ¡Adiós a los robots aburridos!
3. **Carrito de Compras Completo:** Permite a tus clientes ir agregando varios productos diferentes. Muestra un resumen organizado (con separadores visuales `--------`) y totaliza los costos, incluyendo descuentos automáticos y costos de envío.
4. **Cierra Pedidos Solito:** Pide datos clave como nombre, ciudad y dirección, y crea el pedido directamente en WooCommerce.

---

## 🛠️ Lo que necesitas antes de empezar

Solo necesitas 4 cosas básicas:
1. Tu tienda de WooCommerce lista.
2. Una cuenta en [UNO COBOL / Zender](https://uno.cobol.com.co/) con un número de WhatsApp conectado.
3. Una clave gratuita de Google Gemini (te enseñamos cómo sacarla abajo).
4. El archivo principal de configuración `.env`.

---

## 🔑 Paso 1: Configurar las claves mágicas (.env)

El archivo `.env` es como el cerebro privado del bot. Guarda contraseñas y claves que solo tú debes conocer.
Ve a la carpeta del proyecto, busca un archivo llamado `.env.example`, haz una copia de este archivo y renómbralo para que quede solo como `.env`.

Ábrelo y verás varios textos que debes llenar con tu propia información. Aquí te explicamos las más importantes:

### La Inteligencia Artificial (Gemini)
Esta clave le da el superpoder al bot de hablar como humano y entender cómo busca la gente tus productos.
- Ve a [Google AI Studio](https://aistudio.google.com/) y entra con tu cuenta de Google.
- Dale clic en **"Get API Key"** y genera tu clave.
- Pégala en tu archivo `.env`:
  `GEMINI_API_KEY=tu_clave_de_google_aqui`

### El Puente con WhatsApp (Zender/UNO)
Necesitamos decirle a Zender qué bot contestará los mensajes.
- `ZENDER_WEBHOOK_SECRET=tu_clave_secreta_aqui` (Inventa una contraseña y guárdala aquí).
- `UNO_API_SECRET=tu_clave_de_uno` (La consigues en el panel de Zender).
- `UNO_WA_ACCOUNT=tu_identificador` (No es el número, es el código raro que te da Zender para tu cuenta).

### El Puente con tu Tienda (WooCommerce)
Para que el bot sepa qué vendes, conéctalo a WooCommerce:
1. En WordPress, ve a **WooCommerce > Ajustes > Avanzado > API REST**.
2. Dale a **Añadir clave**. Dale permisos de **Lectura/Escritura**.
3. Pega los datos en tu `.env`:
   `WC_BASE_URL=https://tutienda.com`
   `WC_CONSUMER_KEY=ck_xxxxxxxxxxx`
   `WC_CONSUMER_SECRET=cs_xxxxxxxxxxx`

### Configurar Webhooks de WooCommerce (Para los alias automáticos)
Para que el bot aprenda sinónimos automáticos, debes crear un "Webhook" en WooCommerce.
1. En WordPress, ve a **WooCommerce > Ajustes > Avanzado > Webhooks**.
2. Crea 2 webhooks: Uno para "Producto creado" y otro para "Producto actualizado".
3. En la "URL de entrega", pon la ruta de tu bot terminada en `/woocommerce-webhook`.
4. El "Secreto" ponlo en tu `.env`:
   `WC_WEBHOOK_SECRET=tu_secreto_aqui`

### Carpetas de Despliegue (Para Hosting / cPanel)
Para actualizar tu bot fácilmente:
- `CPANEL_REPO_DIR=/ruta/a/tu/repositorio/github`
- `CPANEL_LIVE_DIR=/ruta/a/la/carpeta/viva/public_html`

---

## 🚀 Paso 2: Despliegue en cPanel (Subir a internet)

¿Tienes tu código en GitHub y quieres que los cambios pasen automáticamente a tu hosting? Es muy simple:
Solo asegúrate de haber rellenado `CPANEL_REPO_DIR` y `CPANEL_LIVE_DIR` en tu archivo `.env`.

Luego, en la consola (o Terminal) de tu hosting, entra a la carpeta del proyecto y ejecuta este comando mágico:

```bash
bash deploy_cpanel.sh
```

**¿Qué hace este comando?**
Hace todo por ti. Descarga la versión más reciente de tu código desde GitHub, la copia a la carpeta pública donde vive el bot, revisa que no borres cosas importantes como la base de datos o el archivo `.env`, y reinicia el servicio. ¡En 2 segundos el bot queda actualizado!

---

## 🧠 Paso 3: ¿Cómo funciona la "Base de Datos de Sinónimos" automática?

Anteriormente, si vendías una "Máquina de hacer palomitas", tenías que decirle a mano al bot que si alguien pedía una "palomitera" o un "popcorn", le enviara esa máquina. ¡Eso era mucho trabajo!

Ahora, gracias a la **Inteligencia Artificial de Gemini** y a una base de datos automática (`SQLite`), cuando agregas un producto nuevo en WooCommerce, pasa lo siguiente:
1. WooCommerce le avisa al bot.
2. El bot le pregunta a Gemini: *"Oye, ¿cómo pediría un cliente esto por WhatsApp en Colombia?"*
3. Gemini le da sinónimos.
4. El bot guarda el producto y los sinónimos automáticamente.

¡Tú no tienes que hacer **NADA**! Simplemente sigue agregando tus productos en WooCommerce como siempre lo has hecho.

---

## 🛒 Paso 4: Probar el Carrito de Compras

Tu bot ahora tiene un carrito real. Prueba escribiéndole a tu número de WhatsApp:
1. **"Hola"**: El bot te responderá muy amablemente y te dará un menú.
2. **"Quiero el termo"**: Buscará el producto y te mostrará opciones.
3. Elige la variación y di la cantidad.
4. Puedes pedir **otro producto** distinto. ¡El bot organizará todo en un carrito con líneas separadoras `--------` y sumará todo correctamente!

### 🎮 Control Total del Carrito
Tus clientes tienen el control total de su compra mediante lenguaje natural:
- **Agregar más productos:** Simplemente escribiendo el nombre del producto en cualquier momento del flujo.
- **Ajustar cantidades:** Escribiendo frases como "quiero 3 unidades", "sube a 5" o "ponme solo 1".
- **Quitar productos:** Escribiendo "quita la máquina" o "ya no quiero el termo".
- **Vaciar carrito:** Escribiendo "borrar carrito" o "vaciar pedido".
- **Empezar de cero:** Escribiendo **REINICIAR** en cualquier momento.


---

### 🎉 ¡Felicidades, tienes tu bot listo!

Si te atascas en algún punto o hay un error, revisa la terminal o consola de comandos, el bot siempre te avisará qué falta. ¡Mucho éxito con tus ventas en piloto automático!
