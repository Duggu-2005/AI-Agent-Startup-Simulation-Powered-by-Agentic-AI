from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("how-it-works/", views.how_it_works, name="how_it_works"),
    path("agents/", views.agents, name="agents"),
    path("about/", views.about, name="about"),
]