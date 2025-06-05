from django.urls import path
from . import views

app_name = 'bitcoin'

urlpatterns = [
    path('graph/', views.graph_view, name='graph_view'),
    path('api/address/<str:address_hash>/transactions/', views.get_address_transactions_data, name='get_address_transactions_data'),
    
    path('tx-graph/', views.tx_graph_view, name='tx_graph_view'), 
    path('api/transaction/<str:tx_hash>/graph/', views.get_transaction_graph_data, name='get_transaction_graph_data'),
    
    # URL cho cluster graph
    path('cluster-graph/', views.cluster_graph_view, name='cluster_graph_view'),
    path('api/cluster/<str:cluster_id>/graph/', views.get_cluster_graph_data, name='get_cluster_graph_data'),
      # URL cho trang danh sách giao dịch
    path('list-tx/', views.list_tx_view, name='list_tx_view'),
    path('api/transactions/list/', views.get_transactions_list, name='get_transactions_list'),
]