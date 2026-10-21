from __future__ import annotations

import json
from dataclasses import asdict, fields
from datetime import datetime
from importlib.resources import files
from io import BytesIO
from itertools import pairwise
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import (
    Circle,
    Drawing,
    Line,
    Rect,
    String,
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
)
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

# Neutral operational-report palette. The real StreamOps
# logo remains the primary brand asset; these colours keep
# the evidence document restrained and readable.
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#64748B")
BORDER = colors.HexColor("#DCE3EC")
SURFACE = colors.HexColor("#F8FAFC")
SURFACE_STRONG = colors.HexColor("#EEF2F7")
ACCENT = colors.HexColor("#2563EB")
ACCENT_DARK = colors.HexColor("#1E3A8A")
SUCCESS_BG = colors.HexColor("#DCFCE7")
WARNING_BG = colors.HexColor("#FEF3C7")
DANGER_BG = colors.HexColor("#FEE2E2")
INFO_BG = colors.HexColor("#DBEAFE")

LOGO_HEIGHT = 18 * mm
LOGO_WIDTH = LOGO_HEIGHT * (1100 / 1112)


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
            fontSize=18,
            leading=21,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=1,
        ),
        "brand": ParagraphStyle(
            "StreamOpsBrand",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=9,
            textColor=ACCENT_DARK,
            alignment=TA_LEFT,
        ),
        "subtitle": ParagraphStyle(
            "StreamOpsSubtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=MUTED,
            alignment=TA_LEFT,
        ),
        "heading": ParagraphStyle(
            "StreamOpsHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=ACCENT_DARK,
            spaceBefore=8,
            spaceAfter=5,
        ),
        "subheading": ParagraphStyle(
            "StreamOpsSubHeading",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=INK,
            spaceBefore=5,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "StreamOpsBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.4,
            leading=9.6,
            textColor=INK,
            wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "StreamOpsSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=6.5,
            leading=8,
            textColor=INK,
            wordWrap="CJK",
        ),
        "micro": ParagraphStyle(
            "StreamOpsMicro",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=5.7,
            leading=7,
            textColor=INK,
            wordWrap="CJK",
        ),
        "key": ParagraphStyle(
            "StreamOpsKey",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=6.5,
            leading=8,
            textColor=MUTED,
            wordWrap="CJK",
        ),
        "eyebrow": ParagraphStyle(
            "StreamOpsEyebrow",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=6,
            leading=7,
            textColor=MUTED,
            wordWrap="CJK",
        ),
        "card": ParagraphStyle(
            "StreamOpsCard",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=INK,
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



def _compact_format_value(
    value: object,
) -> str:
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
            sort_keys=True,
            separators=(", ", ": "),
            default=_json_default,
        )

    return str(value)


def _compact_paragraph_text(
    value: object,
) -> str:
    return escape(
        _compact_format_value(value)
    ).replace("\n", "<br/>")


def _has_value(
    value: object,
) -> bool:
    return value not in (
        None,
        "",
        (),
        [],
        {},
    )


def _compact_dataclass_items(
    value: Any,
) -> list[tuple[str, object]]:
    return [
        (key, item)
        for key, item in asdict(value).items()
        if _has_value(item)
    ]


def _paired_table(
    values: list[tuple[str, object]],
    *,
    styles: dict[str, ParagraphStyle],
) -> Table:
    projected = list(values)

    if len(projected) % 2:
        projected.append(("", ""))

    rows: list[list[Paragraph]] = []

    for index in range(
        0,
        len(projected),
        2,
    ):
        left = projected[index]
        right = projected[index + 1]

        rows.append(
            [
                Paragraph(
                    escape(left[0]),
                    styles["key"],
                ),
                Paragraph(
                    _compact_paragraph_text(
                        left[1]
                    ),
                    styles["body"],
                ),
                Paragraph(
                    escape(right[0]),
                    styles["key"],
                ),
                Paragraph(
                    _compact_paragraph_text(
                        right[1]
                    ),
                    styles["body"],
                ),
            ]
        )

    half_width = CONTENT_WIDTH / 2
    key_width = 31 * mm

    table = Table(
        rows,
        colWidths=[
            key_width,
            half_width - key_width,
            key_width,
            half_width - key_width,
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
                    BORDER,
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    SURFACE,
                ),
                (
                    "BACKGROUND",
                    (2, 0),
                    (2, -1),
                    SURFACE,
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


def _logo_image() -> RLImage:
    logo_bytes = (
        files(
            "synthetic_ops_generator.reporting"
        )
        .joinpath(
            "assets",
            "streamops-logo.png",
        )
        .read_bytes()
    )

    return RLImage(
        BytesIO(logo_bytes),
        width=LOGO_WIDTH,
        height=LOGO_HEIGHT,
    )


def _status_background(
    status: str,
):
    normalized = status.lower()

    if normalized == "completed":
        return SUCCESS_BG

    if normalized == "failed":
        return DANGER_BG

    if normalized == "stopped":
        return WARNING_BG

    return INFO_BG


def _brand_header(
    report: RunReportData,
    *,
    styles: dict[str, ParagraphStyle],
) -> Table:
    status = _format_value(
        report.execution.status
    )

    title = Paragraph(
        (
            "<font size='18'><b>Run Evidence Report</b></font><br/>"
            f"<font size='8' color='#64748B'>"
            f"{escape(report.execution.run_id)}"
            "</font>"
        ),
        styles["brand"],
    )

    status_block = Paragraph(
        (
            f"<b>{escape(status.upper())}</b><br/>"
            f"<font size='6.5'>"
            f"{escape(_format_value(report.execution.current_state))}"
            "</font>"
        ),
        styles["small"],
    )

    table = Table(
        [
            [
                _logo_image(),
                title,
                status_block,
            ]
        ],
        colWidths=[
            24 * mm,
            CONTENT_WIDTH - (72 * mm),
            48 * mm,
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
                    "MIDDLE",
                ),
                (
                    "BACKGROUND",
                    (2, 0),
                    (2, 0),
                    _status_background(status),
                ),
                (
                    "BOX",
                    (2, 0),
                    (2, 0),
                    0.5,
                    BORDER,
                ),
                (
                    "ALIGN",
                    (2, 0),
                    (2, 0),
                    "CENTER",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (0, 0),
                    0,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
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
                    5,
                ),
                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, 0),
                    1.2,
                    ACCENT,
                ),
            ]
        )
    )

    return table


