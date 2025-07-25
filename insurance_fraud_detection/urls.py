# insurance_fraud_detection/urls.py
# Updated for Railway deployment with security

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from decouple import config

# Get custom admin URL from environment variable
admin_url = config('ADMIN_URL', default='admin')

urlpatterns = [
    path(f'{admin_url}/', admin.site.urls),  # Hidden admin URL
    path('fraud_detector/', include('fraud_detector.urls')),
    path('', RedirectView.as_view(url='/fraud_detector/', permanent=False)),
]

# Serve media files only in development
# Static files are served by WhiteNoise in production
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers
handler404 = 'fraud_detector.views.custom_404'
handler500 = 'fraud_detector.views.custom_500'
handler403 = 'fraud_detector.views.custom_403'