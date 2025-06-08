from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    bot_token: str = ""
    admin_ids: str = "123456789,987654321"
    base_url: str = "https://api.mail.gw"
    
    @property
    def admin_ids_list(self) -> List[int]:
        """Преобразует строку admin_ids в список целых чисел"""
        return [int(id.strip()) for id in self.admin_ids.split(',') if id.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'


settings = Settings()
