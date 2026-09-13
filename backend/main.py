
from fastapi import FastAPI

app = FastAPI()

churches = [
    {
        "id":1,
        "name":"Источник",
        "leader":"Алексей Смирнов",
        "district":"Устиновский район"
    }
]

@app.get("/")
def home():
    return {"status":"Home Church API"}

@app.get("/churches")
def get_churches():
    return churches
