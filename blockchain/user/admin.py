from django.contrib import admin
from django.contrib.auth.models import User
from .models import WalletAddress, UserProfile


# Không cần đăng ký CustomUser vì sử dụng User mặc định


@admin.register(WalletAddress)
class WalletAddressAdmin(admin.ModelAdmin):
    """
    Cấu hình quản trị cho model WalletAddress
    """
    list_display = ('user', 'address_short', 'label', 'address_type', 'balance', 'is_primary', 'is_active', 'created_at')
    list_filter = ('address_type', 'is_primary', 'is_active', 'created_at')
    search_fields = ('user__username', 'user__email', 'address', 'label')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    def address_short(self, obj):
        """Hiển thị địa chỉ ví rút gọn"""
        return f"{obj.address[:10]}...{obj.address[-10:]}" if len(obj.address) > 20 else obj.address
    address_short.short_description = 'Địa chỉ'
    
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('user', 'address', 'label', 'address_type')
        }),
        ('Số dư & Trạng thái', {
            'fields': ('balance', 'is_primary', 'is_active')
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    Cấu hình quản trị cho model UserProfile
    """
    list_display = ('user', 'phone_number', 'is_verified', 'total_balance', 'preferred_currency', 'notifications_enabled', 'created_at')
    list_filter = ('is_verified', 'preferred_currency', 'notifications_enabled', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone_number', 'location')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Thông tin người dùng', {
            'fields': ('user', 'avatar', 'bio', 'location', 'birth_date', 'phone_number')
        }),
        ('Trạng thái & Xác thực', {
            'fields': ('is_verified',)
        }),
        ('Thông tin ví', {
            'fields': ('total_balance', 'preferred_currency')
        }),
        ('Cài đặt', {
            'fields': ('notifications_enabled',)
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
