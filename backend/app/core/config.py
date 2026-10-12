"""应用配置：从环境变量/.env 读取配置"""
from functools import lru_cache
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    # 数据库（统一使用 SQL Server）
    DB_HOST: str = "192.168.1.112"
    DB_PORT: int = 1433
    DB_NAME: str = "KELKCalCv"
    DB_USER: str = "Sa"
    DB_PASSWORD: str = "QraLBZngRU0PipBmIun4"

    # 应用
    APP_NAME: str = "KELKCalCv调节阀Cv计算与噪音分析系统"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # 安全
    SECRET_KEY: str = "kelk-calcv-secret-change-in-production-2026"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @property
    def database_url(self) -> str:
        # SQLAlchemy + pyodbc 连接串（统一使用 SQL Server）
        return (
            f"mssql+pyodbc://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST},{self.DB_PORT}/{self.DB_NAME}"
            f"?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
        )

    @property
    def database_url_odbc(self) -> str:
        # 原生 pyodbc 连接串，用于初始化建库
        return (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={self.DB_HOST},{self.DB_PORT};"
            f"DATABASE={self.DB_NAME};"
            f"UID={self.DB_USER};PWD={self.DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
