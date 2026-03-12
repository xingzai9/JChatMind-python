"""邮件发送工具"""
import logging
import smtplib
from email.message import EmailMessage

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailSendInput(BaseModel):
    """发送邮件输入参数"""

    to_email: str = Field(..., description="收件人邮箱")
    subject: str = Field(..., description="邮件主题")
    body: str = Field(..., description="邮件正文")


class EmailTool(BaseTool):
    """发送邮件工具"""

    name: str = "email_sender"
    description: str = (
        "发送邮件给指定收件人。输入 to_email、subject、body。"
        "仅在系统已配置 SMTP 参数时可用。"
    )
    args_schema: type[BaseModel] = EmailSendInput

    def _run(self, to_email: str, subject: str, body: str) -> str:
        smtp_host = settings.smtp_host
        smtp_port = settings.smtp_port
        smtp_username = settings.smtp_username
        smtp_password = settings.smtp_password

        if not smtp_host or not smtp_username or not smtp_password:
            return "SMTP 未完整配置，无法发送邮件。请检查 smtp_host/smtp_username/smtp_password。"

        message = EmailMessage()
        message["From"] = smtp_username
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        try:
            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
                    server.login(smtp_username, smtp_password)
                    server.send_message(message)
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(smtp_username, smtp_password)
                    server.send_message(message)

            logger.info("邮件发送成功: to=%s, subject=%s", to_email, subject)
            return f"邮件发送成功：已发送至 {to_email}，主题「{subject}」。"
        except Exception as exc:
            logger.error("邮件发送失败: %s", exc, exc_info=True)
            return f"邮件发送失败：{exc}"

    async def _arun(self, to_email: str, subject: str, body: str) -> str:
        return self._run(to_email=to_email, subject=subject, body=body)
