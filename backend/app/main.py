from fastapi import FastAPI

app = FastAPI(title="OSS Copilot")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
