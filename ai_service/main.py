from fastapi import FastAPI
from pydantic import BaseModel
from models import QueryRequest, QueryResponse, PriceResult, ErrorResult
from nlp import parse_query, chat_with_llm
from price_fetcher import get_price
import uvicorn

app = FastAPI(title="AI Oracle Service")


@app.post("/predict", response_model=QueryResponse)
async def predict(request: QueryRequest) -> QueryResponse:
    try:
        symbol = parse_query(request.query)
    except ValueError as e:
        return QueryResponse(result=ErrorResult(error=str(e), symbol=None), confidence=0.0)

    try:
        price_data = get_price(symbol)
    except ValueError as e:
        return QueryResponse(result=ErrorResult(error=str(e), symbol=symbol), confidence=0.0)
    except RuntimeError as e:
        return QueryResponse(result=ErrorResult(error=str(e), symbol=symbol), confidence=0.0)

    return QueryResponse(
        result=PriceResult(
            symbol=price_data["symbol"],
            price=price_data["price"],
            currency=price_data["currency"],
            sources=price_data["sources"],
            timestamp=price_data["timestamp"],
        ),
        confidence=price_data["confidence"],
    )


class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    reply = chat_with_llm(request.message)
    return ChatResponse(reply=reply or "Sorry, I couldn't generate a response.")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
