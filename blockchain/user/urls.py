# from django.urls import path
# from . import views

# app_name = 'user'

# urlpatterns = [
#     # URLs xác thực
#     path('', views.wallet_view, name='wallet'),
#     path('login/', views.login_view, name='login'),
#     path('register/', views.register_view, name='register'),
#     path('logout/', views.logout_view, name='logout'),
    
#     # URLs quản lý ví
#     path('wallet/', views.wallet_view, name='wallet'),
#     path('wallet/add-address/', views.add_wallet_address, name='add_wallet_address'),
#     path('wallet/delete-address/<int:address_id>/', views.delete_wallet_address, name='delete_wallet_address'),
#     path('wallet/set-primary/<int:address_id>/', views.set_primary_address, name='set_primary_address'),
    
#     # URLs hồ sơ
#     path('profile/', views.profile_view, name='profile'),
# ]

from django.urls import path
from . import views

app_name = 'user'

urlpatterns = [
    # Root redirect (handled from main urls.py)
    # path('', views.home_redirect_view, name='home'),
    # path('', views.guide_)

    # Authentication
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Wallet management
    path('wallet/', views.wallet_view, name='wallet'),
    path('wallet/add-address/', views.add_wallet_address, name='add_wallet_address'),
    path('wallet/delete-address/<int:address_id>/', views.delete_wallet_address, name='delete_wallet_address'),
    path('wallet/set-primary/<int:address_id>/', views.set_primary_address, name='set_primary_address'),
    path('wallet/refresh-balance/<int:address_id>/', views.refresh_address_balance, name='refresh_address_balance'),

    # User profile
    path('profile/', views.profile_view, name='profile'),
]
