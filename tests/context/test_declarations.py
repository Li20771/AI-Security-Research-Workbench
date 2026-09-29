"""Structural declared-state extraction.

Contract §7.3. The extraction path is the only place text becomes a claim, so
it is the only place a `PASS` can be manufactured out of a sentence. These
tests pin the grammar's edges, and the most important one is the line that a
looser grammar would have mis-read.
"""

from __future__ import annotations

import pytest

from plugins.context.declarations import (
    SUBJECT_ALIASES,
    extract_declarations,
    fenced_text_lines,
    normalise_key,
    subject_for_declaration,
)


pytestmark = pytest.mark.layer1


def fenced(*lines: str, info: str = "text") -> str:
    return "\n".join([f"```{info}", *lines, "```"])


class TestTheGrammarCannotManufactureAPass:
    """The finding that fixed the key character class (§7.3)."""

    def test_an_inequality_is_not_a_declaration(self):
        """`NOT_RUN != PASS` asserts the opposite of a declaration.

        A looser key class reads this as key `NOT_RUN !`, value `PASS`.
        `docs/AI-02_CLOSEOUT_2026-09-29.md` contains this exact line.
        """
        assert extract_declarations(fenced("NOT_RUN != PASS")) == ()

    def test_no_pass_is_extracted_from_the_inequality_in_any_spacing(self):
        for line in (
            "NOT_RUN != PASS",
            "NOT_RUN!=PASS",
            "NOT_RUN  !=  PASS",
            "  NOT_RUN != PASS  ",
        ):
            assert extract_declarations(fenced(line)) == (), line

    def test_equality_is_still_extracted(self):
        """The guard must not be so tight that real declarations stop matching."""
        found = extract_declarations(fenced("Live provider execution = NOT_RUN"))
        assert [d.declared_state for d in found] == ["NOT_RUN"]

    @pytest.mark.parametrize(
        "line",
        [
            "A < B = PASS",
            "A > B = PASS",
            "A * B = PASS",
            "`code` = PASS",
            '"quoted" = PASS',
            "'quoted' = PASS",
            "a = b = PASS",
        ],
    )
    def test_characters_outside_the_key_class_cannot_form_a_key(self, line):
        assert extract_declarations(fenced(line)) == ()


class TestFenceScanning:
    def test_only_text_fences_are_scanned(self):
        document = "\n".join(
            [
                fenced("A = PASS", info="yaml"),
                fenced("B = PASS", info="python"),
                fenced("C = PASS"),
                fenced("D = PASS", info="text"),
            ]
        )
        found = {d.key for d in extract_declarations(document)}
        assert found == {"C", "D"}

    def test_prose_outside_a_fence_is_ignored(self):
        document = "Live provider execution = NOT_RUN\n\nno fence anywhere\n"
        assert extract_declarations(document) == ()

    def test_a_bare_fence_is_not_scanned(self):
        """§7.3 rule 1 says `text`, and only `text`.

        A bare ``` block is still a code block, and the repository's README and
        ADRs are full of them. Scanning them would trade a tiny gain in
        coverage for a large gain in false positives.
        """
        document = "```\nA = BLOCKED\n```\n"
        assert extract_declarations(document) == ()

    def test_an_unclosed_fence_runs_to_the_end(self):
        """A truncated document yields more lines, never silently fewer."""
        document = "```text\nA = PASS\nB = FAIL\n"
        assert len(extract_declarations(document)) == 2

    def test_fenced_text_lines_excludes_everything_else(self):
        document = "before\n```text\ninside\n```\nafter\n"
        assert fenced_text_lines(document) == ["inside"]


