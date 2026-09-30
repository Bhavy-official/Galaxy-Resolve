"""Full rule check of a response dict. Used as the cache-write gate and by eval/run_eval.py."""
from __future__ import annotations

import re
from typing import Any, Iterable

from app.pipeline.deeplinks import DUMMY_URI
from app.pipeline.ordering import RANK
from app.pipeline.validators import GOAL_RE, has_url, is_valid_description, is_valid_name, is_valid_title
from app.schema import ContextDeeplinkResponse

_FENCE = re.compile(r"```|^\s*(here is|here's|sure)\b", re.I)


def _strings(obj: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def violations(resp: dict[str, Any], catalog_uris: set[str]) -> list[str]:
    errs: list[str] = []
    try:
        ContextDeeplinkResponse.model_validate({"contexts": resp.get("contexts", [])})
    except Exception as exc:  # pydantic ValidationError
        return [f"schema: {exc}"]
    for path, s in _strings(resp.get("contexts", []), "contexts"):
        if path.endswith(".deeplink"):
            continue
        if has_url(s):
            errs.append(f"url_leak {path}: {s!r}")
        if _FENCE.search(s):
            errs.append(f"markdown {path}")
    for gi, g in enumerate(resp.get("contexts", [])):
        p = f"contexts[{gi}]"
        if not GOAL_RE.match(g["goal"]):
            errs.append(f"goal_template {p}: {g['goal']!r}")
        if not is_valid_title(g["title"]):
            errs.append(f"title {p}: {g['title']!r}")
        if not 0.0 <= float(g["score"]) <= 1.0:
            errs.append(f"score {p}: {g['score']}")
        if not g["actions"]:
            errs.append(f"no_actions {p}")
        last_rank = -1
        for ai, a in enumerate(g["actions"]):
            ap = f"{p}.actions[{ai}]"
            cat = a.get("category") or "manual"
            if RANK[cat] < last_rank:
                errs.append(f"order {ap}: {cat} after higher-disruption action")
            last_rank = max(last_rank, RANK[cat])
            if not is_valid_name(a["actionName"]):
                errs.append(f"actionName {ap}: {a['actionName']!r}")
            if not is_valid_description(a["description"]):
                errs.append(f"description {ap}: {a['description']!r}")
            if not a["stepGroups"]:
                errs.append(f"no_step_groups {ap}")
            for si, sg in enumerate(a["stepGroups"]):
                sp = f"{ap}.stepGroups[{si}]"
                if not sg["steps"]:
                    errs.append(f"empty_steps {sp}")
                dl = sg.get("actionableDeeplink")
                if dl is not None and dl["deeplink"] != DUMMY_URI and dl["deeplink"] not in catalog_uris:
                    errs.append(f"catalog {sp}: {dl['deeplink']}")
                if cat == "manual" and dl is not None:
                    errs.append(f"manual_with_deeplink {sp}")
                if cat == "auto" and dl is None and not any(x.get("actionableDeeplink") for x in a["stepGroups"]):
                    errs.append(f"auto_without_deeplink {sp}")
                vd = sg.get("validationDeeplink")
                if vd is not None and vd["deeplink"] not in catalog_uris:
                    errs.append(f"validation_catalog {sp}: {vd['deeplink']}")
    return errs
