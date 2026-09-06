"""Deterministic Answer Composer — intent routing + Policy Guard fail-closed/downgrade."""

from __future__ import annotations

import re
from shaka_server.f1.composer.answer import Answer
from shaka_server.f1.core.enums import EpistemicStatus
from shaka_server.f1.core.types import AnswerAudit, Event
from shaka_server.f1.policy import (
    guard_action_not_outcome,
    guard_bb_sb_integrity,
    guard_bounded_absence,
    guard_conflict_must_surface,
    guard_hypothesis_not_root_cause,
    guard_invoice_not_install,
    guard_no_serial_guess,
    guard_no_topic_switch,
)
from shaka_server.f1.policy.types import PolicyResult
from shaka_server.f1.retrieval.index import SnapshotIndex
from shaka_server.f1.snapshot.pack import (
    FIXTURE_PART_ABSENT,
    FIXTURE_PART_IMPELLER,
    FixtureSnapshot,
)

_PN_RE = re.compile(r"\b(\d{5,})\b")


def _status_value(s: EpistemicStatus | str) -> str:
    return s.value if isinstance(s, EpistemicStatus) else str(s)


def _apply_policy_status(current: str, result: PolicyResult) -> str:
    if result.epistemic_status is None:
        return current
    return _status_value(result.epistemic_status)


def _audit(
    query: str,
    selected: list[str],
    policy_results: list[PolicyResult],
    status: str,
    snapshot_id: str,
) -> AnswerAudit:
    summary = "; ".join(f"{p.verdict}:{p.code}" for p in policy_results) or "allow:OK"
    return AnswerAudit(
        id=f"AUD-{abs(hash((query, snapshot_id))) % 10_000_000:07d}",
        query=query,
        intent=None,
        selected_ids=list(selected),
        policy_result=summary,
        snapshot_id=snapshot_id,
        model="deterministic-f1-t04",
        response_version="f1-t04-v1",
        epistemic_status=status,
    )


def _source_refs(snapshot: FixtureSnapshot, ids: list[str]) -> list[str]:
    by_id = snapshot.by_id()
    out: list[str] = []
    seen: set[str] = set()
    for eid in ids:
        ent = by_id.get(eid)
        if ent is None:
            continue
        kind = getattr(ent, "kind", "")
        if kind == "Source":
            ref = f"{ent.id}: {ent.title}"
            if ref not in seen:
                out.append(ref)
                seen.add(ref)
        src_ids = getattr(ent, "source_ids", None) or []
        for sid in src_ids:
            src = by_id.get(sid)
            if src is not None and getattr(src, "kind", "") == "Source":
                ref = f"{src.id}: {src.title}"
                if ref not in seen:
                    out.append(ref)
                    seen.add(ref)
        # Evidence → Source
        if kind == "Evidence":
            src = by_id.get(getattr(ent, "source_id", ""))
            if src is not None:
                ref = f"{src.id}: {src.title}"
                if ref not in seen:
                    out.append(ref)
                    seen.add(ref)
        # Claims → evidence → source
        if kind == "Claim":
            for evid in getattr(ent, "evidence_ids", []) or []:
                ev = by_id.get(evid)
                if ev is None:
                    continue
                src = by_id.get(getattr(ev, "source_id", ""))
                if src is not None:
                    ref = f"{src.id}: {src.title}"
                    if ref not in seen:
                        out.append(ref)
                        seen.add(ref)
    return out


