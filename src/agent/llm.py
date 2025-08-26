# LLM interface to use different service
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


class LlmClient:
    def __init__(self, model_name: str = "gpt-4o",
                 base_url: str = "http://localhost:8000/v1",
                 api_key: str = "secret-key",
                 temperature: float = 0.0):
        self.model_name = model_name
        self.temperature = temperature
        self.base_url = base_url
        self.api_key = api_key
        self._client = ChatOpenAI(
            model_name=self.model_name,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=self.temperature
        )

    @property
    def client(self):
        return self._client

    def run(self, messages: list[dict[str, str] | tuple[str, str]]) -> str:
        try:
            return self.client.invoke(messages).content
        except Exception as e:
            raise e


if __name__ == "__main__":
    llm = LlmClient(
        model_name="openai/gpt-oss-20b",
        base_url="http://localhost:1234/v1",
    )
    content = llm.run([
        # {"role": "system", "content": "You are helpful assistant"},
        # {"role": "user", "content": "Hi"},
        ("system", "You are helpful assistant"),
        ("user", "Tell me a joke"),
    ])
    print(content, type(content))
