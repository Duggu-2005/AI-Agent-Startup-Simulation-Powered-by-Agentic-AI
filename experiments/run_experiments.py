import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure the repository root is importable when this script is run directly.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

# Import after Django settings are configured. The simulation engine itself is
# independent of the database and can be called directly.
from simulation.ai_graph import run_simulation


EXPERIMENTS = [
    {
        "id": "S1",
        "name": "share_market_company",
        "idea": "Open a share-market company that helps ordinary people invest in shares.",
        "problem": "Many beginners find the share market confusing and are afraid of losing money.",
        "targets": ["college students", "young workers", "first-time investors"],
        "solution": "A simple service that teaches users and helps them understand shares before investing.",
        "business_type": "financial education and investment support",
        "revenue": "subscription fee",
        "uniqueness": "Very simple explanations and beginner-focused guidance.",
        "founder_question": "Can this idea be useful without taking unsafe financial risks?",
    },
    {
        "id": "S2",
        "name": "quiz_based_exams",
        "idea": "Create a quiz platform that uses regular quizzes instead of traditional exams.",
        "problem": "Students often feel exam stress and may forget what they studied soon after an exam.",
        "targets": ["school students", "college students", "teachers"],
        "solution": "Frequent short quizzes that check learning over time and show weak topics.",
        "business_type": "education technology",
        "revenue": "school subscription",
        "uniqueness": "Continuous small quizzes instead of one large exam.",
        "founder_question": "Can frequent quizzes fairly replace major exams for students?",
    },
    {
        "id": "S3",
        "name": "nursery_plants_business",
        "idea": "Open a nursery plant business selling healthy plants for homes and gardens.",
        "problem": "People may struggle to choose plants and find healthy plants nearby.",
        "targets": ["home owners", "gardeners", "small businesses"],
        "solution": "A local plant nursery with clear plant care help and delivery.",
        "business_type": "retail nursery",
        "revenue": "plant sales and delivery fees",
        "uniqueness": "Local healthy plants with simple care guidance and delivery.",
        "founder_question": "Can a small local nursery earn enough while keeping plants healthy?",
    },
]


def run_one(spec):
    started = time.perf_counter()
    steps, final = run_simulation(spec, spec.get("founder_question", ""))
    elapsed = time.perf_counter() - started

    history = final.get("history") or []
    selected_agents = []
    for item in history:
        if item.get("kind") == "speech":
            agent = item.get("agent")
            if agent and agent not in selected_agents:
                selected_agents.append(agent)

    return {
        "experiment_id": spec["id"],
        "experiment_name": spec["name"],
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(elapsed, 3),
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        "startup_input": spec,
        "selected_agents_observed": selected_agents,
        "steps": steps,
        "history": history,
        "verdict": final.get("verdict") or {},
        "error": final.get("error"),
    }


def main():
    out_dir = ROOT / "experiment_results"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        "experiment_count": len(EXPERIMENTS),
        "experiments": [x["id"] for x in EXPERIMENTS],
        "note": "These are direct runs of the current VyavasAI simulation graph. They are experimental observations, not claims of statistical superiority.",
        "results": [],
    }

    for spec in EXPERIMENTS:
        print(f"Running {spec['id']}: {spec['name']}", flush=True)
        result = run_one(spec)

        path = out_dir / f"{spec['id']}_{spec['name']}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        manifest["results"].append({
            "experiment_id": result["experiment_id"],
            "experiment_name": result["experiment_name"],
            "duration_seconds": result["duration_seconds"],
            "selected_agents_observed": result["selected_agents_observed"],
            "verdict_overall": (result["verdict"] or {}).get("overall"),
            "error": result["error"],
            "file": str(path.relative_to(ROOT)),
        })

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
