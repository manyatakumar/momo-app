"""Hook library + offline draft writer.

MoFU: Gaurav Sharma's 10 middle-of-funnel storytelling hooks.
ToFU: meme formats lifted from the viral hits in my_linkedin_data/.
BoFU: proof formats (receipts, how-did-i, results).

The offline writer is deterministic and instant: it picks the best-fitting hook, fills the template with
pieces of the brain dump, and lays it out in the house voice (lowercase, short lines, → arrows). Anything it
can't infer is left as a [bracket] for you to fill. With a Claude API key, momo/writer.py writes the full
draft instead, using the same library.
"""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, replace


def _p(*patterns: str) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(p, re.I) for p in patterns)


@dataclass(frozen=True)
class Hook:
    key: str
    name: str
    funnels: tuple[str, ...]
    template: str
    rule: str
    signals: tuple[re.Pattern, ...]
    example: str = ""  # reference line from the hook set: calibration only, never her story


HOOKS: dict[str, Hook] = {h.key: h for h in (
    # ---------------------------------------------------------------- MoFU (Gaurav's 10)
    Hook("flex_twist", "The Flex With a Twist", ("MoFU",),
         "I was [the impressive thing you used to be] and now I do the complete opposite.",
         "State an impressive credential or past title in line 1, then immediately undercut it in line 2 to open "
         "a curiosity loop about why you walked away.",
         _p(r"\b(i was an?|used to be|ex[- ]|former|topper|rank(?:er)?|gold medal|walked away|left my|"
            r"complete opposite|gave up my|quit my)\b")),
    Hook("confession", "The Confession", ("MoFU",),
         "The emotional moment you didn't plan for, but the big thing you actually did.",
         "Open on a vulnerable, raw scene or feeling you'd normally hide (e.g. seeing parents cry when moving out). "
         "Keep the tone grounded with casual slang (\"gang\", \"your boy\") so it doesn't get overly heavy.",
         _p(r"\b(cried|crying|tears|parents?|mom|mum|mummy|dad|papa|moving out|moved out|left home|hostel|"
            r"homesick|emotional|scared|alone|never told|hid|hide|ashamed|felt)\b")),
    Hook("receipt", "The Receipt", ("MoFU", "BoFU"),
         "In [a time period], I spent / sent / lost / made [an exact, unrounded number] [a 3-word aside].",
         "Use precise, unrounded financial or metric data (e.g. ₹1,15,643) because money and exact stats make "
         "people stop and read twice.",
         _p(r"[₹$]\s?\d[\d,]*", r"\b(rs\.?|inr)\s?\d[\d,]*", r"\b\d[\d,]{3,}\b", r"\b(spent|sent|lost|made|earned|saved|"
            r"invested|paid|charged|lakhs?|crores?)\b")),
    Hook("how_did_i", "The \"How Did I\"", ("MoFU", "BoFU"),
         "How as a [who you were back then] I managed to [the thing people think is hard]?",
         "Frame a tactical how-to as a direct answer to a question people frequently ask you in DMs.",
         _p(r"\b(how i|how do you|people ask|dms?|managed to|as an? \w+|while studying|tips|step[- ]by[- ]step|"
            r"juggl\w*|balanc\w*|routine|system)\b")),
    Hook("fake_out", "The Fake-Out", ("MoFU",),
         "I [a strong statement nobody expects from you] and it's not what you think.",
         "Deliver a shocking line 1 that sets up a false assumption, followed immediately by line 2 flipping it "
         "into an honest twist.",
         _p(r"\bi (quit|dropped out|got fired|got rejected|failed|am leaving|left|broke up|stopped|deleted|"
            r"skipped)\b", r"not what you think", r"plot twist")),
    Hook("withheld", "The Withheld Answer", ("MoFU",),
         "I inherited / copied / became the one thing I used to hate / judge / laugh at about [a person].",
         "Open a loop using \"the one thing\" without revealing the answer in line 1, forcing them to tap "
         "\"see more\".",
         _p(r"\b(inherited|copied|became|turned into|turning into|used to hate|used to judge|laughed at|"
            r"used to laugh|cringe(?:d)? at|just like my)\b")),
    Hook("backfire", "The Backfire", ("MoFU",),
         "[A decision you were proud of] actually backfired on me because [what you didn't see coming].",
         "Share the sequel to a past win where things went wrong. End with what you changed (e.g. timeblocking, "
         "building a system) rather than self-pity.",
         _p(r"\b(backfired|went wrong|proud|overcommit\w*|said yes to everything|burn ?out|burnt out|"
            r"didn't see coming|messed up|too many|regret)\b")),
    Hook("one_liner", "The One-Liner", ("MoFU", "ToFU"),
         "[A real, slightly silly thing you're doing right now] + one line joke about it.",
         "Zero fluff, high vibe. Use between heavy strategy posts to show you're a human, not a content machine.",
         _p(r"\b(right now|currently|rn|me at|me when|today i|tonight|2 ?am|3 ?am|at the airport|in class|"
            r"in the library|studying)\b")),
    Hook("hot_take", "The Hot Take", ("MoFU", "ToFU"),
         "The popular belief in your space will not [the promise everyone makes] at least in [condition that "
         "makes you right].",
         "Argue directly with the conventional feed advice to take a sharp stand.",
         _p(r"\b(unpopular|hot take|overrated|won't|will not|doesn't work|myth|stop telling|everyone says|"
            r"people say|advice|is a lie|nobody tells)\b")),
    Hook("mirror", "The Mirror", ("MoFU",),
         "You're doing [X] daily, doing [Y] daily and still [the frustration they won't say out loud].",
         "Use rhythmic repetition (daily, daily, daily) to name the reader's exact exhaustion before stepping "
         "into your own story.",
         _p(r"\b(you're|you are|daily|every day|everyday|still not|still no|exhausted|tired of|grinding|"
            r"consistent|consistency)\b")),
    # ---------------------------------------------------------------- ToFU (from the viral hits)
    Hook("economy", "\"Economy So Bad\" Meme", ("ToFU",),
         "economy so bad, [celebrity / brand] had to [do something painfully ordinary].",
         "Pop-culture figure + mundane, relatable action. One line. Let the absurdity do the work. "
         "(Virat Kohli post: 13.4k impressions.)",
         _p(r"\beconomy\b", r"\b(price|prices|expensive|inflation|salary|broke|budget|afford)\b",
            r"(?-i:\b[A-Z][a-z]+ [A-Z][a-z]+\b)")),
    Hook("irony", "Viral Irony", ("ToFU",),
         "i got [absurd thing] today. apparently [x] makes me [y], but [obviously worse thing] don't.",
         "Deadpan, self-deprecating irony about an internet absurdity. Keep the typo-energy. "
         "(AI-police post: 25.8k impressions.)",
         _p(r"\b(apparently|policed|ai|chatgpt|somehow|meanwhile|logic|make it make sense|irony|ironic)\b")),
    Hook("juxtapose", "Visual Juxtaposition", ("ToFU",),
         "after seeing [the expensive / absurd thing], this feels more [economical] appropriate  📸",
         "A photo carries the joke; the caption is one dry line that reframes it. "
         "(Apple iPhone prices post: 31.3k impressions.)",
         _p(r"\b(after seeing|photo|pic|picture|this feels|look at this|spotted)\b")),
    # ---------------------------------------------------------------- BoFU
    Hook("result", "The Result", ("BoFU",),
         "[The client win / result, with the number]. here's exactly how we did it 👇",
         "Lead with the outcome and the metric, then the 3-5 steps as arrows. End with a soft CTA.",
         _p(r"\b(client|campaign|results?|case study|grew|views|followers|impressions|leads|signed|closed|"
            r"booked|roi|conversion)\b", r"\d+(?:\.\d+)?\s?(?:%|x|k|lakh|l)\b")),
)}

