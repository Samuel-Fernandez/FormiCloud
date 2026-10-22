from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import calendar, entries, export

app = FastAPI(title="Formibudget")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(calendar.router)
app.include_router(entries.router)
app.include_router(export.router)


@app.on_event("startup")
def on_startup():
    init_db()