def _overview_cards(
    report: RunReportData,
    *,
    styles: dict[str, ParagraphStyle],
) -> Table:
    labels = (
        "SCENARIO",
        "TARGET SERVICE",
        "ENVIRONMENT",
        "RISK",
    )

    values = (
        (
            f"{report.scenario.scenario_id}\n"
            f"{report.scenario.name}"
        ),
        (
            report.target.service_name
            or report.target.service_id
        ),
        report.target.environment,
        report.scenario.risk,
    )

    table = Table(
        [
            [
                Paragraph(
                    label,
                    styles["eyebrow"],
                )
                for label in labels
            ],
            [
                Paragraph(
                    _compact_paragraph_text(
                        value
                    ),
                    styles["card"],
                )
                for value in values
            ],
        ],
        colWidths=[
            CONTENT_WIDTH / 4
        ]
        * 4,
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    SURFACE_STRONG,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    BORDER,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    return table


def _run_kpi_cards(
    report: RunReportData,
    *,
    styles: dict[str, ParagraphStyle],
) -> Table:
    scope = report.scope

    sequence_range = (
        "-"
        if scope.first_sequence_number is None
        else (
            f"{scope.first_sequence_number}"
            f" -> "
            f"{scope.last_sequence_number}"
        )
    )

    complete_value = (
        "YES"
        if scope.complete_run_represented
        else "NO"
    )

    cards = (
        (
            "EVENTS",
            str(report.execution.event_count),
            "generated",
        ),
        (
            "RETAINED",
            str(scope.total_retained_event_count),
            (
                f"{scope.included_event_count} "
                "included"
            ),
        ),
        (
            "REPORT SCOPE",
            scope.selection.upper(),
            (
                f"max "
                f"{scope.maximum_event_count} events"
            ),
        ),
        (
            "SEQUENCE RANGE",
            sequence_range,
            (
                f"complete run: "
                f"{complete_value}"
            ),
        ),
    )

    cells: list[Paragraph] = []

    for label, value, detail in cards:
        cells.append(
            Paragraph(
                (
                    f"<font size='6' color='#64748B'>"
                    f"<b>{escape(label)}</b>"
                    "</font><br/>"
                    f"<font size='14' color='#0F172A'>"
                    f"<b>{escape(value)}</b>"
                    "</font><br/>"
                    f"<font size='6.5' color='#64748B'>"
                    f"{escape(detail)}"
                    "</font>"
                ),
                styles["body"],
            )
        )

    table = Table(
        [cells],
        colWidths=[
            CONTENT_WIDTH / 4
        ]
        * 4,
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.white,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.45,
                    BORDER,
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.45,
                    BORDER,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    return table


def _state_path(
    states: tuple[str, ...],
    *,
    styles: dict[str, ParagraphStyle],
) -> Table:
    path_text = (
        "  >  ".join(
            str(state).upper()
            for state in states
        )
        if states
        else "-"
    )

    table = Table(
        [
            [
                Paragraph(
                    (
                        "<font size='6' color='#64748B'>"
                        "<b>STATE PROGRESSION</b>"
                        "</font><br/>"
                        f"<font size='8.5' color='#1E3A8A'>"
                        f"<b>{escape(path_text)}</b>"
                        "</font>"
                    ),
                    styles["body"],
                )
            ]
        ],
        colWidths=[
            CONTENT_WIDTH
        ],
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    SURFACE,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.45,
                    BORDER,
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    return table


def _list_paragraph(
    title: str,
    values: tuple[str, ...],
    *,
    styles: dict[str, ParagraphStyle],
) -> Paragraph:
    if not values:
        body = "-"
    else:
        body = "<br/>".join(
            f"- {escape(str(value))}"
            for value in values
        )

    return Paragraph(
        (
            f"<font size='6' color='#64748B'>"
            f"<b>{escape(title.upper())}</b>"
            "</font><br/>"
            f"{body}"
        ),
        styles["small"],
    )


def _scenario_context_table(
    report: RunReportData,
    *,
    styles: dict[str, ParagraphStyle],
) -> Table:
    scenario = report.scenario

    table = Table(
        [
            [
                _list_paragraph(
                    "Initial conditions",
                    scenario.initial_conditions,
                    styles=styles,
                ),
                _list_paragraph(
                    "Assumptions",
                    scenario.assumptions,
                    styles=styles,
                ),
            ]
        ],
        colWidths=[
            CONTENT_WIDTH / 2,
            CONTENT_WIDTH / 2,
        ],
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    SURFACE,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    BORDER,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    return table


def _behaviour_definition(
    behaviour: Any,
) -> str:
    projected = asdict(behaviour)

    core_fields = {
        "behaviour_id",
        "source",
        "during_state",
        "profile_id",
        "continuous",
        "description",
    }

    parts: list[str] = []

    description = projected.get(
        "description"
    )

    if _has_value(description):
        parts.append(str(description))

    for key, value in projected.items():
        if (
            key not in core_fields
            and _has_value(value)
        ):
            parts.append(
                f"{key}: "
                f"{_compact_format_value(value)}"
            )

    return "\n".join(parts) or "-"


def _behaviour_table(
    report: RunReportData,
    *,
    styles: dict[str, ParagraphStyle],
) -> Table:
    headers = (
        "Behaviour",
        "Source",
        "State",
        "Profile",
        "Mode",
        "Definition",
    )

    rows: list[list[Paragraph]] = [
        [
            Paragraph(
                f"<b>{header}</b>",
                styles["small"],
            )
            for header in headers
        ]
    ]

    for behaviour in report.scenario.behaviours:
        rows.append(
            [
                Paragraph(
                    _compact_paragraph_text(
                        behaviour.behaviour_id
                    ),
                    styles["small"],
                ),
                Paragraph(
                    _compact_paragraph_text(
                        behaviour.source
                    ),
                    styles["small"],
                ),
                Paragraph(
                    _compact_paragraph_text(
                        behaviour.during_state
                    ),
                    styles["small"],
                ),
                Paragraph(
                    _compact_paragraph_text(
                        behaviour.profile_id
                    ),
                    styles["small"],
                ),
                Paragraph(
                    (
                        "continuous"
                        if behaviour.continuous
                        else "state-bound"
                    ),
                    styles["small"],
                ),
                Paragraph(
                    _compact_paragraph_text(
                        _behaviour_definition(
                            behaviour
                        )
                    ),
                    styles["small"],
                ),
            ]
        )

    table = Table(
        rows,
        repeatRows=1,
        colWidths=[
            43 * mm,
            28 * mm,
            24 * mm,
            31 * mm,
            22 * mm,
            CONTENT_WIDTH - (148 * mm),
        ],
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    ACCENT_DARK,
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    BORDER,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        SURFACE,
                    ],
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    3,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    3,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    2.5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    2.5,
                ),
            ]
        )
    )

    return table



