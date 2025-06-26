# """
# URL configuration for blockchain project.

# The `urlpatterns` list routes URLs to views. For more information please see:
#     https://docs.djangoproject.com/en/5.0/topics/http/urls/
# Examples:
# Function views
#     1. Add an import:  from my_app import views
#     2. Add a URL to urlpatterns:  path('', views.home, name='home')
# Class-based views
#     1. Add an import:  from other_app.views import Home
#     2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
# Including another URLconf
#     1. Import the include() function: from django.urls import include, path
#     2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
# """
# from django.contrib import admin
# from django.urls import path, include
# from guide_page.views import introduction_view

# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('', include('bitcoin.urls')),
#     path('import_data/', include('import_data.urls')),
#     path('', introduction_view, name='home'),  # Trang chủ là Giới thiệu
#     path('guide/', include('guide_page.urls')),
#     path('user/', include('user.urls')),
# ]

from django.contrib import admin
from django.urls import path, include
from user.views import home_redirect_view  # import the view that checks login

urlpatterns = [
    path('admin/', admin.site.urls),

    # Main redirect logic at root
    path('', home_redirect_view, name='home'),

    path('import_data/', include('import_data.urls')),
    path('bitcoin/', include('bitcoin.urls')),  # Prefix bitcoin to avoid collision
    path('guide/', include('guide_page.urls')),
    path('user/', include('user.urls')),
]
