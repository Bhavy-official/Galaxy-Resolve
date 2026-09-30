from app.pipeline.ordering import apply_categories, critical_rank
from app.pipeline.types import ActionDraft, CandidateStep, GroupDraft


def _make_action(name: str, steps: list[str], has_dl: bool = False) -> ActionDraft:
    cg_steps = [
        CandidateStep(text=s, span=s, section=0, section_title="")
        for s in steps
    ]
    group = GroupDraft(
        steps=cg_steps,
        path=[],
        actionable={"deeplink": "voiceassist://dummy"} if has_dl else None,
        dl_kind="exact" if has_dl else "none"
    )

    return ActionDraft(
        name=name,
        section=0,
        section_title="General",
        groups=[group]
    )



def test_critical_subranking():
    restart = _make_action("Force Restart", ["Press and hold power button to restart."])
    safe_mode = _make_action("Safe Mode", ["Reboot into safe mode to isolate third-party apps."])
    update = _make_action("Software Update", ["Check for system software update."])
    reset = _make_action("Factory Reset", ["Wipe all data and perform a factory reset."])

    assert critical_rank(restart) < critical_rank(safe_mode)
    assert critical_rank(safe_mode) < critical_rank(update)
    assert critical_rank(update) < critical_rank(reset)


def test_topological_sort_backup_before_reset():
    # Intentionally provide reset before backup
    reset = _make_action("Factory Reset", ["Wipe all data and perform a factory reset."])
    backup = _make_action("Backup Data", ["Back up your personal data using Smart Switch."])
    display = _make_action("Display Settings", ["Adjust screen brightness."], has_dl=True)

    ordered = apply_categories([reset, backup, display])

    names = [a.name for a in ordered]
    assert names[0] == "Display Settings"  # auto first
    assert names.index("Backup Data") < names.index("Factory Reset")  # backup before reset
