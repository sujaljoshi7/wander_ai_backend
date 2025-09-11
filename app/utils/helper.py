from datetime import datetime, timedelta, timezone
import random
from app.database.db import get_db
from fastapi import Security, status, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import time
from jose import jwt
from passlib.context import CryptContext
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Union, Type, TypeVar, Optional, Generic
from pydantic import BaseModel, ValidationError
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import re 
from urllib.parse import urlparse
import os
from functools import wraps

security = HTTPBearer()

T = TypeVar("T")
# class CommonResponse(GenericModel, Generic[T]):
#     result: Optional[T] = None
#     id: int = 0
#     role_id: int = 0
#     is_success: bool = True
#     message: str = "Success"
#     status_code: Optional[int] = None

#     @classmethod
#     def response_handler(cls, result: T = None, id: int = 0, role_id: int = 0,
#                          is_success: bool = True, message: str = "Success",
#                          status_code: int = None) -> "CommonResponse[T]":
#         return cls(
#             result=result,
#             id=id,
#             role_id=role_id,
#             is_success=is_success,
#             message=message,
#             status_code=status_code
#         )

def safe_db_operation(module_name: str = "UnknownModule"):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            db = kwargs.get('db')
            try:
                return func(*args, **kwargs)
            except SQLAlchemyError as e:
                if db:
                    db.rollback()
                error_msg = f"[{module_name}] SQLAlchemy Error: {str(e)}"
                return CommonResponse.response_handler(
                    result=None,
                    message=f"Database error occurred: {str(e)}",
                    is_success=False,
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            except Exception as e:
                if db:
                    db.rollback()
                error_msg = f"[{module_name}] Unhandled Exception: {str(e)}"
                return CommonResponse.response_handler(
                    result=None,
                    message=f"Something went wrong: {str(e)}",
                    is_success=False,
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return wrapper
    return decorator

def format_best_time_of_day(time_ranges: list[list[str]]) -> list[str]:
    """
    Convert [['17:00', '19:00'], ['22:00', '23:00']] to ['17:00-19:00', '22:00-23:00']
    """
    formatted = []
    for tr in time_ranges:
        if isinstance(tr, list) and len(tr) == 2:
            formatted.append(f"{tr[0]}-{tr[1]}")
        elif isinstance(tr, str):
            formatted.append(tr)
        else:
            # fallback for unexpected format
            formatted.append(str(tr))
    return formatted


class CommonResponse(BaseModel, Generic[T]):
    # result: Optional[T] = None
    # id: int = 0
    # role_id: int = 0
    result: Optional[T] = None
    id: Optional[int] = None
    role_id: Optional[int] = None
    is_success: bool = False
    error: Optional[str] = None
    # message: str = "Success"
    message: str
    # status_code: Optional[int] = None
    status_code: int
    pagination: Optional[dict] = None
    token: Optional[str] = None

    @classmethod
    def response_handler(
        cls,
        result: T = None,
        # id: int = 0,
        # role_id: int = 0,
        id = None,
        role_id = None,
        is_success = False,
        error = None,
        message: str = "Success",
        status_code = 200 ,
        pagination: dict = None,
        token : str = None,
    ) -> "CommonResponse[T]":
        return cls(
            result=result,
            id=id,
            role_id=role_id,
            is_success=is_success,
            error=error,
            # discount_value = discount_value,
            # is_percentage = is_percentage,
            # type_id = type_id,
            # type_name = type_name,
            message=message,
            status_code=status_code,
            pagination=pagination,
            token=token,
        )
    
    class Config:
        from_attributes = True 

import subprocess, math, json, httpx
from decimal import Decimal
from app.api.itineraries.models import ItineraryRequest, ItineraryCandidate, ItineraryResult, ItineraryModelIO
from sqlalchemy import MetaData, create_engine

def query_llama(prompt: str, model: str = "llama3.1:8b") -> str:
    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt.encode("utf-8"),
        capture_output=True
    )
    return result.stdout.decode("utf-8").strip()

# --- Config toggles ---
URBAN_SPEED_KMH = 25
INTERCITY_SPEED_KMH = 55
HOP_BUFFER_MIN = 12
DAY_BUDGET_MIN = 8 * 60
END_OF_DAY_BUFFER_MIN = 30
OUT_OF_CITY_ONE_WAY_KM_MAX = 220
TARGET_ITEMS_PER_DAY = 3
MAX_ITEMS_PER_DAY = 5
MAX_AI_CANDIDATES = 42
EARTH_KM = 6371.0




DAY_START_HOUR = 10
DAY_END_HOUR = 19  # Let's assume 7 pm end time for visits
DAY_MAX_MINUTES = (DAY_END_HOUR - DAY_START_HOUR) * 60
END_BUFFER_MIN = 30
OUTER_BOUNDARY_KM = 220
TARGET_VISITS_PER_DAY = 3
MAX_VISITS_PER_DAY = 5
MAX_CANDIDATES = 42
EARTH_RADIUS_KM = 6371



DAILY_AVAILABLE_MINS = (DAY_END_HOUR - DAY_START_HOUR) * 60
TRAVEL_BUFFER_MIN = 12





OLLAMA_URL = "http://localhost:11434"
LLM_MODEL = "llama3.1:8b"

metadata = MetaData()
engine = create_engine(os.getenv("DATABASE_URL"), future=True)

def persist_itinerary(
    db: Session,
    city: str,
    days: int,
    suitable_for_norm: str,
    version: str,
    candidate_snapshot: list[dict],
    itinerary_obj: dict,
    auto_params_obj: dict,
    model_io_records: list[dict] | None = None
) -> int:
    req = ItineraryRequest(city=city, days=days, suitable_for=suitable_for_norm or None, version=version)
    db.add(req)
    db.flush()  # get req.id

    # Candidates snapshot (use your actual selected pools at the moment of planning)
    cand_rows = [
        ItineraryCandidate(
            itinerary_request_id= 0,
            place_id=c["place_id"], name=c["name"], lat=c["lat"], lng=c["lng"],
            avg_visit_mins=int(c["avg_visit_mins"]),
            rating=float(c.get("rating") or 0.0),
            distance_from_city_km=float(c.get("distance_from_city_km") or 0.0),
            city=c.get("city") or None
        )
        for c in candidate_snapshot
    ]
    if cand_rows:
        db.add_all(cand_rows)

    # After req is created and you have model_io_records: List[dict]
    # if model_io_records:
    #     io_rows = [
    #         ItineraryModelIO(
    #             itinerary_request_id=req.id,
    #             stage=rec.get("stage", "llm_generate"),
    #             prompt_text=rec.get("prompt_text", {"text": ""}),
    #             raw_response_text=rec.get("raw_response_text", {"text": ""})
    #         )
    #         for rec in model_io_records
    #     ]
    #     db.add_all(io_rows)


    res = ItineraryResult(
        itinerary_request_id=req.id,
        itinerary_json=itinerary_obj,
        auto_params_json=auto_params_obj
    )
    db.add(res)
    db.commit()
    return req.id

def haversine_km(lat1, lon1, lat2, lon2):
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat/2)**2 + math.cos(rlat1)*math.cos(rlat2)*math.sin(dlon/2)**2
    a = min(1.0, max(0.0, a))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_KM * c  # [5]