def _detect_intent(query: str) -> str:
    q = query.lower()
    # Exact / bounded-absence part lookup first
    pns = _PN_RE.findall(query)
    if FIXTURE_PART_ABSENT in pns or FIXTURE_PART_ABSENT in q:
        return "ac06_absence"
    # Serial / asset identity BEFORE keyword service templates (impeller sides, PCU cleaned).
    # Gate D: Q08/Q09/Q10 must not topic-switch to AC-02 / AC-03.
    if _is_serial_identity_query(q):
        return "serial_identity"
    if any(k in q for k in ("motor type", "motortype", "d4", "d6", "labour", "labor")) and (
        "9631" in q or "invoice" in q or "faktura" in q or "conflict" in q or "wording" in q
    ):
        return "cf001_conflict"
    if ("d4" in q and "d6" in q) or ("conflict" in q and ("9631" in q or "labour" in q or "labor" in q)):
        return "cf001_conflict"
    if any(k in q for k in ("årsag", "aarsag", "cause", "root cause", "hvorfor", "død", "dod")):
        return "ac05_cause"
    if any(k in q for k in ("løst", "lost", "lasting", "varig", "fixed", "outcome", "fejl løst", "evc-fejlen", "evc fejlen")):
        return "ac04_outcome"
    if any(k in q for k in ("pcu", "stik", "connector", "cleaned", "renset", "gjort")) and not any(
        k in q for k in ("impeller", "impellerne")
    ):
        return "ac03_pcu_action"
    if any(k in q for k in ("begge", "both", "bb og sb", "bb/sb", "hver side", "allocation", "sides")):
        return "ac02_sides"
    if any(k in q for k in ("impeller", "impellerne", "3588475", "skiftet", "9631")):
        return "ac01_impeller"
    if pns:
        return "part_lookup"
    return "generic"


def _is_serial_identity_query(q: str) -> bool:
    """True when the query asks for serial / identity facts, not service actions."""
    serial_keys = (
        "serienummer",
        "serienumre",
        "serie nummer",
        "serie-nummer",
        "serial number",
        "serial numbers",
        "serials",
        "serialnr",
        "serial no",
        "s/n",
    )
    if any(k in q for k in serial_keys):
        return True
    if re.search(r"\bserial\b", q):
        return True
    return False


def _parse_asset_type(q: str) -> str | None:
    """Map query component words to Asset.asset_type (engine/pcu/ips/impeller)."""
    if any(k in q for k in ("impeller", "impellerne")):
        return "impeller"
    if "pcu" in q:
        return "pcu"
    if "ips" in q:
        return "ips"
    if any(k in q for k in ("motor", "engine", "motoren", "motorer", "motorerne")):
        return "engine"
    return None


def _parse_side_scope(q: str) -> str:
    """Return 'compare', 'BB', 'SB', or 'unknown' for serial/identity queries."""
    has_bb = bool(re.search(r"\bbb\b", q)) or "bagbord" in q
    has_sb = bool(re.search(r"\bsb\b", q)) or "styrbord" in q
    compare_keys = ("sammenlign", "compare", "versus", " vs ", "bb og sb", "bb/sb", "begge")
    if any(k in q for k in compare_keys) or (has_bb and has_sb):
        return "compare"
    if has_bb:
        return "BB"
    if has_sb:
        return "SB"
    return "unknown"


def compose_answer(query: str, index: SnapshotIndex, snapshot: FixtureSnapshot) -> Answer:
    """Compose a structured answer from retrieval hits + Policy Guard."""
    intent = _detect_intent(query)
    policies: list[PolicyResult] = []
    status = EpistemicStatus.UNKNOWN.value

    if intent == "ac06_absence":
        return _compose_ac06(query, index, snapshot, policies)
    if intent == "serial_identity":
        return _compose_serial_identity(query, index, snapshot, policies)
    if intent == "cf001_conflict":
        return _compose_cf001(query, index, snapshot, policies)
    if intent == "ac05_cause":
        return _compose_ac05(query, index, snapshot, policies)
    if intent == "ac04_outcome":
        return _compose_ac04(query, index, snapshot, policies)
    if intent == "ac03_pcu_action":
        return _compose_ac03(query, index, snapshot, policies)
    if intent == "ac02_sides":
        return _compose_ac02(query, index, snapshot, policies)
    if intent == "ac01_impeller":
        return _compose_ac01(query, index, snapshot, policies)

    # Generic / unknown part
    pns = _PN_RE.findall(query)
    if pns and not any(index.has_part_number(p) for p in pns):
        return _compose_ac06(query, index, snapshot, policies, part=pns[0])

    hits = index.search(query, limit=10)
    selected = [h.entity_id for h in hits]
    basis = [f"{h.kind} {h.entity_id} (score={h.score:.1f})" for h in hits[:5]]
    conclusion = (
        "Retrieved matching records from the frozen snapshot; no stronger conclusion without policy path."
        if hits
        else "No matching records in the frozen snapshot for this query."
    )
    ans = Answer(
        query=query,
        conclusion=conclusion,
        basis=basis,
        uncertainty_conflict=["Generic path — epistemic status remains unknown"],
        sources=_source_refs(snapshot, selected),
        epistemic_status=status,
        policy_results=policies,
        selected_ids=selected,
        snapshot_id=snapshot.snapshot_id,
    )
    ans.audit = _audit(query, selected, policies, status, snapshot.snapshot_id)
    return ans



