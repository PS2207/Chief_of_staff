from datetime import datetime
from helper import get_thread_by_id                            
        # ── Generate proof functions ───────────────────────────────
def generate_proof_markdown(approved, threads):
            lines = [
                "# 📧 Proof of Human-in-the-Loop Review",
                f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"**Total Approved Drafts:** {len(approved)}",
                "",
                "---",
                "",
            ]
            for thread_id, draft_text in approved.items():
                t = get_thread_by_id(thread_id, threads)
                subject = t.get("subject", "(No subject)") if t else "(Unknown thread)"
                messages = t.get("messages", []) if t else []

                lines.append(f"## {subject}")
                lines.append("")
                lines.append("### Original Email Thread")
                lines.append("")
                for msg in messages:
                    lines.append(f"> **From:** {msg.get('from', '')}")
                    lines.append(f"> **Date:** {msg.get('date', '')}")
                    lines.append(">")
                    for body_line in msg.get("body", "").split("\n"):
                        lines.append(f"> {body_line}")
                    lines.append(">")
                    lines.append("---")
                    lines.append("")
                lines.append("### ✅ Approved Draft Reply")
                lines.append("")
                lines.append("```")
                lines.append(draft_text)
                lines.append("```")
                lines.append("")
                lines.append("---")
                lines.append("")
            lines.append("")
            lines.append("---")
            lines.append("*Shared with #MyChiefOfStaff to earn your Ghostwriter badge!*")
            return "\n".join(lines)

def generate_proof_html(approved, threads):
            cards_html = ""
            for thread_id, draft_text in approved.items():
                t = get_thread_by_id(thread_id, threads)
                subject = t.get("subject", "(No subject)") if t else "(Unknown thread)"
                messages = t.get("messages", []) if t else []

                # Build original messages HTML
                msgs_html = ""
                for msg in messages:
                    body_escaped = msg.get("body", "").replace("\n", "<br>")
                    msgs_html += f"""
                    <div class="msg">
                        <div class="msg-from">{msg.get('from', '')}</div>
                        <div class="msg-date">{msg.get('date', '')}</div>
                        <div class="msg-body">{body_escaped}</div>
                    </div>
                    """
                draft_escaped = draft_text.replace("\n", "<br>")

                cards_html += f"""
                <div class="card">
                    <h2>{subject}</h2>
                    <div class="grid">
                        <div class="original">
                            <h3>📨 Original Thread</h3>
                            {msgs_html}
                        </div>
                        <div class="draft">
                            <h3>✅ Approved Draft</h3>
                            <div class="draft-text">{draft_escaped}</div>
                        </div>
                    </div>
                </div>
                """

            return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Proof of Review — The Draft Desk</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background-color: #1a1a2e;
            color: #e0e0e0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            padding: 2rem;
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{ color: #e94560; margin-bottom: 0.5rem; }}
        .subtitle {{ color: #888; margin-bottom: 2rem; }}
        .card {{
            background: #16213e;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}
        .card h2 {{ color: #e94560; margin-bottom: 1rem; }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }}
        .original {{
            background: #0f3460;
            border: 2px solid #e67e22;
            border-radius: 8px;
            padding: 1rem;
        }}
        .original h3 {{ color: #e67e22; margin-bottom: 0.75rem; }}
        .draft {{
            background: #0f3460;
            border: 2px solid #27ae60;
            border-radius: 8px;
            padding: 1rem;
        }}
        .draft h3 {{ color: #27ae60; margin-bottom: 0.75rem; }}
        .msg {{
            border-bottom: 1px solid #333;
            padding: 0.5rem 0;
        }}
        .msg:last-child {{ border-bottom: none; }}
        .msg-from {{ font-weight: 600; color: #e0e0e0; }}
        .msg-date {{ color: #888; font-size: 0.8rem; }}
        .msg-body {{ color: #bbb; margin-top: 0.25rem; line-height: 1.5; }}
        .draft-text {{
            color: #a5d6a7;
            line-height: 1.6;
            white-space: pre-wrap;
        }}
        .footer {{
            text-align: center;
            margin-top: 2rem;
            padding: 1.5rem;
            background: #16213e;
            border-radius: 12px;
            color: #888;
        }}
        .footer strong {{ color: #e94560; }}
        @media (max-width: 768px) {{
            .grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <h1>📧 Proof of Human-in-the-Loop Review</h1>
    <div class="subtitle">
        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp;
        Total Approved Drafts: {len(approved)}
    </div>
    {cards_html}
    <div class="footer">
        🤖 Generated by <strong>The Draft Desk</strong> — AI Email Ghostwriter<br><br>
        Share with <strong>#MyChiefOfStaff</strong> to earn your Ghostwriter badge!
    </div>
</body>
</html>"""