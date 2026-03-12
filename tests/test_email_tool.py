from unittest.mock import patch

from app.agents.tools.email_tool import EmailTool


@patch("app.agents.tools.email_tool.settings")
def test_email_tool_missing_smtp_config(mock_settings):
    mock_settings.smtp_host = None
    mock_settings.smtp_port = 587
    mock_settings.smtp_username = None
    mock_settings.smtp_password = None

    tool = EmailTool()
    result = tool._run("user@example.com", "测试主题", "测试正文")

    assert "SMTP 未完整配置" in result


@patch("app.agents.tools.email_tool.smtplib.SMTP")
@patch("app.agents.tools.email_tool.settings")
def test_email_tool_send_success_tls(mock_settings, mock_smtp):
    mock_settings.smtp_host = "smtp.example.com"
    mock_settings.smtp_port = 587
    mock_settings.smtp_username = "sender@example.com"
    mock_settings.smtp_password = "secret"

    tool = EmailTool()
    result = tool._run("to@example.com", "测试主题", "测试正文")

    assert "邮件发送成功" in result
    assert "to@example.com" in result
    mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=15)
