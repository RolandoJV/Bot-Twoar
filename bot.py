import logging
import json
import os
import sqlite3
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from products.load_products import DB_PATH, create_tables, clear_and_load_products
from products.categories import CATEGORIES
from products.exchange_rates import convert_to_currency, format_currency, DEFAULT_CURRENCY
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar logging para evitar exposición del token
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)


# Conexión a la base de datos
def get_db():
    return sqlite3.connect(DB_PATH)


# Obtener la moneda preferida del usuario
def get_user_currency(user_id: int) -> str:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT currency FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        return DEFAULT_CURRENCY

    currency = row[0].strip().upper()
    if currency in ['CUP', 'USDT']:
        return currency
    else:
        return DEFAULT_CURRENCY


# Actualizar la moneda preferida del usuario
def set_user_currency(user_id: int, currency: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row:
        cursor.execute("UPDATE users SET currency = ? WHERE user_id = ?",
                       (currency, user_id))
    else:
        cursor.execute("INSERT INTO users (user_id, currency) VALUES (?, ?)",
                       (user_id, currency))

    conn.commit()
    conn.close()


# --- AUTO-CREACIÓN DE LA BASE DE DATOS ---
def ensure_database():
    if not os.path.exists(DB_PATH):
        print("⚠️ Base de datos no encontrada. Creando nueva...")
        create_tables()
        clear_and_load_products()
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name, category, price FROM products LIMIT 1")
    except sqlite3.OperationalError:
        print("⚠️ Tabla 'products' dañada o ausente. Recreando...")
        create_tables()
        clear_and_load_products()
        conn.close()
        return

    try:
        cursor.execute(
            "SELECT user_id, currency, cart, total FROM users LIMIT 1")
    except sqlite3.OperationalError:
        print("⚠️ Tabla 'users' incompleta. Recreando...")
        create_tables()
        clear_and_load_products()
        conn.close()
        return

    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]
    if count == 0:
        print("⚠️ La tabla 'products' está vacía. Recargando productos...")
        clear_and_load_products()

    conn.close()


# Ejecutar verificación
ensure_database()


# Asegurar que el usuario exista
async def ensure_user_exists(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    currency = get_user_currency(user_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, currency) VALUES (?, ?)",
        (user_id, currency))
    conn.commit()
    conn.close()


# Menú principal
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await ensure_user_exists(user_id, context)
    currency = get_user_currency(user_id)

    keyboard = []
    for key, label in CATEGORIES.items():
        keyboard.append(
            [InlineKeyboardButton(label, callback_data=f'category:{key}')])

    keyboard.extend(
        [[InlineKeyboardButton("🛒 Ver Carrito", callback_data='cart')],
         [InlineKeyboardButton("💰 Pagar", callback_data='checkout')],
         [
             InlineKeyboardButton("💱 Cambiar a USDT",
                                  callback_data='set_currency:USDT'),
             InlineKeyboardButton("💱 Cambiar a CUP",
                                  callback_data='set_currency:CUP')
         ]])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_message.reply_text(
        f"¡Bienvenido a la tienda de productos digitales! 🚀\n"
        f"Moneda actual: {currency}\n\n"
        f"Elige una categoría:",
        reply_markup=reply_markup)


# Mostrar productos
async def show_products_by_category(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    category = query.data.split(':')[1]

    if category not in CATEGORIES:
        await query.answer(text="Categoría no válida.", show_alert=True)
        await query.edit_message_text("Categoría no válida.")
        return

    await query.answer(text="Cargando productos...")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, price, description FROM products WHERE category = ?",
        (category,))
    products = cursor.fetchall()
    conn.close()

    if not products:
        await query.edit_message_text(
            f"No hay productos en {CATEGORIES[category]}.")
        return

    buttons = []
    user_id = query.from_user.id
    currency = get_user_currency(user_id)

    for prod in products:
        product_id, name, price, description = prod
        price_in_currency = convert_to_currency(price, 'CUP', currency)
        btn_text = f"{name} - {format_currency(price_in_currency, currency)}"
        buttons.append([
            InlineKeyboardButton(btn_text, callback_data=f'add:{product_id}')
        ])

    buttons.append([InlineKeyboardButton("⬅️ Volver", callback_data='start')])
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(f"Productos de {CATEGORIES[category]}:",
                                  reply_markup=reply_markup)


