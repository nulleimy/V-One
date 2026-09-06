from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_script(relative: str, module_name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PUBLISHER = _load_script("scripts/publish_review_branch.py", "pr01_publish_review_branch")
GOVERNANCE = _load_script(
    "scripts/verify_github_main_governance.py",
    "pr01_verify_github_main_governance",
)

CANONICAL_REPOSITORY = "eimyroot/Voodoo-One"
CANONICAL_REPOSITORY_URL = "https://github.com/eimyroot/Voodoo-One.git"
LEGACY_FETCH_ALIASES = frozenset(
    {
        "https://github.com/eimyroot/V-One.git",
        "https://github.com/nulleimy/V-One.git",
    }
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_machine_governance_baseline_uses_canonical_repository_identity() -> None:
    baseline = json.loads(
        _read(".github/governance/main-branch-baseline.v1.json")
    )
    assert baseline["repository"] == CANONICAL_REPOSITORY
    assert baseline["desired"]["required_status_checks"] == ["verify"]
    assert baseline["desired"]["workflow"] == "ci"
    assert baseline["desired"]["workflow_path"] == ".github/workflows/ci.yml"


def test_g0_actions_run_identity_rejects_pre_rename_repository_paths() -> None:
    current = "https://github.com/eimyroot/Voodoo-One/actions/runs/123456"
    assert (
        GOVERNANCE._actions_run_id(current, "eimyroot", "Voodoo-One")  # noqa: SLF001
        == 123456
    )

    for historical in (
        "https://github.com/eimyroot/V-One/actions/runs/123456",
        "https://github.com/nulleimy/V-One/actions/runs/123456",
    ):
        with pytest.raises(
            GOVERNANCE.GitHubEvidenceError,
            match="does not identify an Actions run",
        ):
            GOVERNANCE._actions_run_id(  # noqa: SLF001
                historical,
                "eimyroot",
                "Voodoo-One",
            )


def test_review_publisher_has_one_current_target_and_fetch_only_legacy_aliases() -> None:
    assert PUBLISHER.ALLOWED_GITHUB_REPOSITORY == CANONICAL_REPOSITORY_URL
    assert PUBLISHER.LEGACY_GITHUB_REPOSITORY_ALIASES == LEGACY_FETCH_ALIASES

    policy = PUBLISHER.PublicationPolicy()
    policy.validate_repository_url(CANONICAL_REPOSITORY_URL)
    policy.validate_origin_fetch_url(CANONICAL_REPOSITORY_URL, CANONICAL_REPOSITORY_URL)

    for legacy in sorted(LEGACY_FETCH_ALIASES):
        policy.validate_origin_fetch_url(legacy, CANONICAL_REPOSITORY_URL)
        with pytest.raises(PUBLISHER.PublicationError, match="not allowlisted"):
            policy.validate_repository_url(legacy)

    with pytest.raises(PUBLISHER.PublicationError, match="origin fetch URL"):
        policy.validate_origin_fetch_url(
            "https://github.com/example/not-voodoo-one.git",
            CANONICAL_REPOSITORY_URL,
        )


def test_governance_and_publication_docs_bind_current_repository_identity() -> None:
    governance = _read("docs/governance/GITHUB_MAIN_GOVERNANCE_BASELINE_V1.md")
    publication = _read("docs/governance/REVIEW_BRANCH_PUBLICATION.md")

    assert "repository = eimyroot/Voodoo-One" in governance
    assert "repository = nulleimy/V-One" not in governance
    assert "fresh live G0 verification required" in governance

    assert CANONICAL_REPOSITORY_URL in publication
    assert "fetch-only legacy alias" in publication
    assert "never are permitted" not in publication
    assert "nikdy nejsou povoleným publication\ntargetem" in publication


def test_operations_runbook_uses_current_repo_and_artifact_derived_schema_truth() -> None:
    runbook = _read("docs/product/OPERATIONS_RUNBOOK.md")

    assert "--repo eimyroot/Voodoo-One" in runbook
    assert "--repo nulleimy/V-One" not in runbook
    assert "schema_version: 9" not in runbook
    assert "schema version `9`" not in runbook
    assert "highest contiguous migration version bundled" in runbook
    assert "0014_workspace_memberships.sql" in runbook
    assert "current expected schema is 14" in runbook


def test_current_truth_does_not_promote_historical_g0_after_rename() -> None:
    state = _read("CURRENT_PRODUCT_STATE.md")
    capabilities = _read("docs/product/CURRENT_CAPABILITIES.md")
    readme = _read("README.md")

    assert "CANONICAL_REPOSITORY: eimyroot/Voodoo-One" in state
    assert "G0_GITHUB_GOVERNANCE=UNKNOWN" in state
    assert "G0                              = UNKNOWN" in state
    assert "historical_verdict = VERIFIED" in state

    assert "| Canonical repository | `eimyroot/Voodoo-One` |" in capabilities
    assert "| Main GitHub governance policy | UNKNOWN |" in capabilities
    assert "G0_LIVE_ENFORCEMENT_VERIFIED=UNKNOWN_CURRENT" in capabilities
    assert "historical_verdict = VERIFIED" in capabilities

    assert (
        "| GitHub main governance enforcement | UNKNOWN / fresh post-rename G0 required; "
        "historical VERIFIED evidence retained |"
    ) in readme
    assert "current G0 governance is therefore `UNKNOWN`" in readme
    assert "historical G0 VERIFIED evidence is retained" in readme
