"""
Service để lấy tỷ giá hối đoái Bitcoin
"""
import requests
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class ExchangeRateService:
    """
    Service để lấy tỷ giá BTC sang các loại tiền tệ khác
    """
    
    # Tỷ giá mặc định (backup khi API không hoạt động)
    DEFAULT_RATES = {
        'USD': 45000,
        'VND': 1080000000,
        'BTC': 1
    }
    
    @staticmethod
    def get_btc_rate(target_currency='USD'):
        """
        Lấy tỷ giá BTC sang tiền tệ đích
        
        Args:
            target_currency (str): Loại tiền tệ đích (USD, VND, BTC)
            
        Returns:
            float: Tỷ giá BTC sang tiền tệ đích
        """
        if target_currency == 'BTC':
            return 1.0
        
        # Kiểm tra cache trước
        cache_key = f'btc_rate_{target_currency.lower()}'
        cached_rate = cache.get(cache_key)
        
        if cached_rate:
            return cached_rate
        
        try:
            # Thử lấy từ API (ví dụ sử dụng CoinGecko API - miễn phí)
            if target_currency == 'USD':
                rate = ExchangeRateService._get_btc_to_usd()
            elif target_currency == 'VND':
                # Lấy BTC -> USD rồi USD -> VND
                btc_usd = ExchangeRateService._get_btc_to_usd()
                usd_vnd = ExchangeRateService._get_usd_to_vnd()
                rate = btc_usd * usd_vnd
            else:
                rate = ExchangeRateService.DEFAULT_RATES.get(target_currency, 1)
            
            # Cache trong 5 phút
            cache.set(cache_key, rate, 300)
            return rate
            
        except Exception as e:
            logger.warning(f"Không thể lấy tỷ giá {target_currency}: {e}")
            return ExchangeRateService.DEFAULT_RATES.get(target_currency, 1)
    
    @staticmethod
    def _get_btc_to_usd():
        """
        Lấy tỷ giá BTC sang USD từ CoinGecko API
        """
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data['bitcoin']['usd']
            
        except Exception as e:
            logger.warning(f"Lỗi lấy tỷ giá BTC/USD: {e}")
            return ExchangeRateService.DEFAULT_RATES['USD']
    
    @staticmethod
    def _get_usd_to_vnd():
        """
        Lấy tỷ giá USD sang VND
        """
        try:
            # Có thể sử dụng API khác cho VND hoặc giá trị cố định
            # Ở đây dùng giá trị cố định 24,000 VND = 1 USD
            return 24000
            
        except Exception as e:
            logger.warning(f"Lỗi lấy tỷ giá USD/VND: {e}")
            return 24000
    
    @staticmethod
    def convert_btc_to_currency(btc_amount, target_currency):
        """
        Chuyển đổi số lượng BTC sang tiền tệ đích
        
        Args:
            btc_amount (float): Số lượng BTC
            target_currency (str): Tiền tệ đích
            
        Returns:
            float: Giá trị đã chuyển đổi
        """
        try:
            rate = ExchangeRateService.get_btc_rate(target_currency)
            return float(btc_amount) * rate
        except (ValueError, TypeError):
            return 0
    
    @staticmethod
    def get_all_rates():
        """
        Lấy tất cả tỷ giá hiện tại
        
        Returns:
            dict: Dictionary chứa tất cả tỷ giá
        """
        return {
            'USD': ExchangeRateService.get_btc_rate('USD'),
            'VND': ExchangeRateService.get_btc_rate('VND'),
            'BTC': 1.0
        }