# Añadir al carrito
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split(':')[1])
    user_id = query.from_user.id
    await ensure_user_exists(user_id, context)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name, price, description FROM products WHERE id = ?",
        (product_id,))
    product = cursor.fetchone()
    if not product:
        await query.edit_message_text("Producto no encontrado.")
        return

    cursor.execute("SELECT cart FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    cart = json.loads(row[0]) if row and row[0] else {}
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1

    current_currency = get_user_currency(user_id)

    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, cart, total, currency) VALUES (?, ?, ?, ?)",
        (user_id, json.dumps(cart), 0, current_currency))
    conn.commit()
    conn.close()

    name, price, description = product
    currency = get_user_currency(user_id)
    price_in_currency = convert_to_currency(price, 'CUP', currency)

    keyboard = [
        [InlineKeyboardButton("⬅️ Volver al Menú", callback_data='start')],
        [InlineKeyboardButton("💰 Pagar", callback_data='checkout')],
        [InlineKeyboardButton("➕ Seguir Comprando", callback_data='start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✅ {name} añadido al carrito.\n\n"
        f"📝 Descripción: {description}\n\n"
        f"💰 Precio: {format_currency(price_in_currency, currency)}\n\n"
        f"¿Qué deseas hacer?",
        reply_markup=reply_markup)


# Ver carrito
async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT cart FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        await query.edit_message_text("Tu carrito está vacío.")
        return

    cart = json.loads(row[0])
    total = 0
    items = []

    conn = get_db()
    cursor = conn.cursor()
    currency = get_user_currency(user_id)

    for prod_id, qty in cart.items():
        cursor.execute("SELECT name, price FROM products WHERE id = ?",
                       (int(prod_id),))
        prod = cursor.fetchone()
        if prod:
            name, price = prod
            unit_price = convert_to_currency(price, 'CUP', currency)
            subtotal = unit_price * qty
            total += subtotal
            items.append(
                f"• {qty}x {name} → {format_currency(subtotal, currency)}")

    conn.close()

    if not items:
        await query.edit_message_text("Tu carrito está vacío.")
        return

    items_str = "\n".join(items)
    message = f"🛒 Tu carrito:\n\n{items_str}\n\n💰 Total: {format_currency(total, currency)}\n\n¿Qué deseas hacer?"
    keyboard = [[
        InlineKeyboardButton("🗑️ Vaciar carrito", callback_data='clear_cart')
    ], [InlineKeyboardButton("💰 Pagar", callback_data='checkout')
        ], [InlineKeyboardButton("⬅️ Volver al Menú", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup)


# Vaciar carrito
async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET cart = NULL, total = 0 WHERE user_id = ?",
                   (user_id,))
    conn.commit()
    conn.close()

    await query.edit_message_text("🗑️ Carrito vaciado.")


# Checkout
async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_name = query.from_user.username or query.from_user.first_name

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT cart FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        await query.edit_message_text("Tu carrito está vacío.")
        return

    cart = json.loads(row[0])
    total = 0
    items = []

    conn = get_db()
    cursor = conn.cursor()
    currency = get_user_currency(user_id)

    for prod_id, qty in cart.items():
        cursor.execute("SELECT name, price FROM products WHERE id = ?",
                       (int(prod_id),))
        prod = cursor.fetchone()
        if prod:
            name, price = prod
            unit_price = convert_to_currency(price, 'CUP', currency)
            subtotal = unit_price * qty
            total += subtotal
            items.append(f"{qty}x {name}")

    conn.close()

    ADMIN_IDS = [6394480917, 7235352661]

    cart_items_str = "\n".join(items)
    message_to_admin = (f"🚨 NUEVA COMPRA!\n"
                        f"👤 Usuario: @{user_name} ({user_id})\n"
                        f"🛒 Productos:\n{cart_items_str}\n"
                        f"💰 Total: {format_currency(total, currency)}\n\n"
                        f"⚠️ ¡CONFIRMAR PAGO Y ENVIAR PRODUCTO MANUALMENTE!")

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(chat_id=admin_id, text=message_to_admin)

    await query.edit_message_text(
        f"🎉 Gracias por tu compra!\n"
        f"Total: {format_currency(total, currency)}\n\n"
        f"📧 Nos pondremos en contacto para que realices el pago, por favor espere.\n"
        f"Una vez confirmado, te enviaré los productos manualmente.\n\n"
        f"💡 Recuerda: No se envían productos hasta que yo confirme el pago.")


# Cambiar moneda
async def set_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    new_currency = query.data.split(':')[1]
    if new_currency not in ['CUP', 'USDT']:
        await query.edit_message_text("Moneda no válida.")
        return

    user_id = query.from_user.id
    set_user_currency(user_id, new_currency)

    currency_name = "Pesos Cubanos (CUP)" if new_currency == 'CUP' else "Tether (USDT)"
    await query.edit_message_text(
        f"✅ ¡Moneda cambiada a {currency_name}!\n\n"
        f"Todos los precios ahora se muestran en {format_currency(1, new_currency)}.\n\n"
        f"Vuelve a seleccionar una categoría para ver los precios actualizados.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Volver al Menú", callback_data='start')
        ]]))


# Handler de callbacks
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == 'start':
        await start(update, context)
    elif data.startswith('category:'):
        await show_products_by_category(update, context)
    elif data.startswith('add:'):
        await add_to_cart(update, context)
    elif data == 'cart':
        await view_cart(update, context)
    elif data == 'clear_cart':
        await clear_cart(update, context)
    elif data == 'checkout':
        await checkout(update, context)
    elif data.startswith('set_currency:'):
        await set_currency(update, context)


# Handler de errores
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:",
                 exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        await context.bot.send_message(
            chat_id=6394480917,
            text=f"⚠️ Error en el bot:\n{str(context.error)}")


# Función principal
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError(
            "❌ FALTA EL TOKEN DE TELEGRAM. Configúralo como variable de entorno."
        )

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_error_handler(error_handler)

    print("🚀 Bot iniciado. Listo para vender!")
    application.run_polling()


# Ejecución principal
if __name__ == '__main__':
    keep_alive_thread = Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    main()