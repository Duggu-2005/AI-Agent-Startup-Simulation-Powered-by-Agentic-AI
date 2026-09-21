from django.shortcuts import render


def index(request):
    return render(request, "index.html")


def how_it_works(request):
    return render(request, "how-it-works.html")


def agents(request):
    return render(request, "agents.html")


def about(request):
    return render(request, "about.html")