def _compose_serial_identity(
    query: str,
    index: SnapshotIndex,
    snapshot: FixtureSnapshot,
    policies: list[PolicyResult],
) -> Answer:
    """Answer serial/identity queries from Asset bootstrap facts — never invent."""
    q = query.lower()
    asset_type = _parse_asset_type(q) or "engine"
    scope = _parse_side_scope(q)

    candidates = [a for a in snapshot.assets if a.asset_type == asset_type]
    if scope in {"BB", "SB"}:
        candidates = [a for a in candidates if str(a.side) == scope]
    elif scope == "compare":
        candidates = [a for a in candidates if str(a.side) in {"BB", "SB"}]
        candidates = sorted(
            candidates,
            key=lambda a: (0 if str(a.side) == "BB" else 1, a.id),
        )
    else:
        candidates = sorted(candidates, key=lambda a: a.id)

    selected: list[str] = [a.id for a in candidates]
    hits = index.search(
        query,
        keywords=["serial", "serienummer", asset_type, "bb", "sb"],
        limit=10,
    )
    for h in hits:
        kind = getattr(h.entity, "kind", "") or h.kind
        if kind == "Asset" and h.entity_id not in selected:
            selected.append(h.entity_id)

    lines: list[str] = []
    basis: list[str] = []
    uncertainty: list[str] = []
    any_documented = False
    any_unknown = False

    if not candidates:
        policies.append(guard_no_serial_guess("unknown", "blank"))
        conclusion = (
            f"No {asset_type} asset identity found in the frozen snapshot for this query. "
            "Serial remains unknown — not invented."
        )
        uncertainty.append("Scoped asset search returned no matching Asset Instance")
        status = EpistemicStatus.UNKNOWN.value
    else:
        for asset in candidates:
            serial = str(asset.serial) if asset.serial is not None else "unknown"
            if serial and serial != "unknown":
                policies.append(guard_no_serial_guess(serial, "documented"))
                any_documented = True
                lines.append(
                    f"{asset.side} {asset.asset_type} {asset.id}: serial={serial} "
                    "(documented asset bootstrap)"
                )
                basis.append(
                    f"Asset {asset.id}: side={asset.side}, serial={serial}, source=documented"
                )
            else:
                policies.append(guard_no_serial_guess("unknown", "blank"))
                any_unknown = True
                lines.append(
                    f"{asset.side} {asset.asset_type} {asset.id}: serial=unknown "
                    "(not documented in asset bootstrap — not invented)"
                )
                basis.append(f"Asset {asset.id}: side={asset.side}, serial=unknown")
                uncertainty.append(
                    f"Serial for {asset.id} is unknown; refusing guess or sibling inference"
                )

        basis.append("Policy: NO_SERIAL_GUESS — only documented asset serials")
        basis.append(
            "Routed via serial_identity — not service-action templates (impeller/PCU)"
        )

        if scope == "compare" and len(candidates) >= 2:
            conclusion = (
                "BB vs SB serial identity from asset bootstrap: "
                + "; ".join(lines)
                + "."
            )
        elif len(lines) == 1:
            conclusion = lines[0] + "."
        else:
            conclusion = "Asset serial identity: " + "; ".join(lines) + "."

        if any_documented and not any_unknown:
            status = EpistemicStatus.DOCUMENTED.value
        elif any_documented and any_unknown:
            status = EpistemicStatus.UNKNOWN.value
            uncertainty.append("Mixed documented/unknown serials across requested sides")
        else:
            status = EpistemicStatus.UNKNOWN.value

    forbidden = ("impeller kits", "cleaned (faktura", "both motors' impellers")
    low = conclusion.lower()
    if any(f in low for f in forbidden):
        conclusion = "Serial identity path refused service-template topic switch."
        policies.append(guard_no_topic_switch("serial_identity", "service_template"))

    for p in policies:
        if (
            p.verdict in {"downgrade", "reject"}
            and p.epistemic_status is not None
            and _status_value(p.epistemic_status) == EpistemicStatus.UNKNOWN.value
        ):
            status = EpistemicStatus.UNKNOWN.value

    ans = Answer(
        query=query,
        conclusion=conclusion,
        basis=basis,
        uncertainty_conflict=uncertainty
        or ["Serial identity scoped to Asset Instance facts only"],
        sources=_source_refs(snapshot, selected),
        epistemic_status=status,
        policy_results=policies,
        selected_ids=selected,
        snapshot_id=snapshot.snapshot_id,
    )
    ans.audit = _audit(query, selected, policies, status, snapshot.snapshot_id)
    return ans