def _metric_context_key(
    explanation: Any,
) -> str:
    """
    Stable presentation grouping key.

    The renderer groups observations only when the recorded
    evaluation context is identical. It does not recalculate
    classifications or thresholds.
    """

    projected = {
        "metric_definition_id": (
            explanation.metric_definition_id
        ),
        "metric_name": explanation.metric_name,
        "unit": explanation.unit,
        "evaluation_statistic": (
            explanation.evaluation_statistic
        ),
        "direction": explanation.direction,
        "rule": (
            asdict(explanation.rule)
            if explanation.rule is not None
            else None
        ),
        "baseline": (
            asdict(explanation.baseline)
            if explanation.baseline is not None
            else None
        ),
        "benchmark": (
            asdict(explanation.benchmark)
            if explanation.benchmark is not None
            else None
        ),
    }

    return json.dumps(
        projected,
        sort_keys=True,
        default=_json_default,
    )


def _group_metric_explanations(
    explanations: tuple[Any, ...],
) -> list[list[Any]]:
    grouped: dict[str, list[Any]] = {}

    for explanation in explanations:
        key = _metric_context_key(
            explanation
        )

        grouped.setdefault(
            key,
            [],
        ).append(
            explanation
        )

    return list(
        grouped.values()
    )


def _metric_context_title(
    explanation: Any,
) -> str:
    parts = [
        (
            explanation.metric_name
            or explanation.metric_definition_id
        )
    ]

    if (
        explanation.baseline is not None
        and explanation.baseline.profile_id
    ):
        parts.append(
            "baseline "
            f"{explanation.baseline.profile_id}"
        )

    if (
        explanation.benchmark is not None
        and explanation.benchmark.profile_id
    ):
        parts.append(
            "benchmark "
            f"{explanation.benchmark.profile_id}"
        )

    return " | ".join(parts)


