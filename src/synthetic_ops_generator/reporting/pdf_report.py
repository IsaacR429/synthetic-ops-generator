from __future__ import annotations

import json
from dataclasses import asdict, fields
from datetime import datetime
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from synthetic_ops_generator.reporting.run_report import (
    RunReportData,
)

PAGE_SIZE = landscape(A4)

LEFT_MARGIN = 12 * mm
RIGHT_MARGIN = 12 * mm
TOP_MARGIN = 12 * mm
BOTTOM_MARGIN = 14 * mm

CONTENT_WIDTH = (
    PAGE_SIZE[0]
    - LEFT_MARGIN
    - RIGHT_MARGIN
)


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def _format_value(value: object) -> str:
    if value is None:
        return "-"

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(
        value,
        (dict, list, tuple),
    ):
        return json.dumps(
            value,
            indent=2,
            sort_keys=True,
            default=_json_default,
        )

    return str(value)


def _paragraph_text(value: object) -> str:
    return (
        escape(_format_value(value))
        .replace("\n", "<br/>")
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "StreamOpsTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=23,
            spaceAfter=10,
            alignment=TA_LEFT,
        ),
        "heading": ParagraphStyle(
            "StreamOpsHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "subheading": ParagraphStyle(
            "StreamOpsSubHeading",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            spaceBefore=6,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "StreamOpsBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "StreamOpsSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=6.5,
            leading=8.5,
            wordWrap="CJK",
        ),
        "key": ParagraphStyle(
            "StreamOpsKey",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            wordWrap="CJK",
        ),
    }


def _table(
    values: list[tuple[str, object]],
    *,
    styles: dict[str, ParagraphStyle],
) -> Table:
    rows = [
        [
            Paragraph(
                escape(key),
                styles["key"],
            ),
            Paragraph(
                _paragraph_text(value),
                styles["body"],
            ),
        ]
        for key, value in values
    ]

    table = Table(
        rows,
        colWidths=[
            47 * mm,
            CONTENT_WIDTH - (47 * mm),
        ],
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor("#D1D5DB"),
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#F3F4F6"),
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    3,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    3,
                ),
            ]
        )
    )

    return table


def _field_blocks(
    values: list[tuple[str, object]],
    *,
    styles: dict[str, ParagraphStyle],
) -> list[object]:
    story: list[object] = []

    for key, value in values:
        story.append(
            Paragraph(
                (
                    f"<b>{escape(key)}</b><br/>"
                    f"{_paragraph_text(value)}"
                ),
                styles["small"],
            )
        )
        story.append(
            Spacer(1, 2 * mm)
        )

    return story


def _dataclass_items(
    value: Any,
) -> list[tuple[str, object]]:
    projected = asdict(value)

    return list(projected.items())


def _event_timeline_table(
    report: RunReportData,
    *,
    styles: dict[str, ParagraphStyle],
) -> Table:
    headers = (
        "#",
        "Time",
        "Event ID",
        "Event Type",
        "Source",
        "Target",
        "State",
        "Behaviour",
    )

    rows: list[list[Paragraph]] = [
        [
            Paragraph(
                f"<b>{escape(header)}</b>",
                styles["small"],
            )
            for header in headers
        ]
    ]

    for row in report.evidence_rows:
        source = (
            _format_value(row.source_domain)
            + "\n"
            + _format_value(row.source_system)
        )

        target_parts = [
            value
            for value in (
                row.service,
                row.component,
                row.site_id,
                row.service_instance_id,
            )
            if value is not None
        ]

        target = (
            "\n".join(target_parts)
            if target_parts
            else "-"
        )

        event_time = row.event_time.strftime(
            "%Y-%m-%d\n%H:%M:%S"
        )

        values = (
            row.sequence_number,
            event_time,
            row.event_id,
            row.event_type,
            source,
            target,
            row.scenario_state,
            row.behaviour_id,
        )

        rows.append(
            [
                Paragraph(
                    _paragraph_text(value),
                    styles["small"],
                )
                for value in values
            ]
        )

    table = Table(
        rows,
        repeatRows=1,
        colWidths=[
            8 * mm,
            30 * mm,
            24 * mm,
            40 * mm,
            42 * mm,
            40 * mm,
            24 * mm,
            65 * mm,
        ],
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor("#D1D5DB"),
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#E5E7EB"),
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
            ]
        )
    )

    return table


