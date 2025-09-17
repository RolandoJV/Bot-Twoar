# products/exchange_rates.py

# Moneda por defecto
DEFAULT_CURRENCY = 'CUP'

# Tasas de cambio (CUP -> otra moneda)
CUP_TO_USDT_RATE = 400  # 1 USDT ≈ 400 CUP (ajusta según tu mercado real)


def convert_to_currency(amount_cup: float, from_currency: str, to_currency: str) -> float:
    """
    Convierte una cantidad en CUP a otra moneda.
    Solo soporta CUP ↔ USDT.
    """
    if from_currency == to_currency:
        return amount_cup

    if from_currency == 'CUP' and to_currency == 'USDT':
        return amount_cup / CUP_TO_USDT_RATE
    elif from_currency == 'USDT' and to_currency == 'CUP':
        return amount_cup * CUP_TO_USDT_RATE
    else:
        return amount_cup  # Fallback


def format_currency(amount: float, currency: str) -> str:
    """
    Formatea un monto numérico con su símbolo correspondiente *después* del número.

    Ejemplos:
        1800, 'CUP'  → "1800 $"
        75.0, 'USDT' → "75.00 USDT"
        1.5, 'CUP'   → "1.5 $"
    """
    if currency == 'CUP':
        # Si es entero, mostrar sin decimales; si tiene decimal, mostrar hasta 1 decimal
        if amount == int(amount):
            return f"{int(amount)} $"
        else:
            return f"{amount:.1f} $"
    elif currency == 'USDT':
        # Siempre 2 decimales, con "USDT" como texto (evitamos símbolos ambiguos)
        return f"{amount:.2f} USDT"
    else:
        return f"{amount} {currency}"  # Fallback seguro