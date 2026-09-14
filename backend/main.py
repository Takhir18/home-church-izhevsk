from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Домашние церкви Ижевска API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHURCHES = [
    {
        "id": 1,
        "name": "Источник",
        "leader": "Алексей Смирнов",
        "leader_username": "alex_source_test",
        "district": "Устиновский район",
        "address": "ул. Молодёжная, 45",
        "meeting_day": "Воскресенье",
        "meeting_time": "18:00",
        "age": "25–35 лет",
        "participants": 14,
        "description": "Тёплая открытая группа для общения, молитвы, изучения Библии и поддержки друг друга.",
        "interests": ["Общение", "Семьи", "Изучение Библии"],
        "latitude": 56.8468,
        "longitude": 53.2812,
    },
    {
        "id": 2,
        "name": "Надежда",
        "leader": "Иван Петров",
        "leader_username": "ivan_nadezhda_test",
        "district": "Октябрьский район",
        "address": "ул. Пушкинская, 210",
        "meeting_day": "Суббота",
        "meeting_time": "17:00",
        "age": "35–45 лет",
        "participants": 10,
        "description": "Спокойная семейная группа, где люди знакомятся, молятся вместе и поддерживают друг друга.",
        "interests": ["Семьи", "Общение", "Поддержка"],
        "latitude": 56.8654,
        "longitude": 53.2055,
    },
    {
        "id": 3,
        "name": "Живое сердце",
        "leader": "Мария Волкова",
        "leader_username": "maria_heart_test",
        "district": "Первомайский район",
        "address": "ул. Ленина, 98",
        "meeting_day": "Воскресенье",
        "meeting_time": "16:00",
        "age": "18–30 лет",
        "participants": 18,
        "description": "Активная группа для молодых людей, которые хотят дружить, расти духовно и служить вместе.",
        "interests": ["Молодёжь", "Творчество", "Поездки"],
        "latitude": 56.8421,
        "longitude": 53.2309,
    },
    {
        "id": 4,
        "name": "Свет",
        "leader": "Дмитрий Орлов",
        "leader_username": "dmitry_svet_test",
        "district": "Индустриальный район",
        "address": "Воткинское шоссе, 34",
        "meeting_day": "Среда",
        "meeting_time": "19:00",
        "age": "40+",
        "participants": 8,
        "description": "Небольшая группа для близкого общения, молитвы и совместного изучения Библии.",
        "interests": ["Общение", "Библия", "Помощь людям"],
        "latitude": 56.8840,
        "longitude": 53.2440,
    },
]

REQUESTS = []


class JoinRequest(BaseModel):
    church_id: int
    telegram_id: int
    name: str
    username: Optional[str] = None
    message: Optional[str] = None


@app.get("/")
def home():
    return {
        "status": "ok",
        "service": "Home Church API",
        "churches": len(CHURCHES),
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/churches")
def get_churches(
    district: Optional[str] = Query(default=None),
    age: Optional[str] = Query(default=None),
):
    result = CHURCHES
    if district:
        result = [c for c in result if c["district"] == district]
    if age:
        result = [c for c in result if c["age"] == age]
    return result


@app.get("/churches/{church_id}")
def get_church(church_id: int):
    church = next((c for c in CHURCHES if c["id"] == church_id), None)
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")
    return church


@app.post("/requests", status_code=201)
def create_request(payload: JoinRequest):
    church = next((c for c in CHURCHES if c["id"] == payload.church_id), None)
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")

    request = {
        "id": len(REQUESTS) + 1,
        **payload.model_dump(),
        "church_name": church["name"],
        "status": "new",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    REQUESTS.append(request)
    return request


@app.get("/requests")
def get_requests():
    return REQUESTS
