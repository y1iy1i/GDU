from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]


def sequence_issues(
    events: list[dict[str, object]], *, require_freeze: bool
) -> list[str]:
    issues: list[str] = []
    event_ids = [event["event_id"] for event in events]
    if len(event_ids) != len(set(event_ids)):
        issues.append("duplicate_event_id")

    logical_times = [event["logical_time"] for event in events]
    if any(
        current <= previous
        for previous, current in zip(logical_times, logical_times[1:])
    ):
        issues.append("logical_time_not_strictly_increasing")

    freeze_positions = [
        index
        for index, event in enumerate(events)
        if event["event_type"] == "freeze"
    ]
    if len(freeze_positions) > 1:
        issues.append("multiple_freeze_events")
    if require_freeze and len(freeze_positions) != 1:
        issues.append("required_freeze_event_count")
    if freeze_positions and freeze_positions[-1] != len(events) - 1:
        issues.append("freeze_event_not_last")
    return issues


class BuildLogSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads((ROOT / "build_log.schema.json").read_text())
        cls.events = [
            json.loads(line)
            for line in (ROOT / "build_log.example.jsonl").read_text().splitlines()
            if line.strip()
        ]
        cls.validator = jsonschema.Draft202012Validator(
            cls.schema,
            format_checker=jsonschema.FormatChecker(),
        )

    def test_schema_and_all_example_events_are_valid(self) -> None:
        jsonschema.Draft202012Validator.check_schema(self.schema)
        for event in self.events:
            self.validator.validate(event)
        self.assertEqual(
            {event["event_type"] for event in self.events},
            {"revision", "checkpoint", "technical", "freeze"},
        )

    def test_example_sequence_is_valid_for_frozen_log(self) -> None:
        self.assertEqual(sequence_issues(self.events, require_freeze=True), [])

    def test_revision_requires_trigger_evidence(self) -> None:
        event = copy.deepcopy(self.events[2])
        event.pop("trigger_evidence_refs")

        self.assertFalse(self.validator.is_valid(event))

    def test_event_rejects_fields_from_another_event_type(self) -> None:
        event = copy.deepcopy(self.events[1])
        event["before_summary"] = "不属于 technical 事件"

        self.assertFalse(self.validator.is_valid(event))

    def test_freeze_requires_all_stop_gates_to_pass(self) -> None:
        event = copy.deepcopy(self.events[-1])
        event["stop_gate"]["stability"] = "failed"

        self.assertFalse(self.validator.is_valid(event))

    def test_freeze_rejects_unsafe_manifest_path(self) -> None:
        event = copy.deepcopy(self.events[-1])
        event["artifacts_manifest_ref"] = "../ARTIFACTS.sha256"

        self.assertFalse(self.validator.is_valid(event))

        event["artifacts_manifest_ref"] = "..\\ARTIFACTS.sha256"
        self.assertFalse(self.validator.is_valid(event))

    def test_logical_time_must_strictly_increase(self) -> None:
        events = copy.deepcopy(self.events)
        events[2]["logical_time"] = events[1]["logical_time"]

        self.assertIn(
            "logical_time_not_strictly_increasing",
            sequence_issues(events, require_freeze=True),
        )

    def test_event_ids_must_be_unique(self) -> None:
        events = copy.deepcopy(self.events)
        events[2]["event_id"] = events[1]["event_id"]

        self.assertIn(
            "duplicate_event_id",
            sequence_issues(events, require_freeze=True),
        )

    def test_freeze_event_must_be_last(self) -> None:
        events = copy.deepcopy(self.events)
        events[-1], events[-2] = events[-2], events[-1]

        self.assertIn(
            "freeze_event_not_last",
            sequence_issues(events, require_freeze=True),
        )


if __name__ == "__main__":
    unittest.main()