def safe_val(v):
    if isinstance(v, Decimal):
        return float(v)
    return v

def ai_fill_with_llama(
    city: str,
    residual_minutes: int,
    start_lat: float,
    start_lng: float,
    candidates: list[dict],
    max_additional: int,
    already_ids: set,
    model_io_collector: list | None = None
) -> list[dict]:
    # Shortlist for prompt
    pool = [c for c in candidates if c["place_id"] not in already_ids]
    pool = sorted(pool, key=lambda c: (c.get("distance_from_city_km", 1e9), -float(c.get("rating") or 0.0)))[:30]

    prompt = f"""
You are a professional travel planner.

Task: Select up to {max_additional} additional places that fit into the remaining time for the current day.
Return STRICT JSON ONLY as a list of objects:
[{{"place_id":"...", "reason":"..."}}, ...]
No markdown, no extra text.

Context:
- City: {city}
- Residual minutes available: {residual_minutes}
- Start lat/lng: {start_lat}, {start_lng}

Candidates:
{json.dumps([
    {
        "place_id": c["place_id"], "name": c["name"],
        "lat": c["lat"], "lng": c["lng"],
        "visit_minutes": c["avg_visit_mins"],
        "rating": c.get("rating", 0.0),
        "distance_from_city_km": c.get("distance_from_city_km", 0.0),
        "city": c.get("city", "")
    } for c in pool
], ensure_ascii=False)}
"""
    raw = query_llama_local(prompt)
    if model_io_collector is not None:
        model_io_collector.append({
            "stage": "ai_finisher",
            "prompt_text": {"text": prompt},
            "raw_response_text": {"text": raw}
        })
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []

