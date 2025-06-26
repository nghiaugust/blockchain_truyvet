"""
Custom template filters for user app
"""
from django import template

register = template.Library()

@register.filter
def format_currency(value, currency_type):
    """
    Format số tiền theo loại tiền tệ
    """
    try:
        if value is None:
            value = 0
        value = float(value)
        
        if currency_type == 'USD':
            return f"${value:,.2f}"
        elif currency_type == 'VND':
            return f"{value:,.0f} ₫"
        elif currency_type == 'BTC':
            return f"{value:.8f} ₿"
        else:
            return f"{value:.8f}"
            
    except (ValueError, TypeError):
        return "0"

@register.filter
def get_currency_symbol(currency_type):
    """
    Lấy ký hiệu tiền tệ
    """
    symbols = {
        'USD': '$',
        'VND': '₫',
        'BTC': '₿'
    }
    return symbols.get(currency_type, '')

@register.filter
def multiply(value, multiplier):
    """
    Nhân hai số
    """
    try:
        return float(value) * float(multiplier)
    except (ValueError, TypeError):
        return 0