# Best funnels + reference examples, from momo_instructions.md §6 (Hook Library).
# The examples describe other people's situations: they calibrate tone, they are never her life.
_LIBRARY = {
    "flex_twist": (("MoFU",), "i was the president of Finance & Investment Cell… and now my career is complete opposite of it"),
    "confession": (("MoFU",), "seeing my mother crying was not on the bucket list gang but your boy has finally moved out.."),
    "receipt": (("BoFU", "MoFU"), "in the month of july i spent 1,15,643 to be precise"),
    "how_did_i": (("MoFU", "BoFU"), "how as a 21 year old i managed to move out from my house?"),
    "fake_out": (("MoFU", "ToFU"), "i hate posting on linkedin nowadays!! and it's not what you think"),
    "withheld": (("MoFU",), "i inherited the one thing i used to hate about my dad"),
    "backfire": (("MoFU", "BoFU"), "moving out actually backfired on me because i didn't see coming these things"),
    "one_liner": (("ToFU",), "i was staring the ceiling to get some idea i think need to stare more."),
    "hot_take": (("ToFU", "MoFU"), "ai will not make you rich at least in 2026"),
    "mirror": (("MoFU", "ToFU"), "you're posting daily, building daily, grinding daily and still can't tell if you're "
                                 "actually moving forward"),
}
HOOKS = {k: replace(h, funnels=_LIBRARY[k][0], example=_LIBRARY[k][1]) if k in _LIBRARY else h for k, h in HOOKS.items()}

