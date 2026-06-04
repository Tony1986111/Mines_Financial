import os
from langchain_openai import ChatOpenAI

llm_large = ChatOpenAI(
    model="deepseek-chat",
    max_tokens=5000,
    base_url="https://api.deepseek.com",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    temperature=0,
)