def parse_mins(v, default=90):
    try:
        if v is None:
            return default
        return int(v)
    except:
        return default

def auto_radius_km(days: int) -> int:
    if days <= 1: return 25
    if days == 2: return 60
    if days == 3: return 120
    if days == 4: return 160
    return 220

def text_blob(x: dict) -> str:
    """
    Build a lowercase searchable blob from tags + description.
    - tags may be str, list, set, or None
    - description may be str or None
    """
    tags = x.get("tags")
    desc = x.get("description")
    parts = []

    # Handle tags flexibly
    if tags is None:
        pass
    elif isinstance(tags, str):
        parts.append(tags)
    elif isinstance(tags, (list, set, tuple)):
        try:
            parts.append(" ".join(map(str, tags)))
        except Exception:
            # Fallback to str() if elements are not straightforward
            parts.append(str(tags))
    else:
        # Unknown type, fallback
        parts.append(str(tags))

    # Handle description
    if isinstance(desc, str):
        parts.append(desc)
    elif desc is not None:
        parts.append(str(desc))

    return " ".join(parts).lower()

AUDIENCE_TERMS = {
    "families": ["family", "kids", "children", "park", "zoo", "aquarium", "science",
                 "planetarium", "garden", "lake", "toy", "museum", "heritage walk",
                 "play area", "rail", "train"],
    "group": ["group", "adventure", "market", "street", "fort", "museum", "festival"],
    "couple": ["couple", "romantic", "sunset", "riverfront", "lake", "cafe", "heritage", "temple"],
    "solo": ["solo", "walk", "photography", "heritage", "museum", "market", "temple"],
    "seniors": ["seniors", "easy", "garden", "temple", "museum", "ashram", "memorial"]
}
def travel_minutes_est(km: float, urban: bool) -> int:
    speed_kmh = URBAN_SPEED_KMH if urban else INTERCITY_SPEED_KMH
    minutes = (km / max(1e-6, speed_kmh)) * 60.0
    return int(round(minutes))

def hop_time_from_city_minutes(poi: dict, city_lat: float, city_lon: float) -> int:
    return hop_time_minutes(city_lat, city_lon, poi["lat"], poi["lng"], city_lat, city_lon)

def hop_time_minutes(lat1, lon1, lat2, lon2, city_lat, city_lon):
    km = haversine_km(lat1, lon1, lat2, lon2)
    city_to_a = haversine_km(city_lat, city_lon, lat1, lon1)
    city_to_b = haversine_km(city_lat, city_lon, lat2, lon2)
    near_city = (city_to_a < 20) and (city_to_b < 20)
    base = travel_minutes_est(km, urban=near_city)
    return base + HOP_BUFFER_MIN

def round_trip_minutes(poi: dict, city_lat: float, city_lon: float) -> int:
    go = hop_time_minutes(city_lat, city_lon, poi["lat"], poi["lng"], city_lat, city_lon)
    back = hop_time_minutes(poi["lat"], poi["lng"], city_lat, city_lon, city_lat, city_lon)
    return go + poi["avg_visit_mins"] + back

def parse_time(tstr):
    return datetime.strptime(tstr, "%H:%M").time()

def is_within_open_hours(current_time: datetime, open_time: time, close_time: time) -> bool:
    ct = current_time.time()
    return open_time <= ct <= close_time

def adjust_start_time_for_opening(current_time: datetime, opening_hours: dict) -> datetime:
    # Flatten all opening intervals
    intervals = [(parse_time(v['open']), parse_time(v['close'])) for v in opening_hours.values()]
    ct = current_time.time()
    for open_time, close_time in intervals:
        if ct < open_time:
            # Need to wait until open_time
            new_time = current_time.replace(hour=open_time.hour, minute=open_time.minute, second=0, microsecond=0)
            return new_time
        elif open_time <= ct <= close_time:
            return current_time  # already during open hours
    # After all intervals, schedule to next day opening (optional future logic)
    return current_time  # fallback: keep same time