DEFAULT_HOOK = {"MoFU": "confession", "ToFU": "irony", "BoFU": "result"}
_EMOTION = re.compile(r"\b(cried|crying|tears|scared|alone|homesick|emotional|ashamed|hurt|broke down|felt)\b", re.I)
_PERSON = re.compile(r"\b(?:my )?(mom|mother|mum|mummy|dad|father|papa|sister|brother|boss|manager|teacher|"
                     r"professor|grandma|nani|dadi|best friend|ex|parents)\b", re.I)


def hooks_for(funnel: str) -> list[Hook]:
    return [h for h in HOOKS.values() if funnel in h.funnels]


def rank_hooks(text: str, funnel: str) -> list[tuple[float, Hook, list[str]]]:
    """All hooks for this funnel, best fit first: (score, hook, matched words)."""
    words = len(text.split())
    ranked = []
    for h in hooks_for(funnel):
        hits = sorted({m.group(0).lower() for p in h.signals for m in p.finditer(text)})
        score = float(len(hits))
        if h.key == "one_liner" and words <= 14:
            score += 0.5  # tie-breaker for short, vibe-y dumps; real signals still win
        if h.key == DEFAULT_HOOK[funnel]:
            score += 0.01  # the safe default wins ties
        ranked.append((score, h, hits))
    ranked.sort(key=lambda t: t[0], reverse=True)
    return ranked


def pick_hook(text: str, funnel: str, avoid: set[str] | frozenset = frozenset()) -> tuple[Hook, str]:
    """Best-fitting hook + a short human reason. `avoid` = hooks the rotation rule says to rest
    (same hook twice in a row, or already used twice this week)."""
    ranked = rank_hooks(text, funnel)
    fresh = [r for r in ranked if r[1].key not in avoid]
    best_score, best, best_hits = (fresh or ranked)[0]
    rotated = bool(fresh) and ranked[0][1].key in avoid and ranked[0][0] >= 1
    if rotated:
        return best, f"rotating: you just used {ranked[0][1].name}, so switching it up"
    if best_hits:
        reason = "picked up on " + ", ".join(f"“{w}”" for w in best_hits[:3])
    elif best.key == "one_liner":
        reason = "short and punchy, so a one-liner"
    else:
        reason = "the safest fit for a raw " + funnel + " idea"
    return best, reason


# ======================================================================= offline writer

def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip().rstrip(".") for p in parts if p.strip()]


def voice(line: str) -> str:
    """House style: lowercase starts, lowercase 'i', no stiff full stops on one-liners."""
    line = line.strip()
    line = re.sub(r"\bI\b", "i", line)
    line = re.sub(r"\bI'(m|ve|d|ll)\b", r"i'\1", line)
    if line[:1].isupper() and not line[:2].isupper():
        head = line.split(" ", 1)[0]
        if head[1:].islower() or len(head) == 1:
            line = line[0].lower() + line[1:]
    return line


