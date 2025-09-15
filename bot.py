# bot.py
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Configurar logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Función para escapar caracteres de MarkdownV2
def escape_markdown_v2(text: str) -> str:
    """Escapa todos los caracteres especiales de MarkdownV2"""
    if not text:
        return ""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!\\])', r'\\\1', text)

# IDs de los administradores (¡CAMBIA ESTOS NÚMEROS POR LOS DE TÚ Y TU COMPAÑERO!)
ADMIN_IDS = [6394480917,7235352661]  # 👈 TU ID + EL DE TU COMPAÑERO

# Token de tu bot (¡REEMPLAZA CON EL TUYO!)
TOKEN = "7841676971:AAFvOe4AySZ6EcssMt3MxFyqDxqoQjKYfD0"  # 👈 TU TOKEN REAL

# Menú principal - SOLO para /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📺 STREAMING", callback_data='category:streaming')],
        [InlineKeyboardButton("🎵 MÚSICA", callback_data='category:music')],
        [InlineKeyboardButton("🔐 VPN", callback_data='category:vpn')],
        [InlineKeyboardButton("🎨 HERRAMIENTAS", callback_data='category:tools')],
        [InlineKeyboardButton("💻 LICENCIAS", callback_data='category:licenses')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        escape_markdown_v2("🌟 *Servicios Digitales Premium* 🌟\n"
                           "━━━━━━━━━━━━━━━━\n"
                           "Selecciona una categoría para ver los productos:"),
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )

# Mostrar productos por categoría
async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category = query.data.split(':')[1]

    products = {
        "streaming": [
            ("Netflix Premium", 1800),
            ("HBO Max Platino", 1150),
            ("Disney+", 1600),
            ("Prime Video", 1000),
            ("Crunchyroll", 800)
        ],
        "music": [
            ("Apple Music", 800)
        ],
        "vpn": [
            ("Surfshark VPN", 600),
            ("NordVPN", 600),
            ("PIA VPN", 600),
            ("Surfshark 2 Dispositivos", 900)
        ],
        "tools": [
            ("Canva Pro", 4600),
            ("Discord Básico", 3000),
            ("Discord Nitro", 5000),
            ("Adobe CC (2 devices)", 7500)
        ],
        "licenses": [
            ("Windows 10/11 Pro", 2500),
            ("Office 365 + Copilot", 3500),
            ("Xbox Game Pass", 5000)
        ]
    }

    if category not in products:
        await query.edit_message_text(
            escape_markdown_v2("Categoría no encontrada."),
            parse_mode='MarkdownV2'
        )
        return

    buttons = []
    for name, price in products[category]:
        price_str = f"{price:,} CUP"
        btn_text = f"{name} — {price_str}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f'product:{name}:{price}')])

    buttons.append([InlineKeyboardButton("⬅️ Volver al inicio", callback_data='start')])
    reply_markup = InlineKeyboardMarkup(buttons)

    await query.edit_message_text(
        escape_markdown_v2(f"*Productos de {category.upper()}*:\n\n"
                           "Haz clic en el producto que deseas:"),
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )

# Notificar a TODOS los administradores cuando alguien elige un producto
async def notify_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(':')
    product_name = data[1]
    price = data[2]
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name

    # Escapar nombre del producto
    safe_product_name = escape_markdown_v2(product_name)

    # Crear enlace clickeable al usuario
    if username:
        user_link = f"[{escape_markdown_v2(username)}](https://t.me/{username})"
    else:
        user_link = f"[{user_id}](https://t.me/{user_id})"

    # ✅ ¡TODOS LOS TEXTOS FIJOS TAMBIÉN SE ESCAPAN!
    message_to_admins = (
        f"🚨 *NUEVA SELECCIÓN!* 🚨\n"
        f"👤 Usuario: {user_link}\n"
        f"📦 Producto: *{safe_product_name}*\n"
        f"💰 Precio: {price} CUP\n\n"
        f"⚠️ ¡RESPONDE AL USUARIO MANUALMENTE!"
    )

    # ✅ APLICAR ESCAPE A TODO EL MENSAJE (incluyendo los textos fijos)
    message_to_admins = escape_markdown_v2(message_to_admins)

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message_to_admins,
                parse_mode='MarkdownV2'
            )
            print(f"✅ Notificación enviada a admin {admin_id}")
        except Exception as e:
            print(f"❌ Error al enviar a admin {admin_id}: {e}")

    # Mensaje al usuario (sin enlaces, solo texto simple)
    safe_product_name_user = escape_markdown_v2(product_name)
    user_message = (
        f"✅ Has seleccionado:\n\n"
        f"*{safe_product_name_user}* — {price} CUP\n\n"
        f"⏳ Pronto recibirás un mensaje de mi parte con más detalles.\n"
        f"💡 No respondas aquí, te contactaré por privado."
    )

    # ✅ También escapamos este mensaje
    user_message = escape_markdown_v2(user_message)

    await query.edit_message_text(
        user_message,
        parse_mode='MarkdownV2'
    )

# Manejador de callbacks
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith('category:'):
        await show_products(update, context)
    elif data.startswith('product:'):
        await notify_admins(update, context)
    elif data == 'start':
        keyboard = [
            [InlineKeyboardButton("📺 STREAMING", callback_data='category:streaming')],
            [InlineKeyboardButton("🎵 MÚSICA", callback_data='category:music')],
            [InlineKeyboardButton("🔐 VPN", callback_data='category:vpn')],
            [InlineKeyboardButton("🎨 HERRAMIENTAS", callback_data='category:tools')],
            [InlineKeyboardButton("💻 LICENCIAS", callback_data='category:licenses')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            escape_markdown_v2("🌟 *Servicios Digitales Premium* 🌟\n"
                               "━━━━━━━━━━━━━━━━\n"
                               "Selecciona una categoría para ver los productos:"),
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )

# Función principal
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 Bot simplificado iniciado. Notifica con enlaces clickeables.")
    application.run_polling()

if __name__ == '__main__':

    main()
