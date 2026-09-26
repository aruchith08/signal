"""
Telegram Message Formatter — Formats clean, markdown-safe opportunity alerts
"""
import re
from datetime import datetime
from typing import List, Optional


class TelegramMessageFormatter:
    """
    Formats opportunity notifications into clean, human-readable Telegram markdown.
    """

    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        Escapes Telegram Markdown special characters.
        """
        if not text:
            return ""
        # Characters needing escaping in standard Markdown mode: _ * ` [ ]
        # In MarkdownV2: _ * [ ] ( ) ~ ` > # + - = | { } . !
        # We will escape classic Markdown: _ * ` [
        return re.sub(r"([_*`\[])", r"\\\1", text)

    @classmethod
    def format_alert(
        cls,
        title: str,
        score: int,
        reasons: List[str],
        event_title: Optional[str] = None,
        event_type: Optional[str] = None,
        organization_name: Optional[str] = None,
        deadline: Optional[datetime] = None,
        application_url: Optional[str] = None,
        is_critical: bool = False,
    ) -> str:
        """Constructs an aesthetic, markdown-safe Telegram alert."""
        header_icon = "🚨" if is_critical or score >= 90 else "📡"
        header_text = "SIGNAL ALERT" if is_critical else "SIGNAL UPDATE"

        lines = [
            f"{header_icon} *{header_text}*",
            "",
            f"🔥 *{cls.escape_markdown(title)}*",
        ]

        if event_title:
            lines.append(f"📌 {cls.escape_markdown(event_title)}")
        elif event_type:
            friendly_event = event_type.replace("_", " ").title()
            lines.append(f"📌 {cls.escape_markdown(friendly_event)}")

        lines.extend([
            "",
            f"🎯 *Relevance:* {score}%",
            "",
            "*Why you're seeing this:*",
        ])

        # Bullet reasons (max 3)
        display_reasons = reasons[:3] if reasons else ["Matches your student opportunity preferences"]
        for r in display_reasons:
            lines.append(f"• {cls.escape_markdown(r)}")

        if deadline:
            formatted_date = deadline.strftime("%d %B %Y, %H:%M UTC")
            lines.extend([
                "",
                f"⏰ *Deadline:*\n{formatted_date}",
            ])

        if organization_name:
            lines.extend([
                "",
                f"🏢 *Organization:*\n{cls.escape_markdown(organization_name)}",
            ])

        if application_url:
            lines.extend([
                "",
                f"🔗 [Apply / Learn More]({application_url})",
            ])

        lines.extend([
            "",
            "📡 _SIGNAL Opportunity Network_",
        ])

        return "\n".join(lines)