def _gist(text: str, words: int = 12) -> str:
    first = _sentences(text)[0] if _sentences(text) else text
    parts = first.split()
    g = " ".join(parts[:words]).rstrip(",;:—-")
    return voice(g + ("…" if len(parts) > words else ""))


def _find(pattern: str, text: str, group: int = 1) -> str | None:
    m = re.search(pattern, text, re.I)
    return m.group(group).strip() if m else None


def _with_verb(clause: str) -> str:
    """'3 typos in one sentence' -> '... don't'; leave clauses that already have a verb."""
    has_verb = re.search(r"\b(is|are|was|were|do|does|don't|doesn't|get|gets|go|goes|make|makes)\b", clause, re.I)
    return voice(clause) if has_verb else f"{voice(clause)} don't"


def _hook_lines(key: str, text: str) -> tuple[list[str], set[int]]:
    """Return the opening lines and indexes of sentences they already used."""
    sents = _sentences(text)
    first = sents[0] if sents else text
    g = _gist(text)
    used = {0}

    if key == "flex_twist":
        past = _find(r"\b(?:i was|i used to be|used to be|former|ex[- ])\s*([^,.;!?]+?)(?:\s+and\b|[,.;!?]|$)", text)
        now = _find(r"complete opposite[,;:—-]+\s*(?:i\s+)?([^.;!?]+)", text) or _find(r"\bnow (?:i )?([^,.;!?]+)", text)
        if now and "complete opposite" in now:
            now = None
        return [f"i was {past or '[the impressive thing you used to be]'} and now i do the complete opposite.",
                f"now i {now}." if now else "[what you do now: the opposite, in one line]",
                "here's why i walked away →"], used
    if key == "confession":
        idx = next((i for i, s in enumerate(sents) if _EMOTION.search(s)), 0)
        return [voice(sents[idx] if sents else g) + ".", "didn't plan for that part, gang.",
                "but here's the big thing i actually did →"], {idx}
    if key == "receipt":
        period = _find(r"\b((?:in|last|this|past)\s+(?:\d+|one|two|three|six|a)?\s*(?:days?|weeks?|months?|"
                       r"years?|semesters?|summer))\b", text)
        verb = (_find(r"\b(spent|sent|lost|made|earned|saved|invested|paid|charged)\b", text) or "made").lower()
        amount = _find(r"((?:₹|rs\.?\s?|inr\s?|\$)\s?[\d,]+(?:\.\d+)?(?:\s?(?:k|lakhs?|l|crores?|cr))?)", text) \
            or _find(r"\b(\d[\d,]{3,}(?:\.\d+)?)\b", text)
        lines = [f"{(period or 'in [time period]').lower()}, i {verb} {amount or '[exact, unrounded number]'} "
                 f"(yes, i counted)."]
        rest = _find(r"\b((?:while|by|from|as|without|ghostwriting|doing)\b[^.;!?]+)", first)
        if rest:
            lines.append(voice(rest) + ".")
        if amount and re.search(r"\d(?:\s?(k|l|lakhs?|cr|crores?))\b", amount, re.I):
            lines.append("[make that number exact: unrounded numbers stop the scroll]")
        return lines, used
    if key == "how_did_i":
        who = _find(r"\bas an? ([^,.;!?]+?)(?=\s+i\b|\s+i'|[,.;!?]|$)", text) or "19-year-old student"
        thing = _find(r"\b(?:managed to|how i)\s+([^,.;!?]+)", text) or g.rstrip("…")
        thing = re.sub(r"\s+as an? [^,.;!?]+$", "", thing)
        return [f"how as a {voice(who)} i managed to {voice(thing)}?", "you ask this in my dms every week.",
                "here's the honest answer →"], used
    if key == "fake_out":
        before, _, after = first.partition(" but ")
        lines = [f"{voice(before)} and it's not what you think."]
        lines.append(voice("but " + after) + "." if after else "[the honest twist, in one line]")
        return lines, used
    if key == "withheld":
        verb = (_find(r"\b(inherited|copied|became|turned into)\b", text) or "became").lower()
        judge = (_find(r"\b(hate|judge|laugh at|cringe at)\b", text) or "judge").lower()
        person = _find(r"\b((?:my )?(?:mom|mother|mum|mummy|dad|father|papa|sister|brother|boss|manager|teacher|"
                       r"grandma|nani|dadi|parents))\b", text) or "[a person]"
        reveal = first.split(",", 1)[1].strip() if "," in first else None
        lines = [f"i {verb} the one thing i used to {judge} about {person.lower()}.", "and honestly? i'm not even mad."]
        if reveal:
            lines += ["", f"the one thing? {voice(reveal)}."]
        return lines, used
    if key == "backfire":
        idx = next((i for i, s in enumerate(sents) if re.search(r"\b(proud|decided|chose|started|said yes|quit)\b",
                                                                s, re.I)), 0)
        decision = re.split(r"\s+because\s+|\s+(?:(?:but|and)\s+)?(?:it\s+)?(?:actually\s+)?backfired|\s+(?:made|makes) me proud",
                            sents[idx] if sents else g, flags=re.I)[0]
        cause = _find(r"\bbecause\s+([^.;!?]+)", text)
        cause = voice(cause) if cause else "[what you didn't see coming]"
        return [f"{voice(decision)} actually backfired on me because {cause}."], {idx}
    if key == "one_liner":
        jokes = ("productivity level: questionable.", "peak performance, apparently.", "character development, they call it.")
        return [g.rstrip("…") + ".", jokes[zlib.crc32(text.encode()) % len(jokes)]], set(range(len(sents)))
    if key == "hot_take":
        belief = _find(r"\b(?:everyone says|people say|they say|the advice(?: is)?|told to)\s+([^,.;!?]+)", text) \
            or "[the popular belief in your space]"
        condition = _find(r"\b(?:if|when) you(?:'re| are)?\s+([^,.;!?]+)", text) or "[the condition that makes you right]"
        return [f"{voice(belief)} will not [the promise everyone makes].", f"at least not when you're {condition}."], used
    if key == "mirror":
        acts = re.findall(r"\b([a-z]+ing(?: [a-z]+){0,2})", text.lower())
        x = acts[0] if acts else "[x]"
        y = acts[1] if len(acts) > 1 else "[y]"
        return [f"you're doing {x} daily,", f"doing {y} daily,", "and still [the frustration they won't say out loud]."], used
    if key == "economy":
        if first.lower().startswith("economy so bad"):
            return [voice(first) + "."], used
        m = re.search(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)+)\b", text)  # case-sensitive: a proper name
        subject = m.group(1) if m else "[celebrity / brand]"
        action = _find(r"\b(?:had to|has to|is now|now)\s+([^,.;!?]+)", text) or "[do something painfully ordinary]"
        return [f"economy so bad, {subject} had to {action}."], used
    if key == "irony":
        a = _find(r"\bapparently\s+([^,;!?]+?)(?:,?\s+but\b|[.;!?]|$)", text)
        b = _find(r"\bbut\s+([^.;!?]+)", text)
        if a:
            punch = _with_verb(b) if b else "[the obviously worse thing] don't"
            return ([voice(first.split("apparently")[0].rstrip(", ")) + ".", f"apparently {voice(a)}, but {punch}."],
                    set(range(len(sents))))
        return [g.rstrip("…") + ".", "apparently [the absurd rule], but [the even more absurd reality] don't."], used
    if key == "juxtapose":
        thing = _find(r"\b(?:after seeing|seeing)\s+([^,.;!?]+)", text) or g.rstrip("…")
        return [f"after seeing {voice(thing)}, this feels more [economical] appropriate",
                "[📸 attach the photo: the visual is the punchline]"], set(range(len(sents)))
    # result
    return [voice(first) + ".", "here's exactly how we did it 👇"], used