# =========================
# Local LLM bridge (replace)
# =========================
def query_llama_local(prompt: str, max_tokens: int = 1024, temperature: float = 0.4) -> str:
    """
    Implement using ollama/llama.cpp. If available, enforce JSON schema with a grammar/Outlines.
    Return raw JSON string from the model.
    """
    # TODO: integrate your local runtime here.
    return '{"itinerary": {}}'

def query_llama_structured(itin_schema: dict, prompt: str, model: str = LLM_MODEL, base_url: str = OLLAMA_URL) -> str:
    """
    Prefer Ollama REST /api/chat with format schema if supported.
    Returns model content (expected JSON).
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": itin_schema  # structured outputs if available
    }
    with httpx.Client(timeout=120) as client:
        r = client.post(f"{base_url}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()
        return data["message"]["content"].strip()

def query_llama_subprocess(prompt: str, model: str = LLM_MODEL) -> str:
    p = subprocess.Popen(
        ["ollama", "run", model],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,                  # Text mode
        encoding="utf-8",           # Explicitly set UTF-8 decoding
        errors="replace"            # Replace undecodable bytes rather than error
    )
    out, err = p.communicate(input=prompt)
    return (out or "").strip()

def get_llm_itinerary_or_none(prompt: str, schema_hint: dict) -> Optional[dict]:
    # 1) try REST structured
    try:
        raw = query_llama_structured(schema_hint, prompt, model=LLM_MODEL, base_url=OLLAMA_URL)
        parsed = json.loads(raw)
        iti = parsed.get("itinerary", {})
        if isinstance(iti, dict) and iti:
            return iti
    except Exception:
        pass
    # 2) try subprocess with same prompt
    try:
        raw = query_llama_subprocess(prompt, model=LLM_MODEL)
        parsed = json.loads(raw)
        iti = parsed.get("itinerary", {})
        if isinstance(iti, dict) and iti:
            return iti
    except Exception:
        pass
    return None

def format_itinerary(itinerary_json, candidates_map, city, days):
    output = []
    time_slot_defs = [
        ("Morning", 8, 12),    # 8 AM to 12 PM
        ("Afternoon", 12, 17),  # 12 PM to 5 PM
        ("Evening", 17, 20),    # 5 PM to 8 PM
        ("Night", 20, 23),      # 8 PM to 11 PM (optional)
    ]
    daily_start = 8  # assume day starts at 8 AM for visits

    for day_num in range(1, days + 1):
        day_key = f"Day {day_num}"
        output.append(f"Day {day_num} itinerary for {city}\n")

        visits = itinerary_json.get(day_key, [])
        if not visits:
            output.append("No visits planned.\n\n")
            continue

        current_time = datetime.combine(datetime.today(), datetime.min.time()) + timedelta(hours=daily_start)

        # Distribute visits across defined time slots roughly evenly
        visits_per_slot = max(1, len(visits) // len(time_slot_defs))

        visit_idx = 0
        for slot_name, slot_start, slot_end in time_slot_defs:
            slot_visits = visits[visit_idx:visit_idx+visits_per_slot]
            if not slot_visits:
                continue
            output.append(f"{slot_name}:\n")
            slot_time = datetime.combine(datetime.today(), datetime.min.time()) + timedelta(hours=slot_start)

            for visit in slot_visits:
                pid = visit['place_id']
                place = candidates_map.get(pid)
                if not place:
                    continue
                start_str = slot_time.strftime("%I:%M %p")
                duration = place['visit_mins']
                end_time = slot_time + timedelta(minutes=duration)
                end_str = end_time.strftime("%I:%M %p")

                activities = visit.get("activities", "Visit")
                description = place.get("description", "No description available.")

                output.append(f"{start_str} - {end_str}: {place['name']}\n")
                output.append(f"{activities}\n")
                output.append(f"{description}\n\n")

                slot_time = end_time + timedelta(minutes=15)  # 15 min break after visit

            visit_idx += visits_per_slot

        output.append("\n")

    return "\n".join(output)

