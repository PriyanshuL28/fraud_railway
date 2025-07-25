# fraud_detector/urls.py

from django.urls import path
from . import views

app_name = 'fraud_detector'

urlpatterns = [
    # Health check endpoint (add this at the top)
    path('health/', views.health_check, name='health_check'),
    
    # Main pages
    path('', views.index, name='index'),
    path('upload/', views.upload_file, name='upload'),
    path('dashboard/<int:analysis_id>/', views.dashboard, name='dashboard'),
    path('claims/<int:analysis_id>/', views.claims_table, name='claims_table'),
    path('high-risk/<int:analysis_id>/', views.high_risk_claims, name='high_risk_claims'),
    path('download/<int:analysis_id>/<str:file_type>/', views.download_file, name='download_file'),
    path('visualization/<int:analysis_id>/<str:viz_type>/', views.visualization_view, name='visualization'),
    path('history/', views.analysis_history, name='analysis_history'),
    path('analysis/<int:analysis_id>/pattern_details/', views.pattern_details, name='pattern_details'),
    
    # API endpoints
    path('api/charts-data/<int:analysis_id>/', views.charts_data_api, name='charts_data_api'),
]