from settings import SettingsBack
from langchain_openai import ChatOpenAI

settings = SettingsBack()

MODEL_CONFIGS = {
    "gpt_5.4_nano":      {"model": "openai/gpt-5.4-nano"},
    "gpt_5.4_mini":      {"model": "openai/gpt-5.4-mini"},
    "claude_sonnet_4.6": {"model": "anthropic/claude-sonnet-4-6"},
    "claude_opus_4.6":   {"model": "anthropic/claude-opus-4-6"}
}

available_models = {
    name: ChatOpenAI(temperature=0, base_url=settings.proxy_base_url, **cfg)
    for name, cfg in MODEL_CONFIGS.items()
}

prompts = {
    "system_prompt": (
            "Ты полезный AI-ассистент. "
            "Отвечай дружелюбно, понятно и по делу. "
            "Используй историю диалога при ответе."
            )
}