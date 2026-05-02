from pydantic_settings import BaseSettings
from pydantic import computed_field

class SettingsBack(BaseSettings):
    openai_api_key: str

    proxy_base_url: str = "https://openai.api.proxyapi.ru/v1"
    default_model: str = "gpt_5.4_nano"
    max_file_size_mb: int = 10
    max_history_messages: int = 4
    host: str = "0.0.0.0"
    port: int = 8000

    @computed_field
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    model_config = {"env_file": ".env"}

class SettingsFront(BaseSettings):
    api_url: str = "http://localhost:8000/chat"
    connection_timeout: int = 5 #seconds
    read_timeout: int = 120 #seconds
