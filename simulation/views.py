import json

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .ai_graph import new_state, run_simulation


# -------------------------------------------------
# STARTUP FORM PAGE
# -------------------------------------------------
def startup_page(request):
    if request.method == "POST":
        request.session["startup_data"] = {
            "idea": request.POST.get("idea", "").strip(),
            "problem": request.POST.get("problem", "").strip(),
            "targets": request.POST.getlist("targets"),
            "solution": request.POST.get("solution", "").strip(),
            "business_type": request.POST.get("business_type", "").strip(),
            "revenue": request.POST.get("revenue", "").strip(),
            "uniqueness": request.POST.get("uniqueness", "").strip(),
        }
        request.session.pop("simulation_result", None)
        request.session.modified = True
        return redirect("canvas")

    return render(request, "startup.html")


# -------------------------------------------------
# CANVAS PAGE (the boardroom)
# -------------------------------------------------
def canvas(request):
    if "startup_data" not in request.session:
        return redirect("startup")
    return render(request, "canvas.html")


# -------------------------------------------------
# RUN THE FULL BOARDROOM DEBATE → JSON
# -------------------------------------------------
@require_POST
def run_simulation_view(request):
    startup_data = request.session.get("startup_data")
    if not startup_data:
        return JsonResponse({"error": "No startup data in session"}, status=400)

    founder_question = (request.POST.get("question") or "").strip()

    try:
        steps, final = run_simulation(startup_data, founder_question)
    except Exception as exc:
        return JsonResponse(
            {"error": f"The boardroom crashed: {exc}", "steps": [], "verdict": {}},
            status=500,
        )

    result = {
        "startup": startup_data,
        "steps": steps,
        "verdict": final.get("verdict") or {},
    }
    if final.get("error"):
        result["error"] = final["error"]
    request.session["simulation_result"] = result
    request.session.modified = True

    return JsonResponse(result)


# -------------------------------------------------
# LAST RESULT (lets the page survive a refresh)
# -------------------------------------------------
def simulation_result(request):
    # Always 200: an empty payload simply means "no saved run yet", which is
    # the normal first-load state. This avoids a noisy 404 in the browser.
    result = request.session.get("simulation_result")
    if not result:
        return JsonResponse({"result": None})
    return JsonResponse(result)