def _compose_ac01(
    query: str,
    index: SnapshotIndex,
    snapshot: FixtureSnapshot,
    policies: list[PolicyResult],
) -> Answer:
    hits = index.search(
        query,
        keywords=["impeller", "9631", FIXTURE_PART_IMPELLER, "faktura", "invoice"],
        limit=15,
    )
    event = next((h.entity for h in hits if isinstance(h.entity, Event) and "9631" in h.entity_id), None)
    if event is None:
        event = next((e for e in snapshot.events if e.id == "EVT-FAKTURA-9631-IMPELLER"), None)

    selected: list[str] = []
    if event is not None:
        selected.append(event.id)
        selected.extend(event.source_ids or [])
        selected.extend(event.evidence_ids or [])

    claim = next((c for c in snapshot.claims if c.id == "CLM-IMPELLER-INVOICED-2024"), None)
    if claim:
        selected.append(claim.id)

    # Invoice ≠ install / action ≠ lasting outcome
    if event is not None:
        policies.append(guard_invoice_not_install(event, "install"))
    if claim is not None:
        policies.append(guard_action_not_outcome(claim, "lasting_fix"))

    status = EpistemicStatus.INVOICED_WITHOUT_ACTION.value
    for p in policies:
        if p.verdict in {"downgrade", "reject"}:
            status = _apply_policy_status(status, p)

    date = event.time_or_period if event else "unknown"
    conclusion = (
        f"Impeller kits ({FIXTURE_PART_IMPELLER} ×2) appear on Faktura 9631 "
        f"(event date/period {date}). This is an invoiced service record — "
        "not proof of install or lasting replacement outcome."
    )
    basis = [
        f"Event {event.id if event else 'missing'}: role=invoiced, time={date}",
        f"Part {FIXTURE_PART_IMPELLER} ×2 on invoice 9631",
        "Source SRC-FAKTURA-9631 linked via evidence",
        "Policy: invoice ≠ install; action ≠ lasting outcome",
    ]
    uncertainty = [
        "Side allocation BB/SB unknown — quantity alone does not assign sides",
        "Install/replacement not confirmed by invoice alone",
        "Lasting outcome of any impeller change remains unknown",
    ]
    ans = Answer(
        query=query,
        conclusion=conclusion,
        basis=basis,
        uncertainty_conflict=uncertainty,
        sources=_source_refs(snapshot, selected),
        epistemic_status=status,
        policy_results=policies,
        selected_ids=selected,
        snapshot_id=snapshot.snapshot_id,
    )
    ans.audit = _audit(query, selected, policies, status, snapshot.snapshot_id)
    return ans


