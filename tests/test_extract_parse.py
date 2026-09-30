import pytest

from app.cache.slots import extract_slots, slots_compatible
from app.pipeline.extract import clean_content, parse_sections, rules_extract, to_imperative
from app.pipeline.grounding import ground_steps
from app.pipeline.path_parser import build_actions, nav_targets, split_compound
from app.pipeline.types import CandidateStep, Slots


@pytest.mark.parametrize(
    "sentence,expected",
    [
        ("Tap Apps.", "Tap Apps."),
        ("First, please carefully inspect your phone.", None),  # 'carefully' is not a verb -> not a clean step
        ("Alternatively, you can schedule a repair service online.", "Schedule a repair service online."),
        ("If your device has a removable battery, please remove the battery for 60 seconds.",
         "If your device has a removable battery, remove the battery for 60 seconds."),
        ("To turn off this feature, navigate to Settings, tap Display.", "Navigate to Settings, tap Display."),
        ("On devices with a Power button: Press and hold the Power button, then tap Restart.",
         "On devices with a Power button, press and hold the Power button, then tap Restart."),
        ("Next, let's check the Liquid Damage Indicator (LDI).", "Check the Liquid Damage Indicator (LDI)."),
        ("This helps determine if the problem is with your phone.", None),
        ("Remember that passwords are case-sensitive.", None),
        ("Can't think of any useful app pairing combinations?", None),
        ("Check out our website.", None),
    ],
)
def test_to_imperative(sentence, expected):
    assert to_imperative(sentence) == expected


def test_parse_sections_strips_prefix_and_keeps_note_sections():
    content = ("Smartphone,Tablet My title ( Smartphone,Tablet): ## Step 1: Do A\nTap A.\n## Remove things\nNote\n"
               "Some note.\nTap the minus icon next to the shortcuts.\nGlossary\nTerm: definition.")
    secs = parse_sections(content, "My title")
    assert [s.title for s in secs] == ["Do A", "Remove things"]
    assert "Tap the minus icon" in secs[1].text
    assert not clean_content(content).startswith("Smartphone")


def test_rules_extract_spans_are_verbatim(siis_rows):
    for row in siis_rows:
        content = row["siis_response"]["content"]
        for st in rules_extract(parse_sections(content, row["siis_response"]["title"])):
            assert st.span in content


def _steps(*texts, section=0, title="S"):
    return [CandidateStep(t, t, section, title) for t in texts]


def test_split_compound_one_interaction_each():
    out = split_compound(_steps("Go to Settings, tap Display, and then tap Navigation bar.")[0])
    assert [s.text for s in out] == ["Go to Settings.", "Tap Display.", "Tap Navigation bar."]
    cond = split_compound(_steps("If your device has a removable battery, remove the battery for 60 seconds, and then reinsert it.")[0])
    assert [s.text for s in cond] == ["If your device has a removable battery, remove the battery for 60 seconds.", "Reinsert it."]
    frag = split_compound(_steps("Try forcing a restart by pressing the Power button, and then charging the device.")[0])
    assert len(frag) == 1  # 'charging the device' is not a command on its own


def test_nav_targets():
    assert nav_targets("Tap the switch next to Touch sensitivity to disable it.") == (["Touch sensitivity"], True)
    assert nav_targets("Go to Settings > Security and privacy > Screen lock.")[0] == ["Settings", "Security and privacy", "Screen lock"]
    assert nav_targets("Select your email app.")[0] == ["email"]
    assert nav_targets("Touch and hold the Wi-Fi icon.")[0] == []


def test_clear_cache_and_data_share_one_screen_action():
    s1 = _steps("Navigate to Settings.", "Tap Apps.", "Select your email app.", "Tap Storage.", "Tap Clear cache.")
    s2 = _steps("Navigate to Settings.", "Tap Apps.", "Select your email app.", "Tap Storage.", "Tap Clear data, and then tap OK.")
    s2[0].new_procedure = True
    actions = build_actions(s1 + s2)
    assert len(actions) == 1 and len(actions[0].groups) == 2  # One Action = One Screen (Storage)


def test_different_screens_become_different_actions():
    s = _steps("Go to Settings.", "Tap Display.", "Tap Navigation bar.", "Navigate to Settings.", "Tap Battery.", "Tap Power saving.")
    assert len(build_actions(s)) == 2


def test_grounding_drops_hallucinations():
    content = "Navigate to Settings. Tap Apps. Tap Storage. Tap Clear cache."
    steps = [
        CandidateStep("Tap Clear cache.", "Tap Clear cache.", 0, "S"),
        CandidateStep("Tap Storage.", "tap   storage.", 0, "S"),  # whitespace/case differences are fine
        CandidateStep("Update your firmware via Odin.", "Update your firmware via Odin.", 0, "S"),  # not in text
        CandidateStep("Factory reset the phone.", "Tap Clear cache.", 0, "S"),  # real span, unsupported claim
    ]
    kept, dropped = ground_steps(steps, content)
    assert [s.text for s in kept] == ["Tap Clear cache.", "Tap Storage."]
    assert len(dropped) == 2


def test_slots_and_guard():
    a = extract_slots("My phone screen is cracked and flickers")
    assert {"cracked", "flicker"} <= a.symptoms and "display" in a.domains
    b = extract_slots("battery drains fast")
    assert not slots_compatible(b, a)
    assert slots_compatible(extract_slots("screen flashing"), a)
    assert slots_compatible(Slots(), a)  # nothing detected -> no veto