def render_run_report_pdf(
    report: RunReportData,
) -> bytes:
    """
    Render factual StreamOps run evidence as a PDF artifact.

    This renderer does not calculate operational truth and does not
    consume the Scenario Expected Result / Test Oracle.
    """

    styles = _styles()
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=(
            f"StreamOps Run Report - "
            f"{report.execution.run_id}"
        ),
        author="StreamOps",
        subject="Synthetic operational evidence report",
    )

    story: list[object] = []

    story.append(
        Paragraph(
            "StreamOps Run Evidence Report",
            styles["title"],
        )
    )

    story.append(
        Paragraph(
            (
                "Factual synthetic evidence and generation "
                "context for validation, testing, and inspection. "
                "This report does not contain Test Oracle "
                "decisions or Northframe intelligence."
            ),
            styles["body"],
        )
    )

    story.append(
        Spacer(1, 4 * mm)
    )

    story.append(
        Paragraph(
            "Report Context",
            styles["heading"],
        )
    )

    story.append(
        _table(
            [
                (
                    "generated_at",
                    report.generated_at,
                ),
                (
                    "context_resolution",
                    report.context_resolution,
                ),
            ],
            styles=styles,
        )
    )

    story.append(
        Paragraph(
            "Report Scope",
            styles["heading"],
        )
    )

    story.append(
        _table(
            _dataclass_items(
                report.scope
            ),
            styles=styles,
        )
    )

    story.append(
        Paragraph(
            "Run Execution",
            styles["heading"],
        )
    )

    story.append(
        _table(
            _dataclass_items(
                report.execution
            ),
            styles=styles,
        )
    )

    story.append(
        Paragraph(
            "Scenario Definition",
            styles["heading"],
        )
    )

    scenario = report.scenario

    story.append(
        _table(
            [
                (
                    "scenario_id",
                    scenario.scenario_id,
                ),
                (
                    "name",
                    scenario.name,
                ),
                (
                    "description",
                    scenario.description,
                ),
                (
                    "family",
                    scenario.family,
                ),
                (
                    "industry",
                    scenario.industry,
                ),
                (
                    "risk",
                    scenario.risk,
                ),
                (
                    "change_required",
                    scenario.change_required,
                ),
                (
                    "initial_conditions",
                    scenario.initial_conditions,
                ),
                (
                    "state_sequence",
                    scenario.state_sequence,
                ),
                (
                    "assumptions",
                    scenario.assumptions,
                ),
                (
                    "tags",
                    scenario.tags,
                ),
            ],
            styles=styles,
        )
    )

    story.append(
        Paragraph(
            "Trigger",
            styles["subheading"],
        )
    )

    story.append(
        _table(
            _dataclass_items(
                scenario.trigger
            ),
            styles=styles,
        )
    )

    story.append(
        Paragraph(
            "Scenario Frequency Override",
            styles["subheading"],
        )
    )

    if scenario.frequency is None:
        story.append(
            Paragraph(
                "No scenario-specific frequency override.",
                styles["body"],
            )
        )
    else:
        story.append(
            _table(
                _dataclass_items(
                    scenario.frequency
                ),
                styles=styles,
            )
        )

    story.append(
        Paragraph(
            "Generation Behaviours",
            styles["subheading"],
        )
    )

    for index, behaviour in enumerate(
        scenario.behaviours,
        start=1,
    ):
        story.append(
            Paragraph(
                (
                    f"Behaviour {index}: "
                    f"{escape(behaviour.behaviour_id)}"
                ),
                styles["subheading"],
            )
        )

        story.append(
            _table(
                _dataclass_items(
                    behaviour
                ),
                styles=styles,
            )
        )

        story.append(
            Spacer(1, 2 * mm)
        )

    story.append(
        Paragraph(
            "Resolved Run Target",
            styles["heading"],
        )
    )

    story.append(
        _table(
            _dataclass_items(
                report.target
            ),
            styles=styles,
        )
    )

    story.append(
        PageBreak()
    )

    story.append(
        Paragraph(
            "Event Timeline",
            styles["heading"],
        )
    )

    story.append(
        Paragraph(
            (
                "Compact chronological view of every event "
                "included in this report snapshot. Detailed "
                "canonical fields and complete raw payloads for "
                "the same bounded evidence window remain "
                "available in the Evidence Appendix."
            ),
            styles["body"],
        )
    )

    story.append(
        Spacer(1, 3 * mm)
    )

    story.append(
        _event_timeline_table(
            report,
            styles=styles,
        )
    )

    story.append(
        PageBreak()
    )

    story.append(
        Paragraph(
            "Metric Evaluation Explanations",
            styles["heading"],
        )
    )

    if not report.metric_evaluation_explanations:
        story.append(
            Paragraph(
                "No metric evaluation explanations were recorded.",
                styles["body"],
            )
        )

    for explanation in (
        report.metric_evaluation_explanations
    ):
        story.append(
            Paragraph(
                (
                    "Metric Evidence - "
                    f"{escape(explanation.event_id)}"
                ),
                styles["subheading"],
            )
        )

        story.extend(
            _field_blocks(
                list(
                    asdict(
                        explanation
                    ).items()
                ),
                styles=styles,
            )
        )

    story.append(
        PageBreak()
    )

    story.append(
        Paragraph(
            "Canonical Evidence Appendix",
            styles["heading"],
        )
    )

    story.append(
        Paragraph(
            (
                "Every event included in this report snapshot is "
                "represented below using the canonical "
                "RunEvidenceRow field names used by the CSV export. "
                "raw_event contains the complete generated event "
                "envelope and data payload for each included event."
            ),
            styles["body"],
        )
    )

    story.append(
        Spacer(1, 3 * mm)
    )

    for row in report.evidence_rows:
        story.append(
            Paragraph(
                (
                    f"Event {row.sequence_number} - "
                    f"{escape(row.event_id)} - "
                    f"{escape(row.event_type)}"
                ),
                styles["subheading"],
            )
        )

        row_items = [
            (
                field.name,
                getattr(
                    row,
                    field.name,
                ),
            )
            for field in fields(row)
        ]

        story.extend(
            _field_blocks(
                row_items,
                styles=styles,
            )
        )

    def draw_footer(
        canvas,
        doc,
    ) -> None:
        canvas.saveState()
        canvas.setFont(
            "Helvetica",
            7,
        )
        canvas.drawString(
            LEFT_MARGIN,
            6 * mm,
            (
                "StreamOps Run Report - "
                f"{report.execution.run_id}"
            ),
        )
        canvas.drawRightString(
            PAGE_SIZE[0] - RIGHT_MARGIN,
            6 * mm,
            f"Page {doc.page}",
        )
        canvas.restoreState()

    document.build(
        story,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer,
    )

    return buffer.getvalue()
