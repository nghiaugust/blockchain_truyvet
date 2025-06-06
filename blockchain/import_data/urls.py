from django.urls import path
from . import views

app_name = 'import_data'

urlpatterns = [
    path('', views.import_data_view, name='import_data'),
    path('api/import-block/', views.import_block_api, name='import_block_api'),
]