_LESSON = re.compile(r"\b(learn\w*|reali[sz]ed|lesson|taught me|now i know)\b", re.I)


def _body(text: str, used: set[int], skip_lesson: bool) -> list[str]:
    lines: list[str] = []
    for i, s in enumerate(_sentences(text)):
        if i in used or (skip_lesson and _LESSON.search(s)):
            continue
        chunks = re.split(r",\s+(?=(?:and|but|so|because|then)\b)|\s+(?=because\b)|;\s*", s) if len(s.split()) > 14 else [s]
        lines.extend(voice(c) for c in chunks if c.strip())
    if len(lines) <= 1:
        return lines
    return [lines[0]] + [f"→ {ln}" for ln in lines[1:6]]


# Sharp last lines or specific questions only: no "thoughts?", no summary paragraphs (voice rules).
_CLOSERS = {
    "ToFU": ("the bar is in hell and we're limboing.", "be honest, how many times has this happened to you this month?",
             "linkedin, never change. (please change.)"),
    "MoFU": ("what's the one thing you'd tell your 17-year-old self about this?", "if you've been here, what got you out?",
             "still figuring this out. but at least now i know what i'm figuring out."),
    "BoFU": ("what would you have done differently here?", "if you're a founder sitting on stories like this, this is "
             "exactly what i turn into content."),
}
FIRST_COMMENT = {
    "ToFU": "[fill: the meme source or one extra line of context — links go here, never in the post]",
    "MoFU": "[fill: the follow-up detail that didn't fit, or a question that keeps the comments going]",
    "BoFU": "[fill: link to the full case study / carousel PDF]",
}


