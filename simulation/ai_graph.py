"""
AGENTIC VIRTUAL BOARDROOM ENGINE
================================

A self-organising team of AI agents debates a startup idea in a virtual
boardroom, exactly like a real founding team:

    START
      │
      ▼
  SUPERVISOR  ── assembles the team (2–5 relevant members) and plans R rounds
      │
      └─────────► ROUND 1 … ROUND N
                     each agent speaks (reacting to the Chair's question
                     AND the previous speaker), then the CHAIR summarises
                     the round and fires the next driving question
      │
      ▼
    JUDGE  ── scores the whole debate (market/business/revenue/tech/uniqueness)
      │
      ▼
     END

Key capabilities
----------------
- Adaptive teams      : the supervisor only invites relevant members per idea.
- Multi-round debate  : agents reply to each other and the chair, not just talk once.
- Chair / moderator   : keeps the debate focused, flags disagreements, sets agenda.
- Founder interjection: the user can drop a question into the room for a follow-up round.
- Structured verdict  : JSON scores + one honest summary + concrete next steps.
- Resilient           : graceful fallbacks if the LLM returns broken JSON.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph

load_dotenv()

# ------------------------------------------------------------------
# LLM CONFIG
# ------------------------------------------------------------------
LLM_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_AGENT_TOKENS = int(os.getenv("MAX_AGENT_TOKENS", "700"))
MAX_JUDGE_TOKENS = int(os.getenv("MAX_JUDGE_TOKENS", "1600"))

_talk_llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model=LLM_MODEL,
    temperature=0.45,
    max_tokens=MAX_AGENT_TOKENS,
)

_judge_llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model=LLM_MODEL,
    temperature=0.2,
    max_tokens=MAX_JUDGE_TOKENS,
)

# Populated when the LLM rejects our credentials so the UI can surface a
# helpful message instead of a silent, empty verdict.
_LLM_ERROR: Optional[str] = None


def _looks_like_auth_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    return (
        "authentication" in name
        or "permission" in name
        or "invalid api key" in text
        or "401" in text
        or "unauthorized" in text
    )


def _invoke(llm: ChatGroq, prompt: str) -> str:
    """Invoke the LLM and record an auth failure for the caller."""
    global _LLM_ERROR
    try:
        return llm.invoke([("human", prompt)]).content
    except Exception as exc:
        if _looks_like_auth_error(exc):
            _LLM_ERROR = (
                "The Groq API key was rejected (401 Invalid API Key). "
                "Put a valid GROQ_API_KEY in .env and restart the server."
            )
        raise

# ------------------------------------------------------------------
# STATE SCHEMA
# ------------------------------------------------------------------


def noop(_accumulator, update) -> Any:
    """Replace-with reducer: every node returns the FULL new value."""
    return update


class BoardroomState(TypedDict):
    # --- inputs ---
    idea: str
    problem: str
    targets: List[str]
    solution: str
    business_type: str
    revenue: str
    uniqueness: str
    founder_question: str  # optional user interjection to start the debate

    # --- workflow ---
    turns: Annotated[List[str], noop]        # queue of next speakers ("Chair" = round wrap-up)
    round_no: Annotated[int, noop]           # current round (1-based)
    rounds_total: Annotated[int, noop]       # planned rounds
    round_marker: Annotated[int, noop]       # history index where current round started

    # --- conversation ---
    current_message: Annotated[str, noop]
    moderator_question: Annotated[str, noop]  # the chair's driving question
    history: Annotated[List[Dict[str, Any]], noop]
    chair_note: Annotated[str, noop]          # latest chair consensus/disagreement

    # --- verdict ---
    verdict: Annotated[Optional[Dict[str, Any]], noop]
    done: Annotated[bool, noop]


# ------------------------------------------------------------------
# PROMPTS
# ------------------------------------------------------------------
SYSTEM_INTRO = """Startup idea: {idea}
Problem we solve: {problem}
How we help: {solution}
Target users: {targets}
Business type: {business_type}
Revenue model: {revenue}
What makes us different: {uniqueness}
"""

SIMPLE_LANGUAGE = """WRITE LIKE YOU ARE TALKING TO A 10-YEAR-OLD. STRICT RULES:
- Imagine you are a kind older brother or sister explaining ideas over lunch.
- Use the smallest, friendliest words. If a word sounds too big, swap it for a
  short one (say "make money" not "monetise", "start it" not "launch", "first
  version" not "MVP").
- ONE idea per sentence. Maximum 12 words per sentence.
- Say it warm and honest, like a friend. No fancy sounding sentences at all.
- Never use business or tech words: leverage, synergize, monetize, iterate,
  onboarding, holistic, paradigm, ecosystem, scalable, B2B/B2C, "quarter over
  quarter", "go-to-market", stakeholder.
- Read your reply once more. If a 10-year-old would frown at any sentence,
  rewrite that sentence in smaller words.
"""

AGENT_PROFILES = {
    "Customer": {
        "persona": "You are the CUSTOMER - you are the person who would actually use this. You want to love the idea, but you are careful.",
        "focus": "Pain points, whether you would pay, what you already use instead, trust, how it feels day to day.",
        "rules": f"Simple language:\n{SIMPLE_LANGUAGE}\n- 2-3 short lines\n- End with ONE simple question to the rest of the team",
    },
    "CEO": {
        "persona": "You are the CEO - the leader. You decide if this could grow into a real company or stay a small hobby.",
        "focus": "Big picture, how many people need this, risks, and whether the problem is worth fixing at all.",
        "rules": f"Simple language:\n{SIMPLE_LANGUAGE}\n- 2-3 short lines\n- Give a clear stance: This can work / This needs work / This is risky",
    },
    "Marketing": {
        "persona": "You are the MARKETING lead - a bouncy person full of energy who loves hooks, campaigns and word of mouth.",
        "focus": "How to reach customers, the one-line message, the first 100 users, social proof, fun growth ideas.",
        "rules": f"Simple language:\n{SIMPLE_LANGUAGE}\n- 2-3 short lines\n- Suggest ONE simple growth idea",
    },
    "Finance": {
        "persona": "You are the FINANCE lead - careful with money, you always check if the numbers make sense before anyone spends anything.",
        "focus": "Money in, money out, pricing, costs, savings, and when it starts paying for itself.",
        "rules": f"Simple language:\n{SIMPLE_LANGUAGE}\n- 2-3 short lines\n- Name the biggest money risk in everyday words",
    },
    "Tech": {
        "persona": "You are the TECH lead - a builder. You decide if we can actually make this, and how long it will take.",
        "focus": "Feasibility, the smallest first version, tech tools, time to build, the biggest building risk.",
        "rules": f"Simple language:\n{SIMPLE_LANGUAGE}\n- 2-3 short lines\n- Say if the first version is easy / medium / hard to build",
    },
}

AGENT_PROMPT = """{system_intro}

{persona}

This is round {round_no} of {rounds_total}. The CHAIR's question on the table is:
MODERATOR: {moderator_question}

{last_speaker_context}

Your job — {focus}

Rules:
{rules}
- Add NEW value only. NEVER repeat what someone already said.
- Keep it 2-4 short lines.
- Read your reply once more before sending. If a 10-year-old would not
  understand every sentence, rewrite it in smaller words.

Reply:
"""

SUPERVISOR_PROMPT = """You are the SUPERVISOR who assembles the boardroom team for a startup debate.

{system_intro}

Available members:
- Customer   (real demand / pain?)
- CEO        (can this become a company?)
- Marketing  (can we reach customers?)
- Finance    (does the money make sense?)
- Tech       (can we actually build it?)

Pick the SHORTEST relevant team (2 to 5). Skip anyone whose input would be noise.
Also decide how many debate ROUNDS are worth it (1 to 3). Use more rounds when the
problem is unusual or the team would disagree a lot.

Reply ONLY with valid JSON, no markdown fences:
{{"agents": ["CEO", "Customer", "Tech"], "rounds": 2}}
"""

CHAIR_PROMPT = """You are the CHAIR of the boardroom. A debate round just finished.

{system_intro}

Round {round_no} of {rounds_total} is over. This round's exchange:
{round_excerpt}

Write a short chair note (2-3 lines) capturing: what the team agrees on, where they
disagree, and ONE sharp question that must be answered next to move the debate forward.

Write in PLAIN LANGUAGE like you are explaining to a 10-year-old: short
sentences, everyday words, friendly. Treat "consensus", "disagreement" and
"question" like a simple conversation between friends.

Reply ONLY with valid JSON, no markdown fences:
{{"consensus": "...", "disagreement": "...", "question": "one sharp question"}}
"""

JUDGE_PROMPT = """You are a senior startup VALUATION JUDGE. A whole founding team just debated
the idea below in a boardroom.

{system_intro}

Full boardroom discussion (newest last):
{discussion}

Score each dimension 1-10:
- market:     is the problem real and big enough?
- business:   can this become a real company?
- revenue:    does the money model hold up?
- tech:       can this be built and shipped?
- uniqueness: is this different from what already exists?

The "summary" and "recommendations" MUST be in the simplest language possible:
short sentences, everyday words, no business buzzwords. A 10-year-old must
understand every single word.

Reply ONLY with valid JSON, no markdown fences:
{{
  "scores": {{"market": 7, "business": 6, "revenue": 5, "tech": 8, "uniqueness": 7}},
  "overall": 66,
  "summary": "One-line honest verdict with what to fix first. Simple words.",
  "recommendations": ["concrete next step 1", "concrete next step 2", "concrete next step 3"]
}}
"""

# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------


def _build_system_intro(state: BoardroomState) -> str:
    return SYSTEM_INTRO.format(
        idea=(state.get("idea") or "").strip(),
        problem=(state.get("problem") or "").strip(),
        solution=(state.get("solution") or "").strip(),
        targets=", ".join(state.get("targets", []) or []) or "unknown",
        business_type=(state.get("business_type") or "") or "not decided",
        revenue=(state.get("revenue") or "") or "not decided",
        uniqueness=(state.get("uniqueness") or "") or "unknown",
    )


def _extract_json(text: str) -> Optional[Any]:
    """Robust JSON extraction: strips fences, tries full parse, then brace-scan."""
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            pass
    return None


def _build_agent_chain(role: str):
    prompt = PromptTemplate(
        template=AGENT_PROMPT,
        input_variables=[
            "system_intro",
            "persona",
            "focus",
            "rules",
            "round_no",
            "rounds_total",
            "moderator_question",
            "last_speaker_context",
        ],
    )
    return (
        prompt.partial(
            persona=AGENT_PROFILES[role]["persona"],
            focus=AGENT_PROFILES[role]["focus"],
            rules=AGENT_PROFILES[role]["rules"],
        )
        | _talk_llm
        | StrOutputParser()
    )


_AGENT_CHAINS = {r: _build_agent_chain(r) for r in AGENT_PROFILES}


def _recent_history(state: BoardroomState, limit: int = 4) -> str:
    lines = []
    for h in state.get("history", [])[-limit:]:
        lines.append(f"[{h['agent']}] {h['output']}")
    return "\n".join(lines) or "No one has spoken yet."


# ------------------------------------------------------------------
# NODES
# ------------------------------------------------------------------


def supervisor_node(state: BoardroomState) -> dict:
    """Assemble the team and plan the debate rounds."""
    started = time.monotonic()
    intro = _build_system_intro(state)

    chosen: List[str] = []
    rounds = 2
    try:
        raw = _invoke(_talk_llm, SUPERVISOR_PROMPT.format(system_intro=intro))
        parsed = _extract_json(str(raw)) or {}
        agents_raw = parsed.get("agents") if isinstance(parsed, dict) else []
        if isinstance(agents_raw, list):
            chosen = [str(a).strip().capitalize() for a in agents_raw]
        r = parsed.get("rounds", 2) if isinstance(parsed, dict) else 2
        try:
            rounds = max(1, min(3, int(round(float(r)))))
        except (TypeError, ValueError):
            rounds = 2
    except Exception:
        chosen, rounds = [], 2

    known = list(AGENT_PROFILES.keys())
    chosen = [c for c in chosen if c in known]
    chosen = list(dict.fromkeys(chosen))
    if not chosen:
        chosen = known[:3]
    chosen = chosen[:5]

    # Build the turn queue: each round = each agent speaks, then the Chair wraps up.
    turns: List[str] = []
    for _round in range(rounds):
        turns.extend(chosen)
        turns.append("Chair")

    founder = (state.get("founder_question") or "").strip()
    kickoff = (
        f"Founder asks the room: {founder}"
        if founder
        else "Open the floor: who wants to react first to this idea and why?"
    )

    supervisor_msg = (
        f"Assembling the boardroom — inviting {', '.join(chosen)} for {rounds} "
        f"round{'s' if rounds > 1 else ''} of debate. Locking the doors."
    )

    return {
        "turns": turns,
        "round_no": 1,
        "rounds_total": rounds,
        "round_marker": 0,
        "current_message": supervisor_msg,
        "moderator_question": kickoff,
        "chair_note": "",
        "history": [
            {"agent": "Supervisor", "output": supervisor_msg, "round": 0, "kind": "stage"}
        ],
        "verdict": None,
        "done": False,
    }


def agent_node(role: str):
    """Factory producing a boardroom node for one team member."""

    def _run(state: BoardroomState) -> dict:
        started = time.monotonic()
        intro = _build_system_intro(state)
        round_no = state.get("round_no", 1)
        rounds_total = state.get("rounds_total", 2) or 2

        history = list(state.get("history", []))
        last_speaker_context = ""
        past_non_stage = [h for h in history if h.get("kind") != "stage"]
        if past_non_stage:
            last = past_non_stage[-1]
            last_speaker_context = (
                f"{last['agent']} just said:\n{last['output']}"
            )
        else:
            last_speaker_context = "You are opening the round."

        output = ""
        try:
            output = (
                _AGENT_CHAINS[role]
                .invoke(
                    {
                        "system_intro": intro,
                        "round_no": round_no,
                        "rounds_total": rounds_total,
                        "moderator_question": state.get("moderator_question", ""),
                        "last_speaker_context": last_speaker_context,
                    }
                )
                .strip()
            )
        except Exception:
            output = f"(The {role} could not reach the meeting just now. Please retry.)"

        # pop this speaker from the turn queue
        turns = list(state.get("turns", []))
        if turns and turns[0] == role:
            turns = turns[1:]

        history.append(
            {
                "agent": role,
                "output": output,
                "round": round_no,
                "kind": "speech",
            }
        )

        return {
            "turns": turns,
            "round_no": round_no,
            "current_message": output,
            "history": history,
        }

    return _run


def chair_node(state: BoardroomState) -> dict:
    """Wrap up the round, capture consensus/disagreement, set the next question."""
    started = time.monotonic()
    intro = _build_system_intro(state)
    round_no = state.get("round_no", 1)  # the round that just finished
    rounds_total = state.get("rounds_total", 2) or 2

    history = list(state.get("history", []))
    marker = state.get("round_marker", 0)
    current_round = [h for h in history[marker:] if h.get("kind") == "speech"]
    excerpt = "\n".join(f"[{h['agent']}] {h['output']}" for h in current_round) or "No speeches recorded."

    consensus, disagreement, question = "", "", ""
    try:
        raw = _invoke(
            _talk_llm,
            CHAIR_PROMPT.format(
                system_intro=intro,
                round_no=round_no,
                rounds_total=rounds_total,
                round_excerpt=excerpt,
            ),
        )
        parsed = _extract_json(str(raw)) or {}
        consensus = str(parsed.get("consensus", "") or "")
        disagreement = str(parsed.get("disagreement", "") or "")
        question = str(parsed.get("question", "") or "")
    except Exception:
        question = "Let's sharpen this further: what is the one thing we have not proven yet?"

    next_round_no = round_no + 1
    turns = list(state.get("turns", []))
    if turns and turns[0] == "Chair":
        turns = turns[1:]

    note = " ".join(x for x in (consensus, disagreement) if x)
    note = note or f"Round {round_no} complete."

    history.append(
        {
            "agent": "Chair",
            "output": note,
            "consensus": consensus,
            "disagreement": disagreement,
            "round": round_no,
            "kind": "chair",
        }
    )

    return {
        "turns": turns,
        "round_no": next_round_no,
        "round_marker": len(history),
        "moderator_question": question,
        "current_message": note,
        "chair_note": note,
        "history": history,
    }


def judge_node(state: BoardroomState) -> dict:
    started = time.monotonic()
    intro = _build_system_intro(state)
    history = state.get("history", [])
    discussion = "\n".join(
        f"[{h['agent']}] {h['output']}"
        for h in history
        if h.get("kind") in ("speech", "chair")
    ) or "No discussion happened."

    verdict: Dict[str, Any] = {}
    try:
        raw = _invoke(
            _judge_llm,
            JUDGE_PROMPT.format(system_intro=intro, discussion=discussion),
        )
        verdict = _extract_json(str(raw)) or {}
        if not isinstance(verdict, dict):
            verdict = {}

        # sanitize scores
        scores = verdict.get("scores")
        if not isinstance(scores, dict):
            scores = {}
        for k, v in list(scores.items()):
            try:
                scores[k] = max(1, min(10, int(round(float(v)))))
            except (TypeError, ValueError):
                scores.pop(k, None)
        verdict["scores"] = scores

        # overall: fall back to computed average when missing/invalid
        try:
            overall = int(round(float(verdict.get("overall", 0))))
        except (TypeError, ValueError):
            overall = 0
        if not 1 <= overall <= 100:
            avg = sum(scores.values()) / len(scores) if scores else 0
            verdict["overall"] = int(round(avg * 10))
        else:
            verdict["overall"] = overall

        verdict.setdefault("summary", "No clear verdict was produced.")
        recs = verdict.get("recommendations")
        verdict["recommendations"] = (
            [str(r) for r in recs] if isinstance(recs, list) else []
        )
    except Exception:
        verdict = {
            "scores": {},
            "overall": 0,
            "summary": "The judge could not score this simulation. Please retry.",
            "recommendations": [],
        }

    return {
        "verdict": verdict,
        "done": True,
        "current_message": verdict.get("summary", ""),
    }


# ------------------------------------------------------------------
# ROUTING
# ------------------------------------------------------------------


def _next_speaker(state: BoardroomState) -> str:
    turns = state.get("turns", [])
    return str(turns[0]) if turns else "Judge"


def route_after_supervisor(state: BoardroomState) -> str:
    return _next_speaker(state)


def route_after_agent(state: BoardroomState) -> str:
    return _next_speaker(state)


def route_after_chair(state: BoardroomState) -> str:
    return _next_speaker(state)


def route_after_judge(state: BoardroomState) -> str:
    return END


_NODE_NAMES = {r: r for r in AGENT_PROFILES}
_NODE_NAMES["Chair"] = "Chair"
_NODE_NAMES["Judge"] = "Judge"
_NODE_NAMES[END] = END

# ------------------------------------------------------------------
# GRAPH ASSEMBLY
# ------------------------------------------------------------------


def _build_graph():
    g = StateGraph(BoardroomState)

    g.add_node("Supervisor", supervisor_node)
    for role in AGENT_PROFILES:
        g.add_node(role, agent_node(role))
    g.add_node("Chair", chair_node)
    g.add_node("Judge", judge_node)

    g.add_edge(START, "Supervisor")
    g.add_conditional_edges("Supervisor", route_after_supervisor, _NODE_NAMES)
    for role in AGENT_PROFILES:
        g.add_conditional_edges(role, route_after_agent, _NODE_NAMES)
    g.add_conditional_edges("Chair", route_after_chair, _NODE_NAMES)
    g.add_conditional_edges("Judge", route_after_judge, _NODE_NAMES)

    return g.compile()


graph = _build_graph()

# ------------------------------------------------------------------
# PUBLIC API
# ------------------------------------------------------------------


def new_state(startup_data: dict, founder_question: str = "") -> dict:
    """Build a fresh BoardroomState from a form payload."""
    targets = startup_data.get("targets") or startup_data.get("target_users") or []
    if isinstance(targets, str):
        targets = [targets]
    return {
        "idea": startup_data.get("idea", ""),
        "problem": startup_data.get("problem", ""),
        "targets": list(targets),
        "solution": startup_data.get("solution", ""),
        "business_type": startup_data.get("business_type", ""),
        "revenue": startup_data.get("revenue", ""),
        "uniqueness": startup_data.get("uniqueness", ""),
        "founder_question": founder_question or "",
        "turns": [],
        "round_no": 0,
        "rounds_total": 2,
        "round_marker": 0,
        "current_message": "",
        "moderator_question": "",
        "history": [],
        "chair_note": "",
        "verdict": None,
        "done": False,
    }


def run_simulation(
    startup_data: dict, founder_question: str = ""
) -> tuple[List[dict], dict]:
    """Run the whole boardroom debate.

    Returns:
        steps: list of {"speaker", "round", "kind", "text"} in execution order
        final_state: BoardroomState including the judge "verdict"
    """
    global _LLM_ERROR
    _LLM_ERROR = None

    state = new_state(startup_data, founder_question)

    steps: List[dict] = []
    verdict: Dict[str, Any] = {}
    last_history: List[dict] = []

    try:
        for update in graph.stream(state, config={"recursion_limit": 60}):
            for node_name, payload in (update or {}).items():
                payload = payload or {}
                h = payload.get("history")
                if isinstance(h, list) and len(h) > len(last_history):
                    last_history = h
                if node_name == "Judge":
                    v = payload.get("verdict")
                    if isinstance(v, dict):
                        verdict = v
                    continue
                text = payload.get("current_message")
                if text:
                    steps.append(
                        {
                            "speaker": node_name,
                            "round": payload.get("round_no", 0),
                            "kind": node_name,
                            "text": text,
                        }
                    )
    except Exception:
        if not steps:
            steps.append(
                {
                    "speaker": "Supervisor",
                    "round": 0,
                    "kind": "stage",
                    "text": "The boardroom hit a snag while opening. Please try again.",
                }
            )

    final = new_state(startup_data, founder_question)
    final["history"] = last_history

    # Fallback: if the judge never yielded, derive the verdict here.
    if not verdict and last_history:
        try:
            discussion = "\n".join(
                f"[{h['agent']}] {h['output']}"
                for h in last_history
                if h.get("kind") in ("speech", "chair")
            )
            raw = _invoke(
                _judge_llm,
                JUDGE_PROMPT.format(
                    system_intro=_build_system_intro(final), discussion=discussion
                ),
            )
            parsed = _extract_json(str(raw)) or {}
            if isinstance(parsed, dict):
                verdict = parsed
        except Exception:
            verdict = {}
    if not verdict:
        verdict = {
            "scores": {},
            "overall": 0,
            "summary": "The judge could not deliver a verdict. Please retry.",
            "recommendations": [],
        }

    scores = verdict.get("scores")
    if not isinstance(scores, dict):
        scores = {}
    for k, v in list(scores.items()):
        try:
            scores[k] = max(1, min(10, int(round(float(v)))))
        except (TypeError, ValueError):
            scores.pop(k, None)
    verdict["scores"] = scores
    try:
        verdict["overall"] = max(0, min(100, int(round(float(verdict.get("overall", 0))))))
    except (TypeError, ValueError):
        verdict["overall"] = int(round((sum(scores.values()) / len(scores) * 10) if scores else 0))
    if not isinstance(verdict.get("recommendations"), list):
        verdict["recommendations"] = []

    final["verdict"] = verdict
    final["done"] = True

    if _LLM_ERROR:
        final["error"] = _LLM_ERROR

    # Append judge step for the UI.
    steps.append(
        {
            "speaker": "Judge",
            "round": 0,
            "kind": "judge",
            "text": verdict.get("summary", ""),
        }
    )

    return steps, final


# Backwards-compatible aliases
AGENT_ORDER = list(AGENT_PROFILES.keys())
agents = {r: r for r in AGENT_PROFILES}
BASE_PROMPT = SYSTEM_INTRO