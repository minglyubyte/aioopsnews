from fastapi import FastAPI

app = FastAPI(title="AI Reality Check API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
