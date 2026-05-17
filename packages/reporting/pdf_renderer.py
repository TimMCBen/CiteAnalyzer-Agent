from __future__ import annotations

from pathlib import Path
from typing import Any

CM = 28.3464566929


def render_pdf_report(payload: dict[str, Any], output_path: Path) -> None:
    try:
        from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
        from reportlab.graphics.charts.piecharts import Pie
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("reportlab is required for PDF export") from exc

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CNTitle", parent=styles["Title"], fontName="STSong-Light", fontSize=22, leading=28, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="CNHeading", parent=styles["Heading2"], fontName="STSong-Light", fontSize=14, leading=18, spaceBefore=12, spaceAfter=8))
    styles.add(ParagraphStyle(name="CNBody", parent=styles["BodyText"], fontName="STSong-Light", fontSize=9.5, leading=14))
    styles.add(ParagraphStyle(name="CNMuted", parent=styles["BodyText"], fontName="STSong-Light", fontSize=8.5, leading=12, textColor=colors.HexColor("#666666")))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title="CiteAnalyzer Report",
    )

    summary = payload["summary"]
    charts = payload["charts"]
    provenance = payload["provenance"]
    contexts = payload.get("contexts", [])
    story: list[Any] = []

    story.append(Paragraph("论文被引分析报告", styles["CNTitle"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(str(summary.get("target_title") or "Unknown Target Paper"), styles["CNHeading"]))
    story.append(Paragraph(f"DOI: {summary.get('target_doi') or 'N/A'}", styles["CNMuted"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(_metrics_table(summary, styles, Table, TableStyle, colors))

    story.append(Paragraph("分析摘要", styles["CNHeading"]))
    story.extend(_bullet_list(summary.get("executive_summary", []), styles, Paragraph))

    story.append(Paragraph("可视化概览", styles["CNHeading"]))
    story.append(_vertical_bar_chart("引用年份趋势", charts.get("year_trend", {}), VerticalBarChart, Drawing, String, colors))
    story.append(Spacer(1, 0.25 * cm))
    story.append(_pie_chart("引用情感分布", charts.get("sentiment_distribution", {}), Pie, Drawing, String, colors))
    story.append(Spacer(1, 0.25 * cm))
    story.append(_horizontal_bar_chart("施引来源国家/地区分布", charts.get("country_distribution", {}), HorizontalBarChart, Drawing, String, colors))
    story.append(Spacer(1, 0.25 * cm))
    story.append(_horizontal_bar_chart("施引作者机构分布 Top 8", charts.get("institution_distribution", {}), HorizontalBarChart, Drawing, String, colors))

    story.append(PageBreak())
    story.append(Paragraph("重要学者", styles["CNHeading"]))
    story.append(_scholar_table(summary.get("top_scholars", []), styles, Table, TableStyle, colors))

    story.append(Paragraph("代表性引用语境", styles["CNHeading"]))
    representative_contexts = summary.get("representative_contexts", {})
    if isinstance(representative_contexts, dict):
        for label in ("positive", "critical", "neutral"):
            items = representative_contexts.get(label, [])
            if not items:
                continue
            story.append(Paragraph(_sentiment_heading(label), styles["CNBody"]))
            for item in items[:3]:
                story.append(Paragraph(_context_summary(item), styles["CNMuted"]))
    else:
        story.append(Paragraph("暂无代表性引用语境。", styles["CNMuted"]))

    story.append(Paragraph("数据质量与局限", styles["CNHeading"]))
    story.extend(_bullet_list(summary.get("manual_attention_items", []), styles, Paragraph, empty="当前没有需要人工关注的项目。"))
    country_trace = provenance.get("country_resolution_trace", [])
    if country_trace:
        story.append(Paragraph("国家/地区解析说明", styles["CNHeading"]))
        story.append(_country_trace_table(country_trace, styles, Table, TableStyle, colors))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)


def _metrics_table(summary: dict[str, Any], styles: Any, Table: Any, TableStyle: Any, colors: Any) -> Any:
    rows = [
        ["施引文献", summary.get("citation_count", 0), "上下文命中", summary.get("context_found", 0)],
        ["重量级候选", summary.get("heavyweight_candidates", 0), "高影响力候选", summary.get("high_impact_candidates", 0)],
        ["弱信号候选", summary.get("weak_signal_candidates", 0), "未知情感", summary.get("unknown_sentiments", 0)],
    ]
    table = Table(rows, colWidths=[3.2 * CM, 2.2 * CM, 3.2 * CM, 2.2 * CM])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff7eb")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#dfd1ba")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dfd1ba")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#9f4f2b")),
                ("TEXTCOLOR", (3, 0), (3, -1), colors.HexColor("#9f4f2b")),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("ALIGN", (3, 0), (3, -1), "CENTER"),
            ]
        )
    )
    return table


def _bullet_list(items: Any, styles: Any, Paragraph: Any, empty: str = "暂无内容。") -> list[Any]:
    if not isinstance(items, list) or not items:
        return [Paragraph(empty, styles["CNMuted"])]
    return [Paragraph(f"• {item}", styles["CNBody"]) for item in items[:8]]