class TestValueGrammar:
    def test_a_truth_state_is_extracted_verbatim(self):
        found = extract_declarations(fenced("Live provider execution = NOT_RUN"))
        assert found[0].declared_state == "NOT_RUN"

    def test_a_lifecycle_word_is_extracted_verbatim(self):
        """Extraction keeps it; classification is what refuses to promote it."""
        found = extract_declarations(fenced("AI-02 overall = COMPLETE"))
        assert found[0].declared_state == "COMPLETE"

    def test_a_compound_value_is_kept_whole(self):
        found = extract_declarations(fenced("Clean-room reinstall = BLOCKED / DEFERRED"))
        assert found[0].declared_state == "BLOCKED / DEFERRED"

    def test_a_multi_word_value_is_kept_whole(self):
        found = extract_declarations(fenced("AI-03 = NOT STARTED"))
        assert found[0].declared_state == "NOT STARTED"

    @pytest.mark.parametrize(
        "line",
        [
            "Real provider API calls = 0",
            "Commit = 8c5df3e",
            "Count = 42",
            "Flag = true",
            "Name = lowercase",
            "Mixed = Complete",
        ],
    )
    def test_a_non_uppercase_value_is_not_a_declaration(self, line):
        """The grammar admits state-shaped tokens, not arbitrary values."""
        assert extract_declarations(fenced(line)) == ()

    def test_trailing_prose_after_the_value_is_not_a_declaration(self):
        """A `key = VALUE  and then some words` line is prose, not a record."""
        line = "AI-02-A = COMPLETE   contract / execution plan / freeze"
        assert extract_declarations(fenced(line)) == ()

    def test_a_markdown_table_row_is_not_a_declaration(self):
        document = "\n".join(
            [
                "| # | Criterion | Status |",
                "| --- | --- | --- |",
                "| 7 | Live verification executed | **NOT_RUN** |",
            ]
        )
        assert extract_declarations(document) == ()


class TestSubjects:
    def test_normalisation_collapses_punctuation_and_case(self):
        assert normalise_key("Live provider execution") == "live_provider_execution"
        assert normalise_key("live-provider-execution") == "live_provider_execution"
        assert normalise_key("Live_Provider  Execution") == "live_provider_execution"

    def test_two_spellings_share_one_subject(self):
        """D-4: a conflict nobody can detect is a conflict nobody can resolve."""
        first = subject_for_declaration("Live provider execution")
        second = subject_for_declaration("live-provider-execution")
        assert first == second == "declared.live_provider_execution"

    def test_an_unmapped_key_is_namespaced_under_declared(self):
        assert subject_for_declaration("Offline CI") == "declared.offline_ci"

    @pytest.mark.parametrize("key", ["head", "HEAD", "Head", "head "])
    def test_the_alias_table_maps_head_onto_git(self, key):
        assert subject_for_declaration(key) == "git.head"

    def test_the_alias_table_is_exactly_three_entries(self):
        """D-5: the three subjects on which a document can contradict git."""
        assert set(SUBJECT_ALIASES) == {"head", "branch", "working_tree"}
        assert SUBJECT_ALIASES == {
            "head": "git.head",
            "branch": "git.branch",
            "working_tree": "git.working_tree",
        }

    def test_the_alias_table_is_not_a_substring_match(self):
        """`header` is not `head`: the alias applies to the whole key only."""
        assert subject_for_declaration("header") == "declared.header"

    def test_an_empty_key_is_rejected(self):
        from plugins.context.errors import DeclarationError

        with pytest.raises(DeclarationError):
            subject_for_declaration("---")


class TestDeduplication:
    def test_an_exact_duplicate_is_collapsed(self):
        document = fenced("A = PASS", "A = PASS")
        assert len(extract_declarations(document)) == 1

    def test_a_self_contradiction_is_kept(self):
        """Two values for one subject is a real disagreement, not a duplicate."""
        document = fenced("A = PASS", "A = FAIL")
        found = extract_declarations(document)
        assert [d.declared_state for d in found] == ["PASS", "FAIL"]

    def test_document_order_is_preserved(self):
        document = fenced("A = PASS", "B = FAIL", "C = BLOCKED")
        assert [d.key for d in extract_declarations(document)] == ["A", "B", "C"]

    def test_extraction_is_deterministic(self):
        document = fenced("A = PASS", "B = FAIL", "A = FAIL")
        assert extract_declarations(document) == extract_declarations(document)