def _compose_ac02(
    query: str,
    index: SnapshotIndex,
    snapshot: FixtureSnapshot,
    policies: list[PolicyResult],
) -> Answer:
    policies.append(guard_bb_sb_integrity(quantityWithoutSideEvidence=2))
    status = EpistemicStatus.UNKNOWN.value
    for p in policies:
        status = _apply_policy_status(status, p)

    selected = [
        "EVT-FAKTURA-9631-IMPELLER",
        "CLM-IMPELLER-SIDE-UNKNOWN",
        "AI-D4-IMPELLER-KIT",
        "SRC-FAKTURA-9631",
    ]
    # Ensure retrieval can find impeller context
    hits = index.search(query, keywords=["impeller", "begge", "both", "side"], limit=10)
    for h in hits:
        if h.entity_id not in selected:
            selected.append(h.entity_id)

    conclusion = (
        "Cannot conclude that both motors' impellers were changed. "
        "Faktura 9631 shows quantity ×2 without BB/SB side evidence; "
        "side remains unknown."
    )
    basis = [
        f"Invoiced quantity 2 for part {FIXTURE_PART_IMPELLER}",
        "Asset AI-D4-IMPELLER-KIT.side = unknown",
        "Policy BB_SB_INTEGRITY: quantity without side evidence → side unknown",
    ]
    uncertainty = [
        "No documented BB vs SB allocation",
        "Do not infer one kit per side from count alone",
    ]
    ans = Answer(
        query=query,
        conclusion=conclusion,
        basis=basis,
        uncertainty_conflict=uncertainty,
        sources=_source_refs(snapshot, selected),
        epistemic_status=status,
        policy_results=policies,
        selected_ids=selected,
        snapshot_id=snapshot.snapshot_id,
    )
    ans.audit = _audit(query, selected, policies, status, snapshot.snapshot_id)
    return ans


def _compose_ac03(
    query: str,
    index: SnapshotIndex,
    snapshot: FixtureSnapshot,
    policies: list[PolicyResult],
) -> Answer:
    claim = next((c for c in snapshot.claims if c.id == "CLM-PCU-CLEAN-2025"), None)
    event = next((e for e in snapshot.events if e.id == "EVT-FAKTURA-9273-PCU"), None)
    selected = ["CLM-PCU-CLEAN-2025", "EVT-FAKTURA-9273-PCU", "SRC-FAKTURA-9273", "EVD-FAKTURA-9273"]
    hits = index.search(query, keywords=["pcu", "cleaned", "9273"], limit=10)
    for h in hits:
        if h.entity_id not in selected:
            selected.append(h.entity_id)

    # Forbid promoting to "replaced" without evidence
    q = query.lower()
    if any(w in q for w in ("replaced", "udskiftet", "skiftet")) and claim is not None:
        # Treat asserted replacement as lasting_fix / overclaim → downgrade
        policies.append(guard_action_not_outcome(claim, "lasting_fix"))

    status = EpistemicStatus.DOCUMENTED.value
    for p in policies:
        if p.verdict in {"downgrade", "reject"}:
            status = _apply_policy_status(status, p)

    conclusion = (
        "Documented action on the PCU connector: cleaned (Faktura 9273). "
        "There is no evidence of replacement — do not conclude 'replaced'."
    )
    basis = [
        f"Claim {claim.id if claim else 'CLM-PCU-CLEAN-2025'}: role=action, value=cleaned",
        f"Event {event.id if event else 'EVT-FAKTURA-9273-PCU'}: role=action, time=2025-08-26",
        "Evidence extract: oily PCU contact cleaned",
    ]
    uncertainty = [
        "Replacement not documented",
        "Action ≠ lasting outcome (see AC-04)",
    ]
    ans = Answer(
        query=query,
        conclusion=conclusion,
        basis=basis,
        uncertainty_conflict=uncertainty,
        sources=_source_refs(snapshot, selected),
        epistemic_status=status,
        policy_results=policies,
        selected_ids=selected,
        snapshot_id=snapshot.snapshot_id,
    )
    ans.audit = _audit(query, selected, policies, status, snapshot.snapshot_id)
    return ans


