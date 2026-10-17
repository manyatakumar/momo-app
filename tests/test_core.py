"""Core logic tests (no Qt needed):  python -m pytest -q"""
import importlib
from datetime import date

import pytest


@pytest.fixture()
def momo(tmp_path, monkeypatch):
    monkeypatch.setenv("MOMO_HOME", str(tmp_path))
    from momo import config, db, services
    for mod in (config, db, services):
        importlib.reload(mod)
    return config, db, services


def test_classify_funnels():
    from momo.content import classify
    assert classify("Hot take: LinkedIn carousels are dead lol").funnel == "ToFU"
    assert classify("I got laid off and learned the hardest lesson of my career").funnel == "MoFU"
    assert classify("Case study: we grew a client's revenue 212% in 90 days").funnel == "BoFU"


def test_parse_posts_and_metrics():
    from momo.analyzer import parse_posts_text
    posts = parse_posts_text("date: 2026-10-06\nimpressions: 30k\ncomments: 1,204\nI got laid off.\n---\n"
                             "metrics: 1.2k impressions, 9 comments\nUnpopular opinion: stop posting daily.")
    assert [p.impressions for p in posts] == [30_000, 1_200]
    assert posts[0].comments == 1204 and posts[0].date == date(2026, 10, 6)
    assert posts[0].archetype == "vulnerability" and posts[1].archetype == "contrarian"


def test_parse_csv_export():
    from momo.analyzer import parse_csv
    raw = "Top posts\n\nPost URL,Post commentary,Impressions,Comments,Created date\nhttp://x,Our client hit $1M ARR,5400,33,10/01/2026\n"
    (p,) = parse_csv(raw)
    assert p.impressions == 5400 and p.comments == 33 and p.date == date(2026, 10, 1) and p.funnel == "BoFU"


def test_hype_references_past_winner(momo, monkeypatch):
    config, db, services = momo
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config.LINKEDIN_DIR.mkdir(parents=True)
    (config.LINKEDIN_DIR / "posts.md").write_text("date: 2026-10-06\nimpressions: 30k\nI got laid off on a Tuesday.\n")
    result = services.ingest_idea("I almost quit because of burnout")
    assert "30k impressions" in result.message
    assert result.idea.funnel == "MoFU" and result.slot is not None


def test_slots_fill_and_reclassify(momo, monkeypatch):
    config, db, services = momo
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from momo import scheduler
    a = services.ingest_idea("Hot take: carousels are dead lol")
    b = services.ingest_idea("Hot take: polls are overrated")
    assert a.slot != b.slot  # one idea per slot
    moved = services.reclassify(a.idea.id, "BoFU")
    idea = moved.idea
    assert idea.funnel == "BoFU" and config.WEEKLY_PLAN[idea.scheduled_date.weekday()].count("BoFU") == 1
    assert idea.draft and moved.draft.funnel == "BoFU"  # draft rewritten for the new funnel
    assert sum(t for _, t in scheduler.week_progress(scheduler.week_start(date.today())).values()) == 7


def test_offline_drafts_follow_voice_and_hooks():
    from momo.writer import offline
    d = offline("My mom cried when I left for Bangalore. I acted fine. I learned strong doesn't mean silent.")
    assert d.funnel == "MoFU" and d.hook_key == "confession" and d.engine == "offline"
    assert d.text.startswith("my mom cried") and "→" in d.text and "the lesson?" in d.text
    r = offline("In 3 months I made ₹1,15,643 ghostwriting for founders")
    assert r.hook_key == "receipt" and "₹1,15,643" in r.text
    t = offline("got AI policed today, apparently an emoji makes me ai, but 3 typos in one sentence")
    assert t.funnel == "ToFU" and t.hook_key == "irony" and "don't" in t.text
    assert offline("I became the one thing I used to judge about my dad, I check prices").hook_key == "withheld"
    assert offline("Saying yes to everything backfired because I had no time").hook_key == "backfire"


class _FakeAnthropic:
    calls: list = []

    def __init__(self, **_kw):
        import types
        self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(create=self._create))

    def _create(self, **kw):
        import json
        import types
        _FakeAnthropic.calls.append(kw)
        payload = {"funnel": "MoFU", "hook_key": "flex_twist", "why_this_hook": "big credential, big undercut",
                   "draft": "i was the school topper.\nnow i make memes for a living."}
        return types.SimpleNamespace(stop_reason="end_turn",
                                     content=[types.SimpleNamespace(type="text", text=json.dumps(payload))])