def _metric_context_items(
    explanation: Any,
) -> list[tuple[str, object]]:
    items: list[tuple[str, object]] = [
        (
            "Metric ID",
            explanation.metric_definition_id,
        ),
        (
            "Metric name",
            explanation.metric_name,
        ),
        (
            "Unit",
            explanation.unit,
        ),
        (
            "Statistic",
            explanation.evaluation_statistic,
        ),
        (
            "Direction",
            explanation.direction,
        ),
    ]

    rule = explanation.rule

    if rule is not None:
        items.extend(
            [
                (
                    "Rule mode",
                    rule.mode,
                ),
                (
                    "Evaluation order",
                    rule.evaluation_order,
                ),
                (
                    "Warning operator",
                    rule.warning_operator,
                ),
                (
                    "Blocking operator",
                    rule.blocking_operator,
                ),
                (
                    "Fallback",
                    rule.fallback_classification,
                ),
            ]
        )

    baseline = explanation.baseline

    if baseline is not None:
        items.extend(
            [
                (
                    "Baseline profile",
                    baseline.profile_id,
                ),
                (
                    "Baseline center",
                    baseline.center,
                ),
                (
                    "Baseline noise",
                    baseline.noise_stddev,
                ),
                (
                    "Baseline lower",
                    baseline.lower_bound,
                ),
                (
                    "Baseline upper",
                    baseline.upper_bound,
                ),
            ]
        )

    benchmark = explanation.benchmark

    if benchmark is not None:
        items.extend(
            [
                (
                    "Benchmark profile",
                    benchmark.profile_id,
                ),
                (
                    "Reference target",
                    benchmark.reference_target,
                ),
                (
                    "Warning threshold",
                    benchmark.warning_threshold,
                ),
                (
                    "Blocking threshold",
                    benchmark.blocking_threshold,
                ),
                (
                    "Applied overrides",
                    benchmark.applied_overrides,
                ),
            ]
        )

        provenance = benchmark.provenance

        if provenance is not None:
            items.extend(
                [
                    (
                        "Source ID",
                        provenance.source_id,
                    ),
                    (
                        "Source type",
                        provenance.source_type,
                    ),
                    (
                        "Source name",
                        provenance.source_name,
                    ),
                    (
                        "Source reference",
                        provenance.source_reference,
                    ),
                    (
                        "Source version",
                        provenance.version,
                    ),
                    (
                        "Retrieved on",
                        provenance.retrieved_on,
                    ),
                ]
            )

    return [
        (key, value)
        for key, value in items
        if _has_value(value)
    ]


def _metric_observation_table(
    explanations: list[Any],
    *,
    styles: dict[str, ParagraphStyle],
) -> Table:
    headers = (
        "Seq",
        "Event",
        "Value",
        "Classification",
        "Eval status",
        "State",
        "Behaviour",
    )

    rows: list[list[Paragraph]] = [
        [
            Paragraph(
                f"<b>{escape(header)}</b>",
                styles["micro"],
            )
            for header in headers
        ]
    ]

    for explanation in explanations:
        value = _format_value(
            explanation.observed_value
        )

        if explanation.unit:
            value = (
                f"{value} "
                f"{explanation.unit}"
            )

        rows.append(
            [
                Paragraph(
                    _paragraph_text(item),
                    styles["micro"],
                )
                for item in (
                    explanation.sequence_number,
                    explanation.event_id,
                    value,
                    explanation.recorded_classification,
                    explanation.evaluation_status,
                    explanation.scenario_state,
                    explanation.behaviour_profile_id,
                )
            ]
        )

    table = Table(
        rows,
        repeatRows=1,
        colWidths=[
            11 * mm,
            31 * mm,
            29 * mm,
            28 * mm,
            26 * mm,
            25 * mm,
            CONTENT_WIDTH - (150 * mm),
        ],
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    ACCENT_DARK,
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.2,
                    BORDER,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        SURFACE,
                    ],
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


def _canonical_populated_items(
    row: Any,
) -> list[tuple[str, object]]:
    result: list[
        tuple[str, object]
    ] = []

    for field in fields(row):
        if field.name == "raw_event":
            continue

        value = getattr(
            row,
            field.name,
        )

        if _has_value(value):
            result.append(
                (
                    field.name,
                    value,
                )
            )

    return result


def _canonical_unset_fields(
    row: Any,
) -> tuple[str, ...]:
    result: list[str] = []

    for field in fields(row):
        if field.name == "raw_event":
            continue

        value = getattr(
            row,
            field.name,
        )

        if not _has_value(value):
            result.append(
                field.name
            )

    return tuple(result)


