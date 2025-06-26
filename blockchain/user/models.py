from django.db import models
from django.contrib.auth.models import User  # Sử dụng User mặc định
from django.conf import settings


# Bỏ CustomUser class - sử dụng User mặc định của Django


class WalletAddress(models.Model):
    """
    Model để lưu trữ địa chỉ ví Bitcoin của người dùng
    """
    user = models.ForeignKey(
        User,  # Sử dụng User mặc định
        on_delete=models.CASCADE, 
        related_name='wallet_addresses'
    )
    address = models.CharField(max_length=62, unique=True)  # Định dạng địa chỉ Bitcoin
    label = models.CharField(max_length=100, blank=True, help_text="Tên gợi nhớ cho địa chỉ ví")
    address_type = models.CharField(
        max_length=20,
        choices=[
            ('P2PKH', 'Pay to Public Key Hash'),
            ('P2SH', 'Pay to Script Hash'),
            ('P2WPKH', 'Pay to Witness Public Key Hash'),
            ('P2WSH', 'Pay to Witness Script Hash'),
            ('P2TR', 'Pay to Taproot'),
        ],
        default='P2PKH'
    )
    # số dư ví
    balance = models.DecimalField(max_digits=16, decimal_places=8, default=0.00000000)
    is_primary = models.BooleanField(default=False, help_text="Địa chỉ ví chính")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wallet_address'
        verbose_name = 'Địa chỉ ví'
        verbose_name_plural = 'Địa chỉ ví'
        ordering = ['-is_primary', '-created_at']
        unique_together = ['user', 'address']
    
    def __str__(self):
        return f"{self.user.username} - {self.address[:10]}..."
    
    def save(self, *args, **kwargs):
        # Đảm bảo chỉ có một địa chỉ chính cho mỗi người dùng
        if self.is_primary:
            WalletAddress.objects.filter(user=self.user, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)


class UserProfile(models.Model):
    """
    Thông tin hồ sơ mở rộng cho người dùng
    """
    user = models.OneToOneField(
        User,  # Sử dụng User mặc định
        on_delete=models.CASCADE,
        related_name='profile'
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)  # Thêm số điện thoại
    is_verified = models.BooleanField(default=False)  # Thêm trạng thái xác thực
    total_balance = models.DecimalField(max_digits=16, decimal_places=8, default=0.00000000)
    preferred_currency = models.CharField(
        max_length=10,
        choices=[
            ('BTC', 'Bitcoin'),
            ('USD', 'US Dollar'),
            ('VND', 'Vietnamese Dong'),
        ],
        default='BTC'
    )
    notifications_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profile'
        verbose_name = 'Hồ sơ người dùng'
        verbose_name_plural = 'Hồ sơ người dùng'
    
    def __str__(self):
        return f"Hồ sơ của {self.user.username}"
