"""PDF rendering of analysis reports (ReportLab / Platypus).

Produces a self-contained, shareable document mirroring the report view:
overall assessment, triage, per-regulation findings with evidence and
recommendations, remediation plan, and CELLAR/EUR-Lex legal sources.
"""
import html
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import config
from .models import AnalysisReport, Finding

EC_BLUE = colors.HexColor("#004494")
INK = colors.HexColor("#232c36")
MUTED = colors.HexColor("#5b6873")

RISK_COLORS = {
    "critical": colors.HexColor("#8f2d56"),
    "high": colors.HexColor("#da2131"),
    "medium": colors.HexColor("#d97706"),
    "low": colors.HexColor("#006fb4"),
    "info": colors.HexColor("#006fb4"),
    "compliant": colors.HexColor("#467a39"),
    "unknown": MUTED,
}

RISK_LABELS = {
    "critical": "Critical risk",
    "high": "High risk",
    "medium": "Medium risk",
    "low": "Low risk",
    "compliant": "No issues found",
    "unknown": "Unknown",
}

STATUS_LABELS = {
    "violation_likely": "Violation likely",
    "risk_identified": "Risk identified",
    "attention": "Needs attention",
    "compliant": "Compliant",
    "not_applicable": "Not applicable",
}


def _e(text: str | None) -> str:
    return html.escape(text or "")


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK)
    return {
        "base": base,
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=16, leading=20,
                             textColor=colors.white),
        "h1sub": ParagraphStyle("h1sub", parent=base, fontSize=9, leading=12,
                                textColor=colors.HexColor("#cfe0f4")),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=12.5,
                             leading=16, spaceBefore=14, spaceAfter=4, textColor=EC_BLUE),
        "risk": ParagraphStyle("risk", parent=base, fontName="Helvetica-Bold", fontSize=14, leading=18),
        "meta": ParagraphStyle("meta", parent=base, fontSize=8, leading=11, textColor=MUTED),
        "quote": ParagraphStyle("quote", parent=base, fontName="Helvetica-Oblique",
                                leftIndent=10, textColor=colors.HexColor("#44535f")),
        "footer": ParagraphStyle("footer", parent=base, fontSize=7.5, leading=10,
                                 textColor=MUTED, alignment=TA_CENTER),
    }


def _severity_chip(severity: str) -> Paragraph:
    color = RISK_COLORS.get(severity, MUTED)
    return Paragraph(
        f'<font color="{color.hexval()}"><b>{severity.upper()}</b></font>',
        _styles()["base"],
    )


def _finding_block(finding: Finding, styles) -> KeepTogether:
    color = RISK_COLORS.get(finding.severity, MUTED)
    rows = [[
        _severity_chip(finding.severity),
        Paragraph(f"<b>{_e(finding.provision_ref)}</b> — {_e(finding.title)}", styles["base"]),
    ]]
    body: list = [Paragraph(_e(finding.rationale), styles["base"])]
    if finding.evidence_quote:
        body.append(Spacer(0, 2))
        body.append(Paragraph(f"“{_e(finding.evidence_quote)}”", styles["quote"]))
    body.append(Spacer(0, 2))
    body.append(Paragraph(f"<b>Recommendation:</b> {_e(finding.recommendation)}", styles["base"]))
    if finding.source_url:
        body.append(Paragraph(
            f'Official text: <link href="{_e(finding.source_url)}" color="#004494">'
            f"{_e(finding.source_url)}</link> (CELEX {_e(finding.celex)})",
            styles["meta"],
        ))
    rows.append(["", body])
    table = Table(rows, colWidths=[22 * mm, None])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, color),
        ("LEFTPADDING", (0, 0), (0, -1), 6),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafbfc")),
    ]))
    return KeepTogether([table, Spacer(0, 6)])