def _compose_ac04(
    query: str,
    index: SnapshotIndex,
    snapshot: FixtureSnapshot,
    policies: list[PolicyResult],
) -> Answer:
    action = next((c for c in snapshot.claims if c.id == "CLM-PCU-CLEAN-2025"), None)
    result = next((c for c in snapshot.claims if c.id == "CLM-EVC-TEST-RUN-2025"), None)
    if action is not None:
        policies.append(guard_action_not_outcome(action, "lasting_fix"))

    status = EpistemicStatus.UNKNOWN.value
    for p in policies:
        status = _apply_policy_status(status, p)

    selected = [
        "CLM-PCU-CLEAN-2025",
        "CLM-EVC-TEST-RUN-2025",
        "EVT-FAKTURA-9273-VALIDATION",
        "SRC-FAKTURA-9273",
    ]
    hits = index.search(query, keywords=["evc", "lasting", "provkørsel", "9273"], limit=10)
    for h in hits:
        if h.entity_id not in selected:
            selected.append(h.entity_id)

    conclusion = (
        "A test run / provkørsel after PCU cleaning is documented. "
        "Lasting resolution of the EVC fault remains unknown — "
        "documented action/test ≠ lasting fix."
    )
    basis = [
        f"Result claim {result.id if result else 'CLM-EVC-TEST-RUN-2025'}: status=unknown",
        "Validation event EVT-FAKTURA-9273-VALIDATION outcome=test_run_documented; lasting_fix_unknown",
        "Policy ACTION_NE_OUTCOME applied",
    ]
    uncertainty = [
        "Lasting outcome unknown after test run",
        "Root cause still unresolved (see AC-05)",
    ]
    ans = Answer(
        query=query,
        conclusion=conclusion,
        basis=basis,
        uncertainty_conflict=uncertainty,
        sources=_source_refs(snapshot, selected),
        epistemic_status=status,
        policy_results=policies,
        selected_ids=selected,
        snapshot_id=snapshot.snapshot_id,
    )
    ans.audit = _audit(query, selected, policies, status, snapshot.snapshot_id)
    return ans


def _compose_ac05(
    query: str,
    index: SnapshotIndex,
    snapshot: FixtureSnapshot,
    policies: list[PolicyResult],
) -> Answer:
    hyp = next((c for c in snapshot.claims if c.id == "CLM-PCU-OIL-HYP"), None)
    if hyp is not None:
        policies.append(guard_hypothesis_not_root_cause(hyp))

    status = EpistemicStatus.INFERRED.value
    for p in policies:
        status = _apply_policy_status(status, p)

    selected = [
        "CLM-PCU-OIL-HYP",
        "OBS-BB-NO-START-2025",
        "EVD-FAKTURA-9273",
        "SRC-FAKTURA-9273",
    ]
    hits = index.search(query, keywords=["årsag", "cause", "oily", "pcu", "bb"], limit=10)
    for h in hits:
        if h.entity_id not in selected:
            selected.append(h.entity_id)

    conclusion = (
        "Oily / oiled PCU contact is a possible cause of BB no-start only — "
        "not a confirmed root cause."
    )
    basis = [
        f"Hypothesis claim {hyp.id if hyp else 'CLM-PCU-OIL-HYP'}: role=hypothesis",
        "Observation OBS-BB-NO-START-2025 recorded on BB",
        "Policy HYPOTHESIS_NE_ROOT_CAUSE — treat as possible only",
    ]
    uncertainty = [
        "Root cause not confirmed",
        "For/against evidence incomplete beyond oily contact note",
    ]
    ans = Answer(
        query=query,
        conclusion=conclusion,
        basis=basis,
        uncertainty_conflict=uncertainty,
        sources=_source_refs(snapshot, selected),
        epistemic_status=status,
        policy_results=policies,
        selected_ids=selected,
        snapshot_id=snapshot.snapshot_id,
    )
    ans.audit = _audit(query, selected, policies, status, snapshot.snapshot_id)
    return ans


