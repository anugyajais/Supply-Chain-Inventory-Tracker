from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# We'll add viewsets here later

urlpatterns = [
    path('', include(router.urls)),
]