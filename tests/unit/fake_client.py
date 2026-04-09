
class FakeGeminiResponse:
    def __init__(self, text="", embeddings=None):
        self.text = text
        self.embeddings = embeddings or []


class FakeEmbedding:
    def __init__(self, values):
        self.values = values


class FakeModels:
    def __init__(self):
        self._errors = {}

    def set_error(self, method_name, exception):
        self._errors[method_name] = exception

    def clear_errors(self):
        self._errors = {}

    def embed_content(self, model, contents, config=None):
        if "embed_content" in self._errors:
            raise self._errors["embed_content"]
        if isinstance(contents, str):
            return FakeGeminiResponse(embeddings=[FakeEmbedding([0.1] * 768)])
        return FakeGeminiResponse(
            embeddings=[FakeEmbedding([0.1] * 768) for _ in contents]
        )

    def generate_content(self, model, contents, config=None):
        if "generate_content" in self._errors:
            raise self._errors["generate_content"]
        # Default behavior: No conflict
        return FakeGeminiResponse(text='{"conflict": false, "reason": "No conflict"}')


class FakeGeminiClient:
    def __init__(self, api_key="fake_key"):
        self.models = FakeModels()