def _vertical_bar_chart(title: str, values: Any, VerticalBarChart: Any, Drawing: Any, String: Any, colors: Any) -> Any:
    items = _top_items(values, limit=8)
    drawing = Drawing(430, 170)
    drawing.add(String(8, 154, title, fontName="STSong-Light", fontSize=10, fillColor=colors.HexColor("#1f2937")))
    if not items:
        drawing.add(String(8, 78, "暂无数据", fontName="STSong-Light", fontSize=9, fillColor=colors.HexColor("#666666")))
        return drawing
    chart = VerticalBarChart()
    chart.x = 28
    chart.y = 28
    chart.height = 110
    chart.width = 360
    chart.data = [[count for _, count in items]]
    chart.categoryAxis.categoryNames = [label for label, _ in items]
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueStep = 1
    chart.bars[0].fillColor = colors.HexColor("#9f4f2b")
    drawing.add(chart)
    return drawing


def _horizontal_bar_chart(title: str, values: Any, HorizontalBarChart: Any, Drawing: Any, String: Any, colors: Any) -> Any:
    items = _top_items(values, limit=8)
    drawing = Drawing(430, 180)
    drawing.add(String(8, 164, title, fontName="STSong-Light", fontSize=10, fillColor=colors.HexColor("#1f2937")))
    if not items:
        drawing.add(String(8, 82, "暂无数据", fontName="STSong-Light", fontSize=9, fillColor=colors.HexColor("#666666")))
        return drawing
    chart = HorizontalBarChart()
    chart.x = 120
    chart.y = 20
    chart.height = 130
    chart.width = 260
    chart.data = [[count for _, count in items]]
    chart.categoryAxis.categoryNames = [label[:24] for label, _ in items]
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueStep = 1
    chart.bars[0].fillColor = colors.HexColor("#b58a48")
    drawing.add(chart)
    return drawing


def _pie_chart(title: str, values: Any, Pie: Any, Drawing: Any, String: Any, colors: Any) -> Any:
    items = _top_items(values, limit=6)
    drawing = Drawing(430, 180)
    drawing.add(String(8, 164, title, fontName="STSong-Light", fontSize=10, fillColor=colors.HexColor("#1f2937")))
    if not items:
        drawing.add(String(8, 82, "暂无数据", fontName="STSong-Light", fontSize=9, fillColor=colors.HexColor("#666666")))
        return drawing
    pie = Pie()
    pie.x = 110
    pie.y = 20
    pie.width = 130
    pie.height = 130
    pie.data = [count for _, count in items]
    pie.labels = [label for label, _ in items]
    palette = ["#b85c42", "#8f8172", "#6f8f5b", "#b9aa96", "#9f4f2b", "#b58a48"]
    for index, color in enumerate(palette[: len(items)]):
        pie.slices[index].fillColor = colors.HexColor(color)
    drawing.add(pie)
    return drawing


def _scholar_table(items: Any, styles: Any, Table: Any, TableStyle: Any, colors: Any) -> Any:
    rows = [["作者", "标签", "h-index", "机构", "证据"]]
    if isinstance(items, list):
        for item in items[:10]:
            if not isinstance(item, dict):
                continue
            rows.append(
                [
                    item.get("name", ""),
                    item.get("label", ""),
                    item.get("h_index", "N/A"),
                    ", ".join(item.get("affiliations", [])[:1]) if isinstance(item.get("affiliations"), list) else "",
                    "; ".join(item.get("evidence", [])[:2]) if isinstance(item.get("evidence"), list) else "",
                ]
            )
    if len(rows) == 1:
        rows.append(["暂无", "暂无", "N/A", "暂无", "暂无"])
    table = Table(rows, colWidths=[2.7 * CM, 2.7 * CM, 1.4 * CM, 4 * CM, 5 * CM])
    table.setStyle(_table_style(TableStyle, colors))
    return table


def _country_trace_table(items: Any, styles: Any, Table: Any, TableStyle: Any, colors: Any) -> Any:
    rows = [["机构", "国家/地区", "方法", "置信度"]]
    if isinstance(items, list):
        for item in items[:12]:
            if isinstance(item, dict):
                rows.append([item.get("institution", ""), item.get("country", ""), item.get("method", ""), item.get("confidence", "")])
    table = Table(rows, colWidths=[6 * CM, 3 * CM, 2 * CM, 2 * CM])
    table.setStyle(_table_style(TableStyle, colors))
    return table


def _table_style(TableStyle: Any, colors: Any) -> Any:
    return TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3e0ce")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#dfd1ba")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dfd1ba")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ]
    )


def _top_items(values: Any, limit: int) -> list[tuple[str, int]]:
    if not isinstance(values, dict):
        return []
    items = []
    for label, count in values.items():
        try:
            numeric = int(count)
        except (TypeError, ValueError):
            continue
        if numeric > 0:
            items.append((str(label), numeric))
    return sorted(items, key=lambda item: (-item[1], item[0]))[:limit]


def _context_summary(item: Any) -> str:
    if not isinstance(item, dict):
        return str(item)
    text = str(item.get("context_text") or "No context available.")
    if len(text) > 420:
        text = text[:417] + "..."
    return f"{item.get('citing_paper_id', 'unknown')}: {text}"


def _sentiment_heading(label: str) -> str:
    return {
        "positive": "正向引用",
        "critical": "批评性引用",
        "neutral": "中性介绍",
    }.get(label, label)


def _footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFont("STSong-Light", 8)
    canvas.setFillColorRGB(0.4, 0.4, 0.4)
    canvas.drawRightString(540, 25, f"Page {doc.page}")
    canvas.restoreState()