def fill_placeholders(text: str) -> str:
    """[anything] -> [fill: anything], the placeholder style from the instructions."""
    return re.sub(r"\[(?!fill:)([^\]]+)\]", r"[fill: \1]", text)


def first_line(text: str, hook: Hook) -> str:
    return fill_placeholders(_hook_lines(hook.key, text)[0][0])


def alternative_openers(text: str, funnel: str, chosen: str, n: int = 2) -> list[str]:
    """1-2 alternative first lines using different hook types (writing mode §8).

    When a hook can't do more than echo the idea back, show its template with [fill: ...] spots instead."""
    idea_start = voice(_sentences(text)[0] if _sentences(text) else text).lower()[:24]
    out = []
    for _, h, _ in rank_hooks(text, funnel):
        if h.key == chosen:
            continue
        line = first_line(text, h)
        if line.lower().startswith(idea_start) or line.rstrip(".").endswith((" a", " the", " an", "…")):
            line = fill_placeholders(voice(h.template))
        if line not in out:
            out.append(line)
        if len(out) == n:
            break
    return out


def offline_draft(text: str, funnel: str, hook: Hook) -> str:
    opening, used = _hook_lines(hook.key, text)
    has_lesson_block = funnel == "MoFU" and hook.key not in ("one_liner", "backfire")
    body = _body(text, used, has_lesson_block) if hook.key not in ("one_liner", "economy", "juxtapose") else []
    if not body and (funnel == "BoFU" or hook.key == "how_did_i"):
        body = ["[the context in one line]", "→ [step 1]", "→ [step 2]", "→ [step 3]"]
    blocks = ["\n".join(opening)]
    if body:
        blocks.append("\n".join(body))
    if funnel == "MoFU" and hook.key != "one_liner":
        if hook.key == "backfire":
            blocks.append("what i changed:\n→ [the system you built: timeblocking, boundaries, a calendar that says no for you]")
        else:
            lesson = next((voice(s) for s in _sentences(text) if _LESSON.search(s)), None)
            blocks.append("the lesson?\n" + (lesson + "." if lesson else "[the one line you want them to remember]"))
    if hook.key not in ("one_liner", "juxtapose"):
        closers = _CLOSERS[funnel]
        blocks.append(closers[zlib.crc32(text.encode()) % len(closers)])
    return fill_placeholders("\n\n".join(blocks))
