import json, os, time
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
from simulation.ai_graph import run_simulation

EXPERIMENTS = [
    {
        "id": "N1",
        "name": "vernacular_exam_tutor",
        "idea": "Build an AI tutor that teaches government exam topics in Marathi and Hindi.",
        "problem": "Many exam learners understand concepts better in their local language.",
        "targets": ["SSC aspirants", "college students", "rural learners"],
        "solution": "A low-cost tutor that explains topics, creates practice questions, and tracks weak areas.",
        "business_type": "education technology",
        "revenue": "freemium subscription",
        "uniqueness": "Local-language explanations focused on government exam preparation.",
        "founder_question": "Can learners trust this tutor enough to pay for regular practice?"
    },
    {
        "id": "N2",
        "name": "kirana_inventory_ai",
        "idea": "Create a WhatsApp-based AI helper for small kirana shops to track stock and reorder items.",
        "problem": "Small shop owners often track stock by memory or notebooks and may run out of fast-selling items.",
        "targets": ["kirana owners", "small retailers", "family-run shops"],
        "solution": "Owners send simple WhatsApp messages and get stock alerts and reorder suggestions.",
        "business_type": "retail software service",
        "revenue": "monthly subscription",
        "uniqueness": "Simple WhatsApp-first stock help without complex software.",
        "founder_question": "Will small shop owners use and pay for a WhatsApp stock helper every month?"
    },
    {
        "id": "N3",
        "name": "farmer_crop_advisor",
        "idea": "Build a local-language crop advisory service for small farmers using weather and crop information.",
        "problem": "Small farmers may not get timely advice about crop care, pests, and weather risks.",
        "targets": ["small farmers", "farmer groups", "rural cooperatives"],
        "solution": "A phone-based assistant gives simple crop-care guidance and weather-risk alerts.",
        "business_type": "agri technology",
        "revenue": "cooperative subscription and advisory fee",
        "uniqueness": "Simple local-language advice designed for small farms.",
        "founder_question": "Can the service give useful advice without creating unsafe farming decisions?"
    }
]

def run_one(spec):
    started = time.perf_counter()
    steps, final = run_simulation(spec, spec.get("founder_question", ""))
    elapsed = time.perf_counter() - started
    history = final.get("history") or []
    agents = []
    for item in history:
        if item.get("kind") == "speech" and item.get("agent") not in agents:
            agents.append(item.get("agent"))
    return {
        "experiment_id": spec["id"],
        "experiment_name": spec["name"],
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(elapsed, 3),
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        "startup_input": spec,
        "selected_agents_observed": agents,
        "steps": steps,
        "history": history,
        "verdict": final.get("verdict") or {},
        "error": final.get("error")
    }

def main():
    out = ROOT / "experiment_results_new_ideas"
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        "experiment_count": len(EXPERIMENTS),
        "experiments": [x["id"] for x in EXPERIMENTS],
        "note": "Direct runs of the current VyavasAI simulation graph on three additional startup ideas. Experimental observations only.",
        "results": []
    }
    for spec in EXPERIMENTS:
        print(f"Running {spec['id']}: {spec['name']}", flush=True)
        r = run_one(spec)
        path = out / f"{spec['id']}_{spec['name']}.json"
        path.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest["results"].append({
            "experiment_id": r["experiment_id"],
            "experiment_name": r["experiment_name"],
            "duration_seconds": r["duration_seconds"],
            "selected_agents_observed": r["selected_agents_observed"],
            "verdict_overall": (r["verdict"] or {}).get("overall"),
            "scores": (r["verdict"] or {}).get("scores"),
            "error": r["error"],
            "file": str(path.relative_to(ROOT))
        })
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)

if __name__ == "__main__":
    main()
