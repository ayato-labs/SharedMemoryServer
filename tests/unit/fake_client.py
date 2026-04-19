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
        self._responses = {}

    def set_response(self, method_name, text):
        self._responses[method_name] = text

    def set_error(self, method_name, exception):
        self._errors[method_name] = exception

    def clear_errors(self):
        self._errors = {}

    def embed_content(self, model, contents, config=None):
        if "embed_content" in self._errors:
            raise self._errors["embed_content"]

        def _get_val(txt):
            import hashlib

            # Deterministic but text-dependent value
            h = hashlib.md5(txt.encode()).hexdigest()
            # Spread values around 0.1 to avoid all-same-vector issues
            v = int(h[:4], 16) / 65535.0
            return [v] * 768

        if isinstance(contents, str):
            return FakeGeminiResponse(embeddings=[FakeEmbedding(_get_val(contents))])
        return FakeGeminiResponse(
            embeddings=[FakeEmbedding(_get_val(c)) for c in contents]
        )

    def generate_content(self, model, contents, config=None):
        if "generate_content" in self._errors:
            raise self._errors["generate_content"]
        if "generate_content" in self._responses:
            return FakeGeminiResponse(text=self._responses["generate_content"])
        # Default behavior: No conflict
        return FakeGeminiResponse(text='{"conflict": false, "reason": "No conflict"}')

    def list(self):
        return [type("Model", (), {"name": "models/gemini-2.0-flash-exp"})]


class FakeAsyncModels:
    def __init__(self, models: FakeModels):
        self.models = models

    async def list(self):
        return self.models.list()

    async def embed_content(self, **kwargs):
        # Delegate to sync version, it just does mathematical/mock logic
        return self.models.embed_content(**kwargs)

    async def generate_content(self, **kwargs):
        return self.models.generate_content(**kwargs)


class FakeGeminiClient:
    def __init__(self, api_key="fake_key"):
        self.models = FakeModels()
        self.aio = type("FakeAio", (), {"models": FakeAsyncModels(self.models)})
