# smartinvoice/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/business/', include('business.urls')),
    path('api/products/', include('products.urls')),
    path('api/invoices/', include('invoices.urls')),
    path('api/expenses/', include('expenses.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/reports/', include('reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)