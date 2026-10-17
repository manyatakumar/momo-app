"""Post archetypes + funnel classification. Pure heuristics: instant, offline, no API keys."""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class Archetype:
    key: str
    label: str
    funnel: str
    patterns: tuple[re.Pattern, ...]


def _p(*patterns: str) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(p, re.I | re.M) for p in patterns)


ARCHETYPES: dict[str, Archetype] = {a.key: a for a in (
    Archetype("vulnerability", "personal vulnerability story", "MoFU", _p(
        r"\bi (?:failed|struggled|was scared|cried|quit|got fired|got laid off|almost gave up)\b",
        r"\b(laid off|fired|burn ?out|burnt out|anxiety|depress\w*|imposter|vulnerab\w*|confession|rejected|"
        r"hardest|ashamed|panic|grief|lost my|therapy|breakdown|never told|cried|crying|tears|homesick)\b",
    )),
    Archetype("identity", "identity storytelling post", "MoFU", _p(
        r"\b(eldest daughter|elder daughter|eldest|daughter|first[- ]gen\w*|middle[- ]class|introvert\w*|identity|"
        r"\d\d[- ]year[- ]old|teenager|as a girl|as a woman|indian parents?|desi parents?|who i am|being the)\b",
    )),
    Archetype("lesson", "lesson-learned post", "MoFU", _p(
        r"\b(lessons?|learned|learnt|taught me|takeaways?|reali[sz]ed|wish i(?:'d)? known|wish i knew|mistakes?|"
        r"backfired|proud|regret\w*|went wrong|missed|hard way)\b",
    )),
    Archetype("story", "storytime post", "MoFU", _p(
        r"\b(years? ago|when i was|my first|i remember|last (?:week|month|year)|storytime|true story|i was the|"
        r"used to be|topper|now i|walked away|"
        r"my (?:dad|mom|boss|mentor|manager))\b",
    )),
    Archetype("framework", "framework deep-dive", "MoFU", _p(
        r"\b(framework|deep[- ]dive|step[- ]by[- ]step|playbook|how to|how i|my system|process|breakdown|"
        r"guide|blueprint|checklist|template)\b",
    )),
    Archetype("contrarian", "contrarian hot take", "MoFU", _p(
        r"\b(unpopular opinion|hot take|overrated|underrated|myth|nobody talks about|controversial|"
        r"stop (?:doing|saying|posting|using)|is dead|wrong about|change my mind)\b",
    )),
    Archetype("meme", "meme / pop-culture joke", "ToFU", _p(
        r"\b(economy so bad|memes?|virat|kohli|bollywood|cricket|ipl|netflix|series|episode|pov|relatable|"
        r"apple|iphones?|irony|ironic|apparently|policed|ai[- ]polic\w*|lmao|lol|💀|😭)",
    )),
    Archetype("trend", "trend reaction", "ToFU", _p(
        r"\b(trend\w*|viral|news|just (?:announced|launched|dropped)|everyone(?:'s| is)|this week|"
        r"ai|chatgpt|claude|llms?|gen ?z|tiktok|lol|lmao|noticed|observation|anyone else)\b",
    )),
    Archetype("question", "engagement question", "ToFU", _p(
        r"\?\s*$",
        r"\b(what do you think|agree\?|thoughts\?|would you rather|hot or not)",
    )),
    Archetype("results", "results/case-study post", "BoFU", _p(
        r"\b(case study|results?|revenue|roi|clients?|customers?|closed|signed|booked|grew|increased|"
        r"doubled|tripled|mrr|arr|conversion|pipeline|testimonial|before and after)\b",
        r"\d+(?:\.\d+)?\s?%",
        r"[$€£₹]\s?\d",
        r"\b\d+(?:\.\d+)?\s?(?:x|k|m)\b",
        r"\bfrom \$?\d\S* to \$?\d\S*",
    )),
)}

DEFAULT_ARCHETYPE = {"ToFU": "meme", "MoFU": "story", "BoFU": "results"}
_LIST_LINE = re.compile(r"^\s*(?:\d+[.)]|[-•*→✅])\s+\S", re.M)


@dataclass
class Classification:
    funnel: str
    archetype: str
    confidence: float  # 0..1, share of the winning funnel's score


def _raw_scores(text: str) -> dict[str, float]:
    return {k: float(sum(len(p.findall(text)) for p in a.patterns)) for k, a in ARCHETYPES.items()}


def archetype_scores(text: str) -> dict[str, float]:
    scores = _raw_scores(text)
    # The opening line is the hook — it defines what kind of post this is.
    first_line = next((ln for ln in text.splitlines() if ln.strip()), "")
    for k, s in _raw_scores(first_line).items():
        scores[k] += 1.5 * s
    if len(_LIST_LINE.findall(text)) >= 3:  # listicles read as frameworks/deep dives
        scores["framework"] += 2
    return scores


def detect_archetype(text: str) -> str:
    scores = archetype_scores(text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else ("story" if len(text) > 400 else "trend")


def classify(text: str) -> Classification:
    scores = archetype_scores(text)
    funnel_scores = {f: 0.0 for f in config.FUNNELS}
    for key, s in scores.items():
        funnel_scores[ARCHETYPES[key].funnel] += s
    # BoFU means proof: decisive when there are numbers, weak when it's just a word like "client".
    has_numbers = bool(re.search(r"\d|[$€£₹]", text))
    funnel_scores["BoFU"] *= 1.3 if has_numbers else 0.5
    if len(re.findall(r"\b(i|i'm|i've|my|me)\b", text, re.I)) >= 3:  # first-person narrative
        funnel_scores["MoFU"] += 1.0
    if len(text) > 400:
        funnel_scores["MoFU"] += 0.75
    elif len(text) < 120:
        funnel_scores["ToFU"] += 0.5

    total = sum(funnel_scores.values())
    funnel = max(config.FUNNELS, key=lambda f: funnel_scores[f])
    in_funnel = {k: s for k, s in scores.items() if ARCHETYPES[k].funnel == funnel and s > 0}
    archetype = max(in_funnel, key=in_funnel.get) if in_funnel else DEFAULT_ARCHETYPE[funnel]
    return Classification(funnel, archetype, round(funnel_scores[funnel] / total, 2) if total else 0.0)
