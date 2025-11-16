from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "現在の天気を取得する",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                },
                "required": ["city"],
            },
        },
    }
]

resp = client.chat.completions.create(
    model="llama3.1",   # tools対応モデルを使う
    messages=[{"role": "user", "content": "東京の天気教えて"}],
    tools=tools,
)

print(resp)
