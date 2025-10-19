from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('rate/', views.rate, name='rate'),
    path('recommendations/', views.recommander_films, name='recommendations'),
]
