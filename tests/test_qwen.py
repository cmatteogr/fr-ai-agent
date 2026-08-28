import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["FR_AGENT_LLM_API_KEY"],
    base_url=os.environ["FR_AGENT_LLM_BASE_URL"],
)

response = client.chat.completions.create(
    model="qwen.qwen3-32b",  # Bedrock model IDs use dots, not slashes
    messages=[{"role": "user", "content": "Hello, how are you?"}],
)
print(response.choices[0].message.content)
