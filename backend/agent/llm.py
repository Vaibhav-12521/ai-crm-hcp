from functools import lru_cache

from langchain_groq import ChatGroq

from config import settings


@lru_cache(maxsize=1)
def get_llm(temperature: float = 0.0) -> ChatGroq:
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=temperature,
        request_timeout=25,
        max_retries=1,
    )