def build_pdf(report: AnalysisReport) -> bytes:
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
        title=f"Compliance report — {report.campaign.title}",
        author="Marketing Compliance Checker",
    )

    def _page_footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            18 * mm, 10 * mm,
            "Decision-support screening anchored to the Publications Office CELLAR repository — "
            "indicative, not legal advice.")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    story: list = []

    # Header banner
    banner = Table([[
        [Paragraph("Marketing Compliance Checker", styles["h1"]),
         Paragraph("AI Act · GDPR · DSA · UCPD — GraphRAG agentic screening", styles["h1sub"])],
    ]], colWidths=[None])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), EC_BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(banner)
    story.append(Spacer(0, 10))

    # Campaign + overall assessment
    story.append(Paragraph(f"Compliance report — {_e(report.campaign.title)}",
                           ParagraphStyle("t", parent=styles["h2"], fontSize=14, spaceBefore=0)))
    engine = ("agentic (GraphRAG + Claude agents)" if report.engine == "agentic"
              else "heuristic (GraphRAG retrieval only — verify manually)")
    story.append(Paragraph(
        f"Report {_e(report.id)} · {_e(report.created_at[:19].replace('T', ' '))} UTC · engine: {engine}",
        styles["meta"]))
    if report.parent_id:
        story.append(Paragraph(f"Re-analysis of report {_e(report.parent_id)}", styles["meta"]))
    if report.campaign.channels:
        story.append(Paragraph(f"Channels: {_e(', '.join(report.campaign.channels))}", styles["meta"]))
    if report.campaign.target_audience:
        story.append(Paragraph(f"Target audience: {_e(report.campaign.target_audience)}", styles["meta"]))
    story.append(Spacer(0, 8))

    risk_color = RISK_COLORS.get(report.overall_risk, MUTED)
    story.append(Paragraph(
        f'Overall assessment: <font color="{risk_color.hexval()}">'
        f"{RISK_LABELS.get(report.overall_risk, report.overall_risk)}</font>",
        styles["risk"]))
    story.append(Spacer(0, 4))
    story.append(Paragraph(_e(report.executive_summary), styles["base"]))

    if report.triage:
        story.append(Paragraph("Triage", styles["h2"]))
        story.append(Paragraph(_e(report.triage.summary), styles["base"]))
        if report.triage.detected_practices:
            story.append(Paragraph(
                f"Detected practices: {_e(', '.join(report.triage.detected_practices))}",
                styles["meta"]))

    for verdict in report.verdicts:
        label = config.REGULATION_LABELS.get(verdict.regulation, verdict.regulation)
        story.append(Paragraph(
            f"{_e(label)} — {STATUS_LABELS.get(verdict.status, verdict.status)}", styles["h2"]))
        if verdict.notes:
            story.append(Paragraph(_e(verdict.notes), styles["base"]))
            story.append(Spacer(0, 4))
        for finding in verdict.findings:
            story.append(_finding_block(finding, styles))

    if report.recommendations:
        story.append(Paragraph("Remediation plan", styles["h2"]))
        for i, reco in enumerate(report.recommendations, 1):
            story.append(Paragraph(f"{i}. {_e(reco)}", styles["base"]))
            story.append(Spacer(0, 2))

    celexes: dict[str, str] = {}
    for verdict in report.verdicts:
        for finding in verdict.findings:
            if finding.celex:
                celexes.setdefault(
                    finding.celex,
                    config.REGULATION_LABELS.get(verdict.regulation, verdict.regulation))
    if celexes:
        story.append(Paragraph("Legal sources", styles["h2"]))
        story.append(Paragraph(
            "Acts cited in this report, identified in the Publications Office CELLAR "
            "repository by CELEX number:", styles["meta"]))
        story.append(Spacer(0, 3))
        for celex, label in celexes.items():
            url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
            story.append(Paragraph(
                f"CELEX {celex} — {_e(label)} · "
                f'<link href="{url}" color="#004494">{url}</link>', styles["base"]))
        story.append(Spacer(0, 2))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d8dde3")))

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()