def _compose_ac06(
    query: str,
    index: SnapshotIndex,
    snapshot: FixtureSnapshot,
    policies: list[PolicyResult],
    part: str | None = None,
) -> Answer:
    pn = part or FIXTURE_PART_ABSENT
    found = index.has_part_number(pn)
    # Detect attempted topic switch to impeller
    q = query.lower()
    substituted = None
    if "impeller" in q or "3588475" in q:
        substituted = "impeller"
    policies.append(guard_bounded_absence(pn, found, substituted))
    if substituted:
        # Also explicit no-topic-switch
        policies.append(guard_no_topic_switch(pn, substituted))

    rejected = any(p.verdict == "reject" for p in policies)
    status = EpistemicStatus.BOUNDED_ABSENCE.value
    for p in policies:
        if p.epistemic_status is not None:
            status = _apply_policy_status(status, p)

    selected = ["KO-D4-0036"]  # belt KO exists but not under this P/N
    # Do NOT add impeller records to selected — that would be topic switch
    if rejected:
        conclusion = (
            f"Refusing topic switch: query targets exact P/N {pn}; "
            "will not answer with impeller history."
        )
        uncertainty = ["Topic switch rejected — bounded absence preserved"]
    else:
        conclusion = (
            f"Bounded absence: no record for exact P/N {pn} in the frozen AC snapshot. "
            "No catalog substitute and no switch to impeller (or other) topics."
        )
        uncertainty = [
            f"Scoped search found no Evidence/Event/Claim for {pn}",
            "KO-D4-0036 lists other EPC candidates — not this P/N",
        ]

    basis = [
        f"Exact P/N lookup for {pn}",
        f"part_numbers in snapshot: {sorted(snapshot.part_numbers)}",
        "Policy BOUNDED_ABSENCE / NO_TOPIC_SWITCH",
    ]
    ans = Answer(
        query=query,
        conclusion=conclusion,
        basis=basis,
        uncertainty_conflict=uncertainty,
        sources=[],  # no source for absent P/N
        epistemic_status=status,
        policy_results=policies,
        selected_ids=selected,
        snapshot_id=snapshot.snapshot_id,
        rejected=rejected,
    )
    ans.audit = _audit(query, selected, policies, status, snapshot.snapshot_id)
    return ans


def _compose_cf001(
    query: str,
    index: SnapshotIndex,
    snapshot: FixtureSnapshot,
    policies: list[PolicyResult],
) -> Answer:
    policies.append(guard_conflict_must_surface(list(snapshot.conflict_statements)))
    status = EpistemicStatus.CONFLICTED.value
    for p in policies:
        status = _apply_policy_status(status, p)

    selected = [
        "CLM-MOTOR-TYPE-D4",
        "CLM-MOTOR-TYPE-D6",
        "EVD-D4-LABOUR",
        "EVD-D6-LABOUR",
        "SRC-FAKTURA-9631",
        "SRC-DOC-D4-LABOUR",
        "SRC-DOC-D6-LABOUR",
    ]
    hits = index.search(query, keywords=["d4", "d6", "labour", "9631", "motor"], limit=15)
    for h in hits:
        if h.entity_id not in selected:
            selected.append(h.entity_id)

    conclusion = (
        "Conflict must surface: Faktura 9631 labour wording disagrees on motor type "
        "(D4 vs D6). Neither wording is silently preferred."
    )
    basis = [
        "DOC-D4-LABOUR: Labour described as D4 impeller service",
        "DOC-D6-LABOUR: Labour described as D6 related work",
        "Claims CLM-MOTOR-TYPE-D4 and CLM-MOTOR-TYPE-D6 both status=conflicted",
        "Policy CONFLICT_MUST_SURFACE",
    ]
    uncertainty = [
        "D4 vs D6 conflicted wording on 9631 labour (CF-001 / AC-17 related)",
        "Vessel identity elsewhere is consistently D4-300 — conflict still visible here",
    ]
    ans = Answer(
        query=query,
        conclusion=conclusion,
        basis=basis,
        uncertainty_conflict=uncertainty,
        sources=_source_refs(snapshot, selected),
        epistemic_status=status,
        policy_results=policies,
        selected_ids=selected,
        snapshot_id=snapshot.snapshot_id,
    )
    ans.audit = _audit(query, selected, policies, status, snapshot.snapshot_id)
    return ans
