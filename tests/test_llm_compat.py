from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_import_from_package_ask_llm():
    from Tool.llm.client import ask_llm

    assert callable(ask_llm)


def test_import_from_package_llm_tool():
    from Tool.llm.client import LLMTool

    assert LLMTool is not None


def test_import_from_package_ask_llm_gpt5():
    from Tool.llm.client import ask_llm_gpt5

    assert callable(ask_llm_gpt5)


def test_llm_tool_finds_default_config():
    from Tool.llm.client import LLMTool

    tool = LLMTool()
    assert tool.config is not None
    assert tool.config.provider in ("azure_openai", "openai_compatible")
    assert tool.config.api_key
    assert tool.config.endpoint


def test_ask_llm_gpt5_missing_config_raises():
    from Tool.llm.client import ask_llm_gpt5

    with pytest.raises(FileNotFoundError, match="GPT-5 config not found"):
        ask_llm_gpt5("test question", config_path="config/azure_gpt5_config_nonexistent.json")


def test_llm_tool_custom_config_path(tmp_dir, sample_config_file):
    from Tool.llm.client import LLMTool

    tool = LLMTool(str(sample_config_file))
    assert tool.config.api_key == "test-key-12345"
    assert tool.config.endpoint == "https://test-endpoint.example.com"


def test_llm_tool_ask_sends_request(sample_config_file):
    from Tool.llm.client import LLMTool

    tool = LLMTool(str(sample_config_file))

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "测试回复"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("Tool.llm.client.requests.post", return_value=mock_response) as mock_post:
        result = tool.ask("测试问题")
        assert result == "测试回复"
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        assert "messages" in payload
        assert "temperature" in payload
        assert "top_p" in payload


@pytest.mark.parametrize("deployment", ["gpt-5", "gpt-5.5"])
def test_gpt5_series_omits_sampling_controls(tmp_path, deployment):
    from Tool.llm.client import LLMTool

    config_path = tmp_path / f"azure_{deployment.replace('.', '_')}_config.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": "azure_openai",
                "azure_api_key": "test-key",
                "azure_endpoint": "https://test-endpoint.example.com",
                "azure_deployment": deployment,
                "model": deployment,
                "api_version": "2024-02-01",
                "max_tokens": 100,
                "temperature": 0.2,
            }
        ),
        encoding="utf-8",
    )
    tool = LLMTool(str(config_path))

    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "OK"}}]}
    mock_response.raise_for_status = MagicMock()

    with patch("Tool.llm.client.requests.post", return_value=mock_response) as mock_post:
        result = tool.ask("测试问题", temperature=0.2, top_p=0.6)

    payload = mock_post.call_args.kwargs["json"]
    assert result == "OK"
    assert "temperature" not in payload
    assert "top_p" not in payload
    assert payload["max_completion_tokens"] == 100


def test_ask_llm_uses_default_config():
    from Tool.llm.client import ask_llm

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "默认配置回复"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("Tool.llm.client.requests.post", return_value=mock_response):
        result = ask_llm("测试", max_tokens=100)
        assert result == "默认配置回复"
