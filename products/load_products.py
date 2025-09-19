# products/load_products.py

import sqlite3
import os
from products.products_data import PRODUCTS
from products.categories import CATEGORIES

# Ruta a la base de datos
DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def create_tables():
    """Crea las tablas 'products' y 'users' si no existen, y añade la columna 'currency' si es necesario."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Crear tabla products
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            delivery_info TEXT
        )
    ''')

    # Crear tabla users con columna currency
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            cart TEXT,
            total REAL DEFAULT 0,
            currency TEXT DEFAULT 'CUP'
        )
    ''')

    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS user_preferences
                   (
                       user_id INTEGER PRIMARY KEY,
                       currency TEXT DEFAULT 'CUP' -- Puede ser 'USD' o 'CUP'
                   )
                   ''')

    # Verificar si la columna 'currency' existe en la tabla users
    try:
        cursor.execute("SELECT currency FROM users LIMIT 1")
    except sqlite3.OperationalError:
        # La columna no existe → la añadimos
        cursor.execute("ALTER TABLE users ADD COLUMN currency TEXT DEFAULT 'CUP'")
        print("✅ Columna 'currency' añadida automáticamente a la tabla users.")

    conn.commit()
    conn.close()
    print("✅ Tablas 'products' y 'users' verificadas/creadas.")


def clear_and_load_products():
    """Borra todos los productos y carga los nuevos desde products_data.py."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM products")

    for i, product in enumerate(PRODUCTS):
        if len(product) != 5:
            raise ValueError(f"❌ Producto {i+1} tiene {len(product)} elementos, pero se esperan 5: {product}")
        cursor.execute('''
            INSERT INTO products (name, category, price, description, delivery_info)
            VALUES (?, ?, ?, ?, ?)
        ''', product)

    conn.commit()
    conn.close()
    print("✅ Productos cargados correctamente.")

if __name__ == "__main__":
    create_tables()
    clear_and_load_products()