def _raw_event_json(
    row: Any,
) -> str:
    return json.dumps(
        row.raw_event,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def _classification_rank(
    classification: str | None,
) -> int:
    return {
        "blocking": 4,
        "warning": 3,
        "normal": 2,
    }.get(
        (
            classification.lower()
            if classification
            else ""
        ),
        1,
    )


def _selected_metric_groups(
    report: RunReportData,
    *,
    limit: int = 2,
) -> list[list[Any]]:
    groups = _group_metric_explanations(
        report.metric_evaluation_explanations
    )

    usable = [
        [
            explanation
            for explanation in group
            if explanation.observed_value is not None
        ]
        for group in groups
    ]

    usable = [
        group
        for group in usable
        if group
    ]

    def score(
        group: list[Any],
    ) -> tuple[int, int, int, str]:
        max_severity = max(
            _classification_rank(
                explanation.recorded_classification
            )
            for explanation in group
        )

        non_normal = sum(
            1
            for explanation in group
            if (
                explanation.recorded_classification
                not in (
                    None,
                    "normal",
                )
            )
        )

        return (
            max_severity,
            non_normal,
            len(group),
            group[0].metric_definition_id,
        )

    return sorted(
        usable,
        key=score,
        reverse=True,
    )[:limit]


def _metric_number(
    value: float,
) -> str:
    absolute = abs(value)

    if absolute >= 1000:
        return f"{value:.0f}"

    if absolute >= 100:
        return f"{value:.1f}"

    if absolute >= 10:
        return f"{value:.1f}"

    if absolute >= 1:
        return f"{value:.2f}"

    return f"{value:.3f}"


def _classification_color(
    classification: str | None,
):
    normalized = (
        classification.lower()
        if classification
        else ""
    )

    if normalized == "blocking":
        return colors.HexColor(
            "#DC2626"
        )

    if normalized == "warning":
        return colors.HexColor(
            "#D97706"
        )

    if normalized == "normal":
        return colors.HexColor(
            "#16A34A"
        )

    return ACCENT


def _metric_series_chart(
    explanations: list[Any],
    *,
    width: float,
    height: float,
) -> Drawing:
    representative = explanations[0]

    drawing = Drawing(
        width,
        height,
    )

    drawing.add(
        Rect(
            0,
            0,
            width,
            height,
            fillColor=colors.white,
            strokeColor=BORDER,
            strokeWidth=0.6,
        )
    )

    title = (
        representative.metric_name
        or representative.metric_definition_id
    )

    drawing.add(
        String(
            7 * mm,
            height - (8 * mm),
            title,
            fontName="Helvetica-Bold",
            fontSize=8.5,
            fillColor=INK,
        )
    )

    context_parts: list[str] = []

    if (
        representative.baseline is not None
        and representative.baseline.profile_id
    ):
        context_parts.append(
            representative.baseline.profile_id
        )

    if (
        representative.benchmark is not None
        and representative.benchmark.profile_id
    ):
        context_parts.append(
            representative.benchmark.profile_id
        )

    if context_parts:
        drawing.add(
            String(
                7 * mm,
                height - (13 * mm),
                " | ".join(
                    context_parts
                ),
                fontName="Helvetica",
                fontSize=5.5,
                fillColor=MUTED,
            )
        )

    left = 17 * mm
    right = width - (8 * mm)
    bottom = 15 * mm
    top = height - (22 * mm)

    observations = [
        (
            explanation.sequence_number,
            float(
                explanation.observed_value
            ),
            explanation,
        )
        for explanation in explanations
        if explanation.observed_value is not None
    ]

    threshold_values: list[
        tuple[str, float, object]
    ] = []

    benchmark = representative.benchmark

    if benchmark is not None:
        if benchmark.reference_target is not None:
            threshold_values.append(
                (
                    "reference",
                    float(
                        benchmark.reference_target
                    ),
                    MUTED,
                )
            )

        if benchmark.warning_threshold is not None:
            threshold_values.append(
                (
                    "warning",
                    float(
                        benchmark.warning_threshold
                    ),
                    colors.HexColor(
                        "#D97706"
                    ),
                )
            )

        if benchmark.blocking_threshold is not None:
            threshold_values.append(
                (
                    "blocking",
                    float(
                        benchmark.blocking_threshold
                    ),
                    colors.HexColor(
                        "#DC2626"
                    ),
                )
            )

    numeric_values = [
        value
        for _, value, _ in observations
    ] + [
        value
        for _, value, _ in threshold_values
    ]

    if not numeric_values:
        return drawing

    data_min = min(
        numeric_values
    )
    data_max = max(
        numeric_values
    )

    span = (
        data_max
        - data_min
    )

    if span <= 0:
        span = (
            abs(data_max) * 0.2
            or 1.0
        )

    y_min = data_min - (
        span * 0.14
    )
    y_max = data_max + (
        span * 0.14
    )

    if (
        data_min >= 0
        and y_min < 0
    ):
        y_min = 0.0

    sequence_values = [
        sequence
        for sequence, _, _ in observations
    ]

    x_min = min(
        sequence_values
    )
    x_max = max(
        sequence_values
    )

    def x_pos(
        sequence: int,
    ) -> float:
        if x_max == x_min:
            return (
                left
                + right
            ) / 2

        return (
            left
            + (
                sequence
                - x_min
            )
            / (
                x_max
                - x_min
            )
            * (
                right
                - left
            )
        )

    def y_pos(
        value: float,
    ) -> float:
        return (
            bottom
            + (
                value
                - y_min
            )
            / (
                y_max
                - y_min
            )
            * (
                top
                - bottom
            )
        )

    for index in range(5):
        fraction = (
            index
            / 4
        )

        value = (
            y_min
            + fraction
            * (
                y_max
                - y_min
            )
        )

        y = y_pos(
            value
        )

        drawing.add(
            Line(
                left,
                y,
                right,
                y,
                strokeColor=SURFACE_STRONG,
                strokeWidth=0.5,
            )
        )

        drawing.add(
            String(
                2 * mm,
                y - 2,
                _metric_number(
                    value
                ),
                fontName="Helvetica",
                fontSize=5,
                fillColor=MUTED,
            )
        )

    drawing.add(
        Line(
            left,
            bottom,
            left,
            top,
            strokeColor=MUTED,
            strokeWidth=0.7,
        )
    )

    drawing.add(
        Line(
            left,
            bottom,
            right,
            bottom,
            strokeColor=MUTED,
            strokeWidth=0.7,
        )
    )

    for label, value, color in threshold_values:
        y = y_pos(
            value
        )

        drawing.add(
            Line(
                left,
                y,
                right,
                y,
                strokeColor=color,
                strokeWidth=0.8,
            )
        )

        drawing.add(
            String(
                right - (31 * mm),
                y + 2,
                (
                    f"{label}: "
                    f"{_metric_number(value)}"
                ),
                fontName="Helvetica",
                fontSize=5,
                fillColor=color,
            )
        )

    sorted_observations = sorted(
        observations,
        key=lambda item: item[0],
    )

    for current, following in pairwise(sorted_observations):
        current_sequence, current_value, _ = (
            current
        )
        next_sequence, next_value, _ = (
            following
        )

        drawing.add(
            Line(
                x_pos(
                    current_sequence
                ),
                y_pos(
                    current_value
                ),
                x_pos(
                    next_sequence
                ),
                y_pos(
                    next_value
                ),
                strokeColor=ACCENT,
                strokeWidth=1.5,
            )
        )

    for sequence, value, explanation in (
        sorted_observations
    ):
        x = x_pos(
            sequence
        )
        y = y_pos(
            value
        )

        point_color = (
            _classification_color(
                explanation.recorded_classification
            )
        )

        drawing.add(
            Circle(
                x,
                y,
                2.7,
                fillColor=point_color,
                strokeColor=colors.white,
                strokeWidth=0.7,
            )
        )

        drawing.add(
            String(
                x - 4,
                bottom - (6 * mm),
                str(sequence),
                fontName="Helvetica",
                fontSize=5,
                fillColor=MUTED,
            )
        )

        if (
            explanation.recorded_classification
            not in (
                None,
                "normal",
            )
        ):
            drawing.add(
                String(
                    x + 3,
                    y + 4,
                    str(
                        explanation.recorded_classification
                    ).upper(),
                    fontName="Helvetica-Bold",
                    fontSize=4.8,
                    fillColor=point_color,
                )
            )

    unit = (
        representative.unit
        or ""
    )

    drawing.add(
        String(
            2 * mm,
            height - (18 * mm),
            unit,
            fontName="Helvetica",
            fontSize=5,
            fillColor=MUTED,
        )
    )

    drawing.add(
        String(
            (
                left
                + right
            )
            / 2
            - (12 * mm),
            4 * mm,
            "event sequence",
            fontName="Helvetica",
            fontSize=5.3,
            fillColor=MUTED,
        )
    )

    return drawing


def _evidence_composition_chart(
    report: RunReportData,
    *,
    width: float,
    height: float,
) -> Drawing:
    counts: dict[
        str,
        int,
    ] = {}

    for row in report.evidence_rows:
        category = (
            row.source_domain
            or row.event_type
            or "other"
        )

        counts[category] = (
            counts.get(
                category,
                0,
            )
            + 1
        )

    ordered = sorted(
        counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    )

    drawing = Drawing(
        width,
        height,
    )

    drawing.add(
        Rect(
            0,
            0,
            width,
            height,
            fillColor=colors.white,
            strokeColor=BORDER,
            strokeWidth=0.6,
        )
    )

    drawing.add(
        String(
            7 * mm,
            height - (8 * mm),
            "Evidence composition",
            fontName="Helvetica-Bold",
            fontSize=8,
            fillColor=INK,
        )
    )

    if not ordered:
        return drawing

    max_count = max(
        value
        for _, value in ordered
    )

    bar_left = 38 * mm
    bar_right = width - (14 * mm)

    usable_height = (
        height
        - (18 * mm)
    )

    row_height = (
        usable_height
        / max(
            len(ordered),
            1,
        )
    )

    for index, (
        category,
        count,
    ) in enumerate(
        ordered
    ):
        center_y = (
            height
            - (15 * mm)
            - (
                index
                + 0.5
            )
            * row_height
        )

        bar_width = (
            0
            if max_count == 0
            else (
                count
                / max_count
                * (
                    bar_right
                    - bar_left
                )
            )
        )

        drawing.add(
            String(
                7 * mm,
                center_y - 2,
                str(category),
                fontName="Helvetica",
                fontSize=5.7,
                fillColor=INK,
            )
        )

        drawing.add(
            Rect(
                bar_left,
                center_y - 3,
                bar_width,
                6,
                fillColor=ACCENT,
                strokeColor=None,
            )
        )

        drawing.add(
            String(
                bar_left
                + bar_width
                + 4,
                center_y - 2,
                str(count),
                fontName="Helvetica-Bold",
                fontSize=5.7,
                fillColor=INK,
            )
        )

    drawing.add(
        String(
            width - (45 * mm),
            height - (8 * mm),
            (
                f"{len(report.evidence_rows)} "
                "events in report window"
            ),
            fontName="Helvetica",
            fontSize=5.5,
            fillColor=MUTED,
        )
    )

    return drawing


def _evidence_overview_flowables(
    report: RunReportData,
    *,
    styles: dict[str, ParagraphStyle],
) -> list[object]:
    story: list[object] = []

    story.append(
        Paragraph(
            "Evidence Overview",
            styles["heading"],
        )
    )

    story.append(
        Paragraph(
            (
                "Visual summary of recorded StreamOps evidence in "
                "this report window. Metric values, classifications "
                "and threshold lines come directly from the recorded "
                "evidence and benchmark context; no operational "
                "conclusion is inferred here."
            ),
            styles["body"],
        )
    )

    story.append(
        Spacer(
            1,
            4 * mm,
        )
    )

    selected = _selected_metric_groups(
        report,
        limit=2,
    )

    chart_width = (
        CONTENT_WIDTH
        - (6 * mm)
    ) / 2

    chart_height = (
        72 * mm
    )

    chart_cells: list[object] = []

    for group in selected:
        chart_cells.append(
            _metric_series_chart(
                group,
                width=chart_width,
                height=chart_height,
            )
        )

    while len(chart_cells) < 2:
        chart_cells.append(
            Paragraph(
                (
                    "No additional numeric metric series "
                    "was available for this report window."
                ),
                styles["small"],
            )
        )

    charts = Table(
        [
            chart_cells
        ],
        colWidths=[
            chart_width,
            chart_width,
        ],
        hAlign="LEFT",
    )

    charts.setStyle(
        TableStyle(
            [
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
            ]
        )
    )

    story.append(
        charts
    )

    story.append(
        Spacer(
            1,
            5 * mm,
        )
    )

    story.append(
        _evidence_composition_chart(
            report,
            width=CONTENT_WIDTH,
            height=42 * mm,
        )
    )

    return story


def _event_timeline_table(
    report: RunReportData,
    *,
    styles: dict[str, ParagraphStyle],
) -> Table:
    headers = (
        "#",
        "Time",
        "Event",
        "Source",
        "Target",
        "State",
        "Behaviour",
    )

    rows: list[list[Paragraph]] = [
        [
            Paragraph(
                f"<b>{escape(header)}</b>",
                styles["micro"],
            )
            for header in headers
        ]
    ]

    for row in report.evidence_rows:
        event = (
            f"{row.event_id}\n"
            f"{row.event_type}"
        )

        source = (
            f"{_format_value(row.source_domain)}\n"
            f"{_format_value(row.source_system)}"
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
            "%Y-%m-%d\n%H:%M:%S %z"
        )

        values = (
            row.sequence_number,
            event_time,
            event,
            source,
            target,
            row.scenario_state,
            row.behaviour_id,
        )

        rows.append(
            [
                Paragraph(
                    _paragraph_text(value),
                    styles["micro"],
                )
                for value in values
            ]
        )

    table = Table(
        rows,
        repeatRows=1,
        colWidths=[
            8 * mm,
            31 * mm,
            49 * mm,
            39 * mm,
            46 * mm,
            24 * mm,
            CONTENT_WIDTH - (197 * mm),
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
                    0.2,
                    BORDER,
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    ACCENT_DARK,
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        SURFACE,
                    ],
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    1.8,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    1.8,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    1.8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    1.8,
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

    # -----------------------------------------------------
    # PAGE 1 - RUN OVERVIEW
    # -----------------------------------------------------

    story.append(
        _brand_header(
            report,
            styles=styles,
        )
    )

    story.append(
        Spacer(
            1,
            3 * mm,
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
            styles["subtitle"],
        )
    )

    story.append(
        Spacer(
            1,
            3 * mm,
        )
    )

    story.append(
        _overview_cards(
            report,
            styles=styles,
        )
    )

    story.append(
        Spacer(
            1,
            4 * mm,
        )
    )

    story.append(
        Paragraph(
            "Report Scope",
            styles["heading"],
        )
    )

    story.append(
        _run_kpi_cards(
            report,
            styles=styles,
        )
    )

    story.append(
        Spacer(
            1,
            2 * mm,
        )
    )

    story.append(
        Paragraph(
            (
                "<b>Maximum events:</b> "
                f"{report.scope.maximum_event_count} | "
                "<b>Retained events:</b> "
                f"{report.scope.total_retained_event_count} | "
                "<b>Included events:</b> "
                f"{report.scope.included_event_count} | "
                "<b>Complete run:</b> "
                f"{report.scope.complete_run_represented}"
            ),
            styles["small"],
        )
    )

    story.append(
        Paragraph(
            "Run Execution",
            styles["heading"],
        )
    )

    story.append(
        _paired_table(
            [
                (
                    "Run ID",
                    report.execution.run_id,
                ),
                (
                    "Status",
                    report.execution.status,
                ),
                (
                    "Started",
                    report.execution.started_at,
                ),
                (
                    "Completed",
                    report.execution.completed_at,
                ),
                (
                    "Random seed",
                    report.execution.random_seed,
                ),
                (
                    "Event interval",
                    report.execution.event_interval_seconds,
                ),
                (
                    "Validation passed",
                    report.execution.validation_passed,
                ),
                (
                    "Execution mode",
                    report.execution.execution_mode,
                ),
            ],
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
        Paragraph(
            _compact_paragraph_text(
                scenario.description
            ),
            styles["body"],
        )
    )

    story.append(
        Spacer(
            1,
            3 * mm,
        )
    )

    story.append(
        _state_path(
            scenario.state_sequence,
            styles=styles,
        )
    )

    story.append(
        Spacer(
            1,
            2 * mm,
        )
    )

    story.append(
        Paragraph(
            (
                "<b>Report Context:</b> generated "
                f"{escape(_format_value(report.generated_at))} | "
                f"context {escape(report.context_resolution)}"
            ),
            styles["micro"],
        )
    )

    story.append(
        PageBreak()
    )

    # -----------------------------------------------------
    # PAGE 2 - SCENARIO & GENERATION DEFINITION
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "Scenario & Generation Definition",
            styles["heading"],
        )
    )

    story.append(
        _paired_table(
            [
                (
                    "Scenario ID",
                    scenario.scenario_id,
                ),
                (
                    "Name",
                    scenario.name,
                ),
                (
                    "Family",
                    scenario.family,
                ),
                (
                    "Industry",
                    scenario.industry,
                ),
                (
                    "Risk",
                    scenario.risk,
                ),
                (
                    "Change required",
                    scenario.change_required,
                ),
                (
                    "Tags",
                    scenario.tags,
                ),
            ],
            styles=styles,
        )
    )

    story.append(
        Spacer(
            1,
            3 * mm,
        )
    )

    story.append(
        _scenario_context_table(
            report,
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
        _paired_table(
            _compact_dataclass_items(
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
            _paired_table(
                _compact_dataclass_items(
                    scenario.frequency
                ),
                styles=styles,
            )
        )

    story.append(
        Paragraph(
            "Generation Behaviours",
            styles["heading"],
        )
    )

    story.append(
        _behaviour_table(
            report,
            styles=styles,
        )
    )

    story.append(
        Paragraph(
            "Resolved Run Target",
            styles["heading"],
        )
    )

    story.append(
        _paired_table(
            _compact_dataclass_items(
                report.target
            ),
            styles=styles,
        )
    )

    story.append(
        PageBreak()
    )

    # -----------------------------------------------------
    # PAGE 3 - EVIDENCE OVERVIEW
    # -----------------------------------------------------

    story.extend(
        _evidence_overview_flowables(
            report,
            styles=styles,
        )
    )

    story.append(
        PageBreak()
    )

    # -----------------------------------------------------
    # PAGE 4 - EVENT TIMELINE
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "Event Timeline",
            styles["heading"],
        )
    )

    story.append(
        Paragraph(
            (
                "Chronological view of every event included in "
                "this report snapshot. Detailed canonical fields "
                "and complete raw payloads for the same bounded "
                "evidence window remain available in the "
                "Canonical Evidence Appendix."
            ),
            styles["body"],
        )
    )

    story.append(
        Spacer(
            1,
            3 * mm,
        )
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

    story.append(
        Paragraph(
            (
                "Recorded metric evaluation contexts are shown once "
                "per unique rule, baseline and benchmark combination. "
                "Every observation classified under that context is "
                "listed below. StreamOps does not recalculate the "
                "recorded classification in this report."
            ),
            styles["body"],
        )
    )

    if not report.metric_evaluation_explanations:
        story.append(
            Paragraph(
                "No metric evaluation explanations were recorded.",
                styles["body"],
            )
        )

    metric_groups = _group_metric_explanations(
        report.metric_evaluation_explanations
    )

    for group_index, explanations in enumerate(
        metric_groups,
        start=1,
    ):
        representative = explanations[0]

        story.append(
            Paragraph(
                (
                    f"Evaluation Context {group_index} - "
                    f"{escape(_metric_context_title(representative))}"
                ),
                styles["subheading"],
            )
        )

        story.append(
            _paired_table(
                _metric_context_items(
                    representative
                ),
                styles=styles,
            )
        )

        benchmark = representative.benchmark

        if (
            benchmark is not None
            and benchmark.provenance is not None
            and benchmark.provenance.rationale
        ):
            story.append(
                Paragraph(
                    (
                        "<b>Benchmark rationale:</b> "
                        f"{escape(benchmark.provenance.rationale)}"
                    ),
                    styles["small"],
                )
            )

        story.append(
            Spacer(1, 2 * mm)
        )

        story.append(
            _metric_observation_table(
                explanations,
                styles=styles,
            )
        )

        story.append(
            Spacer(1, 4 * mm)
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
                "represented using the canonical RunEvidenceRow "
                "projection used by the CSV export. Populated fields "
                "are shown compactly, unset or empty fields are "
                "explicitly inventoried, and raw_event contains the "
                "complete generated event envelope and data payload."
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

        populated_items = (
            _canonical_populated_items(
                row
            )
        )

        if populated_items:
            story.append(
                _paired_table(
                    populated_items,
                    styles=styles,
                )
            )

        unset_fields = (
            _canonical_unset_fields(
                row
            )
        )

        if unset_fields:
            story.append(
                Spacer(1, 1.5 * mm)
            )

            story.append(
                Paragraph(
                    (
                        "<b>Unset / empty canonical fields:</b> "
                        f"{escape(', '.join(unset_fields))}"
                    ),
                    styles["micro"],
                )
            )

        story.append(
            Spacer(1, 1.5 * mm)
        )

        story.append(
            Paragraph(
                (
                    "<b>raw_event - complete generated envelope "
                    "and payload</b>"
                ),
                styles["small"],
            )
        )

        story.append(
            Paragraph(
                escape(
                    _raw_event_json(
                        row
                    )
                ),
                styles["micro"],
            )
        )

        story.append(
            Spacer(1, 4 * mm)
        )

    def draw_footer(
        canvas,
        doc,
    ) -> None:
        canvas.saveState()

        canvas.setStrokeColor(
            BORDER
        )
        canvas.setLineWidth(
            0.5
        )
        canvas.line(
            LEFT_MARGIN,
            10 * mm,
            PAGE_SIZE[0] - RIGHT_MARGIN,
            10 * mm,
        )

        canvas.setFont(
            "Helvetica-Bold",
            6.5,
        )
        canvas.setFillColor(
            ACCENT_DARK
        )
        canvas.drawString(
            LEFT_MARGIN,
            6 * mm,
            "STREAMOPS",
        )

        canvas.setFont(
            "Helvetica",
            6.5,
        )
        canvas.setFillColor(
            MUTED
        )
        canvas.drawString(
            LEFT_MARGIN + (19 * mm),
            6 * mm,
            (
                "Run Evidence Report - "
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