def test_claude_writer_request_and_fallback(monkeypatch):
    import anthropic
    import httpx
    from momo import writer
    from momo.analyzer import LinkedInProfile, PastPost

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("MOMO_AI_PROVIDER", raising=False)
    monkeypatch.setattr(anthropic, "Anthropic", _FakeAnthropic)
    profile = LinkedInProfile(about="19, IIM Bangalore", posts=[PastPost("being the eldest daughter finally paid off...",
                                                                        impressions=4400, archetype="identity")])
    d = writer.write_draft("i was the school topper and now i make memes", profile)
    assert d.engine == "claude" and d.hook_key == "flex_twist" and d.funnel == "MoFU"
    kw = _FakeAnthropic.calls[-1]
    assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default"
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert "eldest daughter" in kw["system"] and "The Flex With a Twist" in kw["system"]

    def boom(**_kw):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    monkeypatch.setattr(_FakeAnthropic, "_create", lambda self, **kw: boom(**kw))
    d2 = writer.write_draft("i was the school topper and now i make memes", profile)
    assert d2.engine == "offline" and "no internet" in d2.note


def test_gemini_writer_request_model_pick_and_fallback(monkeypatch):
    import io
    import json
    import urllib.error
    from momo import writer
    from momo.analyzer import LinkedInProfile

    assert writer.pick_gemini_model(["models/gemini-2.5-flash", "models/gemini-3.5-flash", "models/gemini-3.5-pro",
                                     "models/gemini-3.5-flash-lite", "models/embedding-001"]) == "gemini-3.5-flash"
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    monkeypatch.setenv("MOMO_AI_PROVIDER", "auto")
    monkeypatch.setattr(writer, "_gemini_model_cache", None)
    monkeypatch.setattr(writer.config, "GEMINI_MODEL", "")
    calls = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        calls.append(req)
        if req.full_url.endswith("pageSize=1000"):
            return Resp(json.dumps({"models": [{"name": "models/gemini-3.5-flash",
                                                "supportedGenerationMethods": ["generateContent"]}]}).encode())
        payload = {"funnel": "ToFU", "hook_key": "irony", "format": "short text", "why_this_hook": "deadpan irony",
                   "draft": "got AI policed again.\napparently [the rule], but typos are fine.",
                   "alt_first_lines": ["a", "b"], "first_comment": "c", "rationale": "like the AI-police post"}
        return Resp(json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}).encode())

    monkeypatch.setattr(writer.urllib.request, "urlopen", fake_urlopen)
    assert writer.provider() == "gemini"
    d = writer.write_draft("got AI policed again", LinkedInProfile(about="19, IIM Bangalore"))
    assert d.engine == "gemini" and d.hook_key == "irony" and "[fill: the rule]" in d.text
    assert d.alt_first_lines == ["a", "b"] and d.first_comment == "c"
    gen = calls[-1]
    assert gen.full_url.endswith("models/gemini-3.5-flash:generateContent")
    assert gen.get_header("X-goog-api-key") == "AIza-test"
    body = json.loads(gen.data)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "The Mirror" in body["system_instruction"]["parts"][0]["text"]

    def rejected(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 400, "bad", {},
                                     io.BytesIO(b'{"error": {"message": "API key not valid. Please pass a valid API key."}}'))
    monkeypatch.setattr(writer.urllib.request, "urlopen", rejected)
    d2 = writer.write_draft("got AI policed again", LinkedInProfile())
    assert d2.engine == "offline" and "Gemini API key was rejected" in d2.note


def test_copy_prompt_and_rotation(momo, monkeypatch):
    config, db, services = momo
    for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    a = services.ingest_idea("Saying yes to everything backfired because I had no time")
    b = services.ingest_idea("My plan to wake up at 5am backfired because I slept through my exam")
    assert a.draft.hook_key == "backfire" and b.draft.hook_key != "backfire"  # never the same hook twice in a row
    prompt = services.copy_prompt("i got ghosted after the final interview")
    assert "i got ghosted after the final interview" in prompt and "Two alternative first lines" in prompt
