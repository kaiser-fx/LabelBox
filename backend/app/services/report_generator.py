from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.db.models.inspection_session import InspectionSession
from app.schemas.session import SessionReport


def build_session_pdf(session: InspectionSession, report: SessionReport) -> bytes:
    """Render a concise, cited inspection report as a downloadable PDF."""
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("LabelBox Inspection Report", styles["Title"]),
        Paragraph(
            f"Store: {session.store_name}<br/>Location: {session.location or 'Not recorded'}<br/>"
            f"Started: {session.started_at:%d %b %Y, %H:%M UTC}<br/>"
            f"Generated: {datetime.now(timezone.utc):%d %b %Y, %H:%M UTC}",
            styles["BodyText"],
        ),
        Spacer(1, 6 * mm),
    ]
    summary = [
        ["Products scanned", "Compliant", "Scans with issues", "Recorded violations"],
        [str(report.total_scans), str(report.compliant_scans), str(report.scans_with_violations), str(report.total_violations)],
    ]
    story.append(_styled_table(summary, [38 * mm, 38 * mm, 48 * mm, 48 * mm]))
    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph("Cited violations", styles["Heading2"]))
    violations = [
        ["Scan", "Severity", "Rule", "Reason and citation"],
    ]
    for scan in sorted(session.scans, key=lambda item: item.captured_at):
        for violation in scan.violations:
            violations.append([
                scan.id[:8], violation.severity.title(), violation.rule_id.replace("_", "."),
                Paragraph(f"{violation.reason}<br/><font size=8>{violation.citation}</font>", styles["BodyText"]),
            ])
    if len(violations) == 1:
        violations.append(["-", "-", "-", "No violations were recorded in this session."])
    story.append(_styled_table(violations, [24 * mm, 22 * mm, 20 * mm, 102 * mm]))
    document.build(story)
    return output.getvalue()


def _styled_table(rows: list[list[object]], widths: list[float]) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#21211F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E4E1DA")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table
