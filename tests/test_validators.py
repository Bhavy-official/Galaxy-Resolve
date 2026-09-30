import pytest

from app.pipeline.textutil import is_title_case, sentence_spans, title_case, word_count
from app.pipeline.validators import (
    GOAL_RE,
    enforce_action_name,
    enforce_description,
    enforce_title,
    goal_text,
    has_url,
    is_valid_description,
    is_valid_title,
    normalize_step,
    scrub_tree,
    scrub_urls,
    template_description,
)


@pytest.mark.parametrize(
    "text",
    [
        "For help visit https://www.samsung.com/us/support today.",
        "Go to www.techcorp.com for details",
        "See [the guide](http://example.com/guide) for more.",
        "Visit samsung.com/support if the issue persists.",
        "Email kidshome.pin@TechCorp.com to reset.",
        "http://x.io",
    ],
)
def test_scrub_removes_every_url_form(text):
    out = scrub_urls(text)
    assert not has_url(out), out
    assert "http" not in out and "www." not in out and "](" not in out


def test_scrub_keeps_normal_text_and_markdown_label():
    assert scrub_urls("See [the guide](http://example.com) now.") == "See the guide now."
    assert scrub_urls("Tap Wi-Fi.") == "Tap Wi-Fi."


def test_scrub_tree_skips_deeplink_uri_fields():
    tree = {"deeplink": "voiceassist://masked/act/abc", "steps": ["Visit https://a.com now."]}
    out = scrub_tree(tree)
    assert out["deeplink"] == "voiceassist://masked/act/abc"
    assert not has_url(out["steps"][0])


def test_goal_template():
    assert goal_text("screen damage") == "Follow these steps to perform this Screen Damage Troubleshooting"
    assert goal_text("Feature Removal", "Configuration").endswith("Feature Removal Configuration")
    assert GOAL_RE.match(goal_text("Blank Screen Troubleshooting"))  # no doubled suffix
    assert "Troubleshooting Troubleshooting" not in goal_text("Blank Screen Troubleshooting")


@pytest.mark.parametrize("draft", ["Screen display damage", "screen FLICKER issue on my phone!!", "Blank", "", "Wi-Fi drops"])
def test_title_always_2_to_3_words_sentence_case(draft):
    title, _ = enforce_title(draft)
    assert is_valid_title(title), title


def test_title_valid_draft_passes_untouched():
    assert enforce_title("Screen display damage") == ("Screen display damage", True)


@pytest.mark.parametrize(
    "name",
    ["Clear the Email App's Cache and Data", "Force a Restart", "Charger Issues", "Touch Sensitivity Setting",
     "Restart Your Phone in Safe Mode", "Customize the Quick Access Panel", "Safe Mode", "X"],
)
def test_template_description_rules(name):
    d = template_description(name)
    assert d.startswith("It will ") and 5 <= word_count(d) <= 7, d


def test_description_validate_repair_fallback():
    ok = "It will clear the app cache"
    assert enforce_description(ok, "Clear Cache") == (ok, True)
    too_long = "It will facilitate secure data transfer between your devices"
    fixed, first = enforce_description(too_long, "Back Up Data", repair=lambda d, n: "It will back up your data")
    assert (fixed, first) == ("It will back up your data", False)
    fallback, _ = enforce_description(too_long, "Back Up Data", repair=lambda d, n: "still way too long for the rule here")
    assert is_valid_description(fallback)
    phrase, _ = enforce_description(None, "Touch Sensitivity Setting", verb_phrase="turn off touch sensitivity")
    assert phrase == "It will turn off touch sensitivity"


def test_title_case_and_action_names():
    assert title_case("turn off touch sensitivity") == "Turn Off Touch Sensitivity"
    assert title_case("clear the email app's cache and data") == "Clear the Email App's Cache and Data"
    assert title_case("check wi-fi on TechCorp") == "Check Wi-fi on TechCorp"
    assert enforce_action_name("Step 4: Clear the Email App's Cache and Data") == "Clear the Email App's Cache and Data"
    assert is_title_case(enforce_action_name("1. restart your device."))


def test_normalize_step():
    assert normalize_step("Next, please tap Storage") == "Tap Storage."
    assert normalize_step("Alternatively, visit https://samsung.com for help") == "Visit for help."


def test_sentence_spans_are_verbatim_and_split_runons():
    text = "Tap Apps.Tap Storage. Then tap Clear cache.\nNext line here"
    spans = [text[s:e] for s, e in sentence_spans(text)]
    assert spans == ["Tap Apps.", "Tap Storage.", "Then tap Clear cache.", "Next line here"]
