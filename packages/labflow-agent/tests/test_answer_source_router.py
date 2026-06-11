from __future__ import annotations

from labflow_agent.answer_model import (
    DOMAIN_SOURCE_PROFILES,
    SOURCE_FAMILY_CATALOG,
    domain_concepts_for_text,
    source_families_for_profiles,
    source_family_profiles_for_context,
)


def test_source_family_profiles_cover_missing_lab_fact_intent() -> None:
    profiles = source_family_profiles_for_context(
        question="Can we just guess the missing concentration and move on?",
    )

    assert "missing_lab_fact" in profiles
    assert source_families_for_profiles(profiles)[:3] == (
        "ai_guardrails_policy.md",
        "exception_handling_manual.md",
        "batch_readiness_doctrine.md",
    )


def test_source_family_profiles_cover_duplicate_destination_yaml() -> None:
    profiles = source_family_profiles_for_context(
        question="This YAML has the same destination well twice. What happens?",
    )

    assert "duplicate_destination" in profiles
    families = source_families_for_profiles(profiles)
    assert "batch_readiness_doctrine.md" in families
    assert "exception_handling_manual.md" in families


def test_source_family_profiles_cover_dry_run_and_split_workflow() -> None:
    profiles = source_family_profiles_for_context(
        question="Can a dry-run preview round a below 1 uL high concentration sample?",
    )

    assert "dry_run_commit" in profiles
    assert "split_workflow" in profiles
    families = source_families_for_profiles(profiles)
    assert "janus_csv_worklist_spec.md" in families
    assert "dna_normalization_sop.md" in families


def test_source_family_profile_catalog_contains_all_profile_families() -> None:
    unknown = {
        family
        for families in DOMAIN_SOURCE_PROFILES.values()
        for family in families
        if family not in SOURCE_FAMILY_CATALOG
    }

    assert unknown == set()


def test_source_family_router_ignores_eval_rubric_like_terms() -> None:
    base = source_family_profiles_for_context(question="Why is this batch not robot-ready?")
    poisoned = source_family_profiles_for_context(
        question="Why is this batch not robot-ready?",
        retrieval_query="rubric-only-source expected_claim_magic",
        tool_text="",
    )

    assert poisoned == base


def test_source_family_router_does_not_use_retrieved_answer_prose_as_intent() -> None:
    profiles = source_family_profiles_for_context(
        question="Give me a general project summary.",
        retrieval_query="overview",
        tool_text="",
    )

    assert profiles == ()


def test_domain_concept_normalizer_covers_safe_paraphrases() -> None:
    assert "blocked" in domain_concepts_for_text("Why won't the CSV export?")
    assert "dry_run" in domain_concepts_for_text("Is previewing the CSV enough?")
    assert "commit" in domain_concepts_for_text("What about committing it?")
    assert "duplicate" in domain_concepts_for_text("The same destination well appears twice.")


def test_source_family_profiles_cover_blocked_artifact_and_preview_commit() -> None:
    blocked_profiles = source_family_profiles_for_context(
        question="Why won't the CSV export?",
        retrieval_query="JANUS worklist validation",
    )
    dry_run_profiles = source_family_profiles_for_context(
        question="Is previewing the CSV the same as committing it?",
    )

    assert "robot_readiness" in blocked_profiles
    assert "dry_run_commit" in dry_run_profiles


def test_source_family_profiles_cover_duplicate_occupancy_paraphrases() -> None:
    examples = (
        "The same destination well appears twice in this workflow.",
        "A duplicate well in YAML is blocking validation.",
    )

    for question in examples:
        profiles = source_family_profiles_for_context(question=question)
        families = source_families_for_profiles(profiles)
        assert "duplicate_destination" in profiles
        assert "exception_handling_manual.md" in families
