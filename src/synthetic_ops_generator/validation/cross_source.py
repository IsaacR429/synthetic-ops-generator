from collections import Counter
from collections.abc import Sequence

from synthetic_ops_generator.domain.enterprise import Enterprise
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.validation.models import (
    CrossSourceValidationReport,
)


class CrossSourceValidator:
    """
    Validates consistency across generated events belonging
    to the same Scenario Run.

    This validator checks generated-data integrity only.
    It does not calculate platform Decisions, Actions or RCA.
    """

    def validate(
        self,
        *,
        events: Sequence[GeneratedEvent],
        context: ScenarioContext,
        enterprise: Enterprise | None = None,
    ) -> CrossSourceValidationReport:
        report = CrossSourceValidationReport()

        self._validate_unique_event_ids(
            events=events,
            report=report,
        )

        self._validate_unique_sequence_numbers(
            events=events,
            report=report,
        )

        self._validate_context_correlation(
            events=events,
            context=context,
            report=report,
        )

        self._validate_chronology(
            events=events,
            report=report,
        )

        if enterprise is not None:
            self._validate_enterprise_references(
                events=events,
                context=context,
                enterprise=enterprise,
                report=report,
            )

        self._validate_deployment_relationships(
            events=events,
            context=context,
            report=report,
        )

        self._validate_incident_relationships(
            events=events,
            context=context,
            report=report,
        )

        self._validate_evidence_references(
            events=events,
            report=report,
        )

        return report

    @staticmethod
    def _validate_unique_event_ids(
        *,
        events: Sequence[GeneratedEvent],
        report: CrossSourceValidationReport,
    ) -> None:
        counts = Counter(
            event.event_id
            for event in events
        )

        for event_id, count in counts.items():
            if count <= 1:
                continue

            report.add_finding(
                requirement_id="REQ-VAL-003",
                rule="unique_event_id",
                message=(
                    f"Event ID {event_id} occurs "
                    f"{count} times."
                ),
                event_ids=[event_id],
            )

    @staticmethod
    def _validate_unique_sequence_numbers(
        *,
        events: Sequence[GeneratedEvent],
        report: CrossSourceValidationReport,
    ) -> None:
        counts = Counter(
            event.sequence_number
            for event in events
        )

        for sequence_number, count in counts.items():
            if count <= 1:
                continue

            affected_event_ids = [
                event.event_id
                for event in events
                if (
                    event.sequence_number
                    == sequence_number
                )
            ]

            report.add_finding(
                requirement_id="REQ-COR-010",
                rule="unique_sequence_number",
                message=(
                    f"Sequence number {sequence_number} "
                    f"occurs {count} times."
                ),
                event_ids=affected_event_ids,
            )

    @staticmethod
    def _validate_context_correlation(
        *,
        events: Sequence[GeneratedEvent],
        context: ScenarioContext,
        report: CrossSourceValidationReport,
    ) -> None:
        for event in events:
            if event.scenario_id != context.scenario_id:
                report.add_finding(
                    requirement_id="REQ-COR-002",
                    rule="scenario_correlation",
                    message=(
                        f"Event {event.event_id} references "
                        f"Scenario {event.scenario_id}; "
                        f"expected {context.scenario_id}."
                    ),
                    event_ids=[event.event_id],
                )

            if event.run_id != context.run_id:
                report.add_finding(
                    requirement_id="REQ-COR-003",
                    rule="run_correlation",
                    message=(
                        f"Event {event.event_id} references "
                        f"Run {event.run_id}; "
                        f"expected {context.run_id}."
                    ),
                    event_ids=[event.event_id],
                )

            if (
                event.chg_id is not None
                and event.chg_id != context.chg_id
            ):
                report.add_finding(
                    requirement_id="REQ-COR-001",
                    rule="change_correlation",
                    message=(
                        f"Event {event.event_id} references "
                        f"Change {event.chg_id}; "
                        f"expected {context.chg_id}."
                    ),
                    event_ids=[event.event_id],
                )

            if (
                event.business_stream is not None
                and event.business_stream
                != context.business_stream
            ):
                report.add_finding(
                    requirement_id="REQ-COR-004",
                    rule="business_stream_correlation",
                    message=(
                        f"Event {event.event_id} references "
                        f"Business Stream "
                        f"{event.business_stream}; expected "
                        f"{context.business_stream}."
                    ),
                    event_ids=[event.event_id],
                )

            if (
                event.service is not None
                and event.service != context.service
            ):
                report.add_finding(
                    requirement_id="REQ-COR-005",
                    rule="service_correlation",
                    message=(
                        f"Event {event.event_id} references "
                        f"Service {event.service}; "
                        f"expected {context.service}."
                    ),
                    event_ids=[event.event_id],
                )

    @staticmethod
    def _validate_chronology(
        *,
        events: Sequence[GeneratedEvent],
        report: CrossSourceValidationReport,
    ) -> None:
        sequence_numbers = [
            event.sequence_number
            for event in events
        ]

        if sequence_numbers != sorted(sequence_numbers):
            report.add_finding(
                requirement_id="REQ-COR-010",
                rule="sequence_chronology",
                message=(
                    "Generated events are not ordered by "
                    "sequence number."
                ),
                event_ids=[
                    event.event_id
                    for event in events
                ],
            )

        event_times = [
            event.event_time
            for event in events
        ]

        if event_times != sorted(event_times):
            report.add_finding(
                requirement_id="REQ-COR-010",
                rule="timestamp_chronology",
                message=(
                    "Generated event timestamps do not "
                    "preserve chronological ordering."
                ),
                event_ids=[
                    event.event_id
                    for event in events
                ],
            )

    @staticmethod
    def _validate_enterprise_references(
        *,
        events: Sequence[GeneratedEvent],
        context: ScenarioContext,
        enterprise: Enterprise,
        report: CrossSourceValidationReport,
    ) -> None:
        business_streams = {
            stream.stream_id: stream
            for stream in enterprise.business_streams
        }

        services = {
            service.service_id: service
            for service in enterprise.services
        }

        components = {
            component.component_id: component
            for component in enterprise.components
        }

        for event in events:
            if (
                event.business_stream is not None
                and event.business_stream not in business_streams
            ):
                report.add_finding(
                    requirement_id="REQ-COR-004",
                    rule="business_stream_reference",
                    message=(
                        f"Event {event.event_id} references "
                        f"unknown Business Stream "
                        f"{event.business_stream}."
                    ),
                    event_ids=[event.event_id],
                )

            service = None

            if event.service is not None:
                service = services.get(event.service)

                if service is None:
                    report.add_finding(
                        requirement_id="REQ-COR-005",
                        rule="service_reference",
                        message=(
                            f"Event {event.event_id} references "
                            f"unknown Service {event.service}."
                        ),
                        event_ids=[event.event_id],
                    )

            if (
                service is not None
                and event.business_stream is not None
                and service.business_stream_id
                != event.business_stream
            ):
                report.add_finding(
                    requirement_id="REQ-COR-005",
                    rule="service_business_stream_relationship",
                    message=(
                        f"Service {service.service_id} does not "
                        f"belong to Business Stream "
                        f"{event.business_stream}."
                    ),
                    event_ids=[event.event_id],
                )

            if event.component is None:
                continue

            component = components.get(event.component)

            if component is None:
                report.add_finding(
                    requirement_id="REQ-COR-006",
                    rule="component_reference",
                    message=(
                        f"Event {event.event_id} references "
                        f"unknown Component {event.component}."
                    ),
                    event_ids=[event.event_id],
                )
                continue

            expected_service = (
                event.service
                if event.service is not None
                else context.service
            )

            if component.service_id != expected_service:
                report.add_finding(
                    requirement_id="REQ-COR-006",
                    rule="component_service_relationship",
                    message=(
                        f"Component {component.component_id} "
                        f"belongs to Service "
                        f"{component.service_id}; expected "
                        f"{expected_service}."
                    ),
                    event_ids=[event.event_id],
                )

            if (
                event.environment is not None
                and component.environment
                != event.environment
            ):
                report.add_finding(
                    requirement_id="REQ-VAL-010",
                    rule="component_environment_relationship",
                    message=(
                        f"Component {component.component_id} "
                        f"uses Environment "
                        f"{component.environment.value}; event "
                        f"uses {event.environment.value}."
                    ),
                    event_ids=[event.event_id],
                )

    @staticmethod
    def _validate_deployment_relationships(
        *,
        events: Sequence[GeneratedEvent],
        context: ScenarioContext,
        report: CrossSourceValidationReport,
    ) -> None:
        deployment_events = [
            event
            for event in events
            if event.event_type.startswith("cicd.deployment.")
        ]

        if not deployment_events:
            return

        deployment_ids: dict[str, list[GeneratedEvent]] = {}

        for event in deployment_events:
            payload = event.data.get("deployment")

            if not isinstance(payload, dict):
                report.add_finding(
                    requirement_id="REQ-COR-007",
                    rule="deployment_payload",
                    message=(
                        f"Deployment Event {event.event_id} "
                        "does not contain a valid Deployment payload."
                    ),
                    event_ids=[event.event_id],
                )
                continue

            deployment_id = payload.get("deployment_id")

            if not isinstance(deployment_id, str):
                report.add_finding(
                    requirement_id="REQ-COR-007",
                    rule="deployment_id",
                    message=(
                        f"Deployment Event {event.event_id} "
                        "does not contain a valid Deployment ID."
                    ),
                    event_ids=[event.event_id],
                )
                continue

            deployment_ids.setdefault(
                deployment_id,
                [],
            ).append(event)

            if (
                context.deployment_id is not None
                and deployment_id != context.deployment_id
            ):
                report.add_finding(
                    requirement_id="REQ-COR-007",
                    rule="deployment_correlation",
                    message=(
                        f"Deployment Event {event.event_id} "
                        f"references Deployment {deployment_id}; "
                        f"expected {context.deployment_id}."
                    ),
                    event_ids=[event.event_id],
                )

        for deployment_id, related_events in deployment_ids.items():
            rollback_events = [
                event
                for event in related_events
                if event.event_type in {
                    "cicd.deployment.rollback_started",
                    "cicd.deployment.rollback_completed",
                }
            ]

            if not rollback_events:
                continue

            completed_events = [
                event
                for event in related_events
                if event.event_type
                == "cicd.deployment.completed"
            ]

            if not completed_events:
                report.add_finding(
                    requirement_id="REQ-COR-007",
                    rule="rollback_deployment_relationship",
                    message=(
                        f"Rollback for Deployment "
                        f"{deployment_id} has no prior "
                        "completed Deployment event."
                    ),
                    event_ids=[
                        event.event_id
                        for event in rollback_events
                    ],
                )
                continue

            earliest_rollback = min(
                event.sequence_number
                for event in rollback_events
            )

            if not any(
                event.sequence_number < earliest_rollback
                for event in completed_events
            ):
                report.add_finding(
                    requirement_id="REQ-COR-007",
                    rule="rollback_deployment_chronology",
                    message=(
                        f"Rollback for Deployment "
                        f"{deployment_id} does not occur "
                        "after its completed Deployment event."
                    ),
                    event_ids=[
                        event.event_id
                        for event in rollback_events
                    ],
                )

    @staticmethod
    def _validate_incident_relationships(
        *,
        events: Sequence[GeneratedEvent],
        context: ScenarioContext,
        report: CrossSourceValidationReport,
    ) -> None:
        incident_events = [
            event
            for event in events
            if event.event_type.startswith("itsm.incident.")
        ]

        if not incident_events:
            return

        incident_ids: dict[str, list[GeneratedEvent]] = {}

        for event in incident_events:
            payload = event.data.get("incident")

            if not isinstance(payload, dict):
                report.add_finding(
                    requirement_id="REQ-COR-008",
                    rule="incident_payload",
                    message=(
                        f"Incident Event {event.event_id} "
                        "does not contain a valid Incident payload."
                    ),
                    event_ids=[event.event_id],
                )
                continue

            incident_id = payload.get("incident_id")

            if not isinstance(incident_id, str):
                report.add_finding(
                    requirement_id="REQ-COR-008",
                    rule="incident_id",
                    message=(
                        f"Incident Event {event.event_id} "
                        "does not contain a valid Incident ID."
                    ),
                    event_ids=[event.event_id],
                )
                continue

            incident_ids.setdefault(
                incident_id,
                [],
            ).append(event)

            if (
                context.incident_id is not None
                and incident_id != context.incident_id
            ):
                report.add_finding(
                    requirement_id="REQ-COR-008",
                    rule="incident_correlation",
                    message=(
                        f"Incident Event {event.event_id} "
                        f"references Incident {incident_id}; "
                        f"expected {context.incident_id}."
                    ),
                    event_ids=[event.event_id],
                )

        for incident_id, related_events in incident_ids.items():
            created_events = [
                event
                for event in related_events
                if event.event_type
                == "itsm.incident.created"
            ]

            resolved_events = [
                event
                for event in related_events
                if event.event_type
                == "itsm.incident.resolved"
            ]

            for resolved_event in resolved_events:
                prior_created = [
                    event
                    for event in created_events
                    if (
                        event.sequence_number
                        < resolved_event.sequence_number
                    )
                ]

                if not prior_created:
                    report.add_finding(
                        requirement_id="REQ-COR-008",
                        rule="incident_resolution_relationship",
                        message=(
                            f"Resolved Incident {incident_id} "
                            "has no prior Incident creation event."
                        ),
                        event_ids=[
                            resolved_event.event_id,
                        ],
                    )
                    continue

                created_payload = prior_created[-1].data[
                    "incident"
                ]
                resolved_payload = resolved_event.data[
                    "incident"
                ]

                for field_name in (
                    "chg_id",
                    "service",
                    "component",
                ):
                    if (
                        resolved_payload.get(field_name)
                        != created_payload.get(field_name)
                    ):
                        report.add_finding(
                            requirement_id="REQ-COR-008",
                            rule=(
                                "incident_lifecycle_consistency"
                            ),
                            message=(
                                f"Incident {incident_id} changed "
                                f"{field_name} between creation "
                                "and resolution."
                            ),
                            event_ids=[
                                prior_created[-1].event_id,
                                resolved_event.event_id,
                            ],
                        )

    @staticmethod
    def _validate_evidence_references(
        *,
        events: Sequence[GeneratedEvent],
        report: CrossSourceValidationReport,
    ) -> None:
        event_by_id = {
            event.event_id: event
            for event in events
        }

        for evidence_event in events:
            if evidence_event.event_type != "evidence.captured":
                continue

            evidence = evidence_event.data.get("evidence")

            if not isinstance(evidence, dict):
                report.add_finding(
                    requirement_id="REQ-VAL-009",
                    rule="evidence_payload",
                    message=(
                        f"Evidence Event "
                        f"{evidence_event.event_id} does not "
                        "contain a valid Evidence payload."
                    ),
                    event_ids=[evidence_event.event_id],
                )
                continue

            source_event_ids = evidence.get(
                "source_event_ids",
                [],
            )

            source_record_ids = evidence.get(
                "source_record_ids",
                [],
            )

            if not source_event_ids and not source_record_ids:
                report.add_finding(
                    requirement_id="REQ-VAL-009",
                    rule="evidence_source_reference",
                    message=(
                        f"Evidence Event "
                        f"{evidence_event.event_id} has no "
                        "source references."
                    ),
                    event_ids=[evidence_event.event_id],
                )

            for source_event_id in source_event_ids:
                source_event = event_by_id.get(
                    source_event_id
                )

                if source_event is None:
                    report.add_finding(
                        requirement_id="REQ-COR-009",
                        rule="evidence_event_reference",
                        message=(
                            f"Evidence Event "
                            f"{evidence_event.event_id} references "
                            f"unknown Event {source_event_id}."
                        ),
                        event_ids=[
                            evidence_event.event_id,
                        ],
                    )
                    continue

                if (
                    source_event.scenario_id
                    != evidence_event.scenario_id
                    or source_event.run_id
                    != evidence_event.run_id
                    or source_event.chg_id
                    != evidence_event.chg_id
                ):
                    report.add_finding(
                        requirement_id="REQ-COR-009",
                        rule="evidence_reference_correlation",
                        message=(
                            f"Evidence Event "
                            f"{evidence_event.event_id} references "
                            f"Event {source_event_id} from a "
                            "different correlation context."
                        ),
                        event_ids=[
                            evidence_event.event_id,
                            source_event.event_id,
                        ],
                    )

                if (
                    source_event.sequence_number
                    >= evidence_event.sequence_number
                ):
                    report.add_finding(
                        requirement_id="REQ-COR-010",
                        rule="evidence_reference_chronology",
                        message=(
                            f"Evidence Event "
                            f"{evidence_event.event_id} references "
                            f"Event {source_event_id} that does "
                            "not occur earlier in the Run."
                        ),
                        event_ids=[
                            evidence_event.event_id,
                            source_event.event_id,
                        ],
                    )