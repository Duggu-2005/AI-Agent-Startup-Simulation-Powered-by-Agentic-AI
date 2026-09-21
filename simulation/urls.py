from django.urls import path

from .views import canvas, run_simulation_view, simulation_result, startup_page

urlpatterns = [
    path("startup/", startup_page, name="startup"),
    path("canvas/", canvas, name="canvas"),
    path("run-simulation/", run_simulation_view, name="run-simulation"),
    path("simulation-result/", simulation_result, name="simulation-result"),
]