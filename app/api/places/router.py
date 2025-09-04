from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from datetime import datetime
from app.database.db import get_db
from app.api.places.models import Places, ItineraryRequest, ItineraryCandidate, ItineraryResult, ItineraryModelIO
from typing import List, Optional, Dict, Any
from app.utils.embeddings import get_embedding
import subprocess
from sqlalchemy import text, func, Table, MetaData, create_engine
import json, math, httpx, subprocess
from decimal import Decimal
from app.api.places.schema import WEEKDAYS, EntryFee, Accessibility, PlaceCreate
import os

router = APIRouter(prefix="/places", tags=["Places"])

# EARTH_KM = 6371.0
metadata = MetaData()
engine = create_engine(os.getenv("DATABASE_URL"), future=True)

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

OLLAMA_URL = "http://localhost:11434"
LLM_MODEL = "llama3.1:8b"

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
            itinerary_request_id=req.id,
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
    """
    Fallback using subprocess. Uses communicate() to avoid deadlocks.
    """
    p = subprocess.Popen(
        ["ollama", "run", model],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
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


def generate_place_id(db: Session) -> str:
    last_place = db.query(Places).order_by(Places.id.desc()).first()
    if not last_place or not last_place.place_id:
        return "P_00001"
    last_num = int(last_place.place_id.split("_")[1])
    return f"P_{last_num+1:05d}"


@router.post("/create")
def create_place(place_req: dict, db: Session = Depends(get_db)):
    """
    Accept JSON, ignore provided id, auto-generate place_id,
    prevent duplicate entries, and store embeddings.
    """

    # --- Required defaults ---
    for f in ["name", "city", "state", "country"]:
        if f not in place_req or not str(place_req[f]).strip():
            raise HTTPException(status_code=400, detail=f"Missing required field: {f}")

    name = place_req["name"].strip()
    city = place_req["city"].strip()
    state = place_req["state"].strip()
    country = place_req["country"].strip()

    # --- Duplicate check ---
    existing_place = (
        db.query(Places)
        .filter(
            Places.name.ilike(name),
            Places.city.ilike(city),
            Places.state.ilike(state),
            Places.country.ilike(country),
        )
        .first()
    )
    if existing_place:
        return {"message": "Entry already exists", "place_id": existing_place.place_id}

    # --- Generate new place_id ---
    place_id = generate_place_id(db)

    # --- Filter valid DB columns ---
    valid_columns = {c.name for c in Places.__table__.columns}
    filtered_data = {}
    extras = {}

    for key, value in place_req.items():
        if key == "id":  # ignore incoming id
            continue
        if key in valid_columns:
            filtered_data[key] = value
        else:
            extras[key] = value

    # --- Add system-generated fields ---
    filtered_data["place_id"] = place_id
    filtered_data["extras"] = extras
    if "last_verified" not in filtered_data:
        filtered_data["last_verified"] = datetime.now().date()

    # --- Generate embedding ---
    embedding_text = " ".join([
        filtered_data.get("name", ""),
        filtered_data.get("city", ""),
        filtered_data.get("state", ""),
        filtered_data.get("country", ""),
        filtered_data.get("description", "")
    ])
    filtered_data["embedding"] = get_embedding(embedding_text)

    # --- Save to DB ---
    place_obj = Places(**filtered_data)
    db.add(place_obj)
    db.commit()
    db.refresh(place_obj)

    return {"message": "Place data inserted successfully", "place_id": place_id}



WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

@router.post("/create1", status_code=status.HTTP_201_CREATED)
def create_place(place_req: PlaceCreate, db: Session = Depends(get_db)):
    """
    Accept JSON, ignore provided id, auto-generate place_id,
    prevent duplicate entries, and store embeddings.
    """

    # Deduplication check
    name = place_req.name.strip()
    city = place_req.city.strip()
    state = place_req.state.strip()
    country = place_req.country.strip()

    existing_place = (
        db.query(Places)
        .filter(
            func.lower(func.trim(Places.name)) == func.lower(name),
            func.lower(func.trim(Places.city)) == func.lower(city),
            func.lower(func.trim(Places.state)) == func.lower(state),
            func.lower(func.trim(Places.country)) == func.lower(country),
        )
        .first()
    )
    if existing_place:
        return {
            "message": "Entry already exists",
            "place_id": existing_place.place_id
        }

    # Generate new place_id
    place_id = generate_place_id(db)

    # Convert Pydantic model → dict
    src: Dict[str, Any] = place_req.dict(exclude_unset=False)

    # Extract valid DB columns
    valid_columns = {c.name for c in Places.__table__.columns}
    filtered_data: Dict[str, Any] = {}
    extras: Dict[str, Any] = {}

    def ensure_list(val):
        return val if isinstance(val, list) else []

    # Separate known vs unknown keys
    for key, value in src.items():
        if key in ["id", "place_id"]:
            continue
        if key in valid_columns:
            filtered_data[key] = value
        else:
            extras[key] = value
# Merge: if request already had "extras", combine it with new extras
    req_extras = src.get("extras", {})
    if req_extras and isinstance(req_extras, dict):
        extras.update(req_extras)
    # Defaults
    filtered_data.setdefault("avg_visit_mins", 60)
    # Save into filtered_data
    filtered_data["extras"] = extras

    # Open hours
    if place_req.open_hours:
        filtered_data["open_hours"] = dict(place_req.open_hours.dict())
    else:
        filtered_data["open_hours"] = {d: [] for d in WEEKDAYS}

    # Arrays
    filtered_data["tags"] = ensure_list(filtered_data.get("tags") or [])
    filtered_data["suitable_for"] = ensure_list(filtered_data.get("suitable_for") or [])
    filtered_data["famous_for"] = ensure_list(filtered_data.get("famous_for") or [])
    filtered_data["best_months"] = ensure_list(filtered_data.get("best_months") or [])
    filtered_data["nearby_attractions"] = ensure_list(filtered_data.get("nearby_attractions") or [])

    # JSONB fields
    filtered_data["entry_fee"] = dict(place_req.entry_fee.dict()) if place_req.entry_fee else {}
    filtered_data["accessibility"] = dict(place_req.accessibility.dict()) if place_req.accessibility else {}

    # Explicit lat/lng/rating cast
    filtered_data["lat"] = float(src["lat"]) if src.get("lat") is not None else None
    filtered_data["lng"] = float(src["lng"]) if src.get("lng") is not None else None
    filtered_data["rating"] = float(src["rating"]) if src.get("rating") is not None else None

    # System fields
    filtered_data["place_id"] = place_id
    # filtered_data["extras"] = extras
    filtered_data["last_verified"] = filtered_data.get("last_verified") or datetime.utcnow().date()

    # Embedding text
    embedding_text = " ".join([
        filtered_data.get("name", ""),
        filtered_data.get("city", ""),
        filtered_data.get("state", ""),
        filtered_data.get("country", ""),
        filtered_data.get("description", "")
    ]).strip()

    # Embedding generation
    embedding_vec = None
    try:
        embedding_vec = get_embedding(embedding_text) if embedding_text else None
        if embedding_vec is not None and len(embedding_vec) != 384:
            raise ValueError("Embedding dimension mismatch; expected 384")
    except Exception:
        embedding_vec = None

    filtered_data["embedding"] = embedding_vec

    # Persist
    place_obj = Places(**filtered_data)
    db.add(place_obj)
    try:
        db.commit()
    except Exception:
        db.rollback()
        existing_place = (
            db.query(Places)
            .filter(
                func.lower(func.trim(Places.name)) == func.lower(name),
                func.lower(func.trim(Places.city)) == func.lower(city),
                func.lower(func.trim(Places.state)) == func.lower(state),
                func.lower(func.trim(Places.country)) == func.lower(country),
            )
            .first()
        )
        if existing_place:
            return {"message": "Entry already exists", "place_id": existing_place.place_id}
        raise HTTPException(status_code=500, detail="Database error")

    db.refresh(place_obj)
    return {"message": "Place data inserted successfully", "place_id": place_id}

@router.post("/bulk_create")
def bulk_create_places(places_req: List[dict], db: Session = Depends(get_db)):
    """
    Accept a list of JSON objects, prevent duplicates,
    insert unique places with auto-generated IDs,
    and generate embeddings for each.
    """

    if not places_req:
        raise HTTPException(status_code=400, detail="No data provided")

    inserted = []
    skipped = []

    # --- Get last place_id once ---
    last_place = db.query(Places).order_by(Places.id.desc()).first()
    if not last_place or not last_place.place_id:
        next_id_num = 1
    else:
        next_id_num = int(last_place.place_id.split("_")[1]) + 1

    for place_req in places_req:
        # --- Required defaults ---
        for f in ["name", "city", "state", "country"]:
            if f not in place_req or not str(place_req[f]).strip():
                skipped.append({"data": place_req, "reason": f"Missing required field: {f}"})
                break
        else:  # only if all required fields are present
            name = place_req["name"].strip()
            city = place_req["city"].strip()
            state = place_req["state"].strip()
            country = place_req["country"].strip()

            # --- Duplicate check ---
            existing_place = (
                db.query(Places)
                .filter(
                    Places.name.ilike(name),
                    Places.city.ilike(city),
                    Places.state.ilike(state),
                    Places.country.ilike(country),
                )
                .first()
            )
            if existing_place:
                skipped.append({
                    "data": place_req,
                    "reason": "Entry already exists",
                    "existing_place_id": existing_place.place_id,
                })
                continue

            # --- Assign unique place_id ---
            place_id = f"P_{next_id_num:05d}"
            next_id_num += 1

            # --- Filter valid DB columns ---
            valid_columns = {c.name for c in Places.__table__.columns}
            filtered_data = {}
            extras = {}

            for key, value in place_req.items():
                if key == "id":  # ignore incoming id
                    continue
                if key in valid_columns:
                    filtered_data[key] = value
                else:
                    extras[key] = value

            # --- Add system-generated fields ---
            filtered_data["place_id"] = place_id
            filtered_data["extras"] = extras
            if "last_verified" not in filtered_data:
                filtered_data["last_verified"] = datetime.now().date()

            # --- Generate embedding (use text representation for consistency) ---
            embedding_text = f"{name}, {city}, {state}, {country}, {extras}"
            filtered_data["embedding"] = get_embedding(embedding_text)

            # --- Save to DB session ---
            place_obj = Places(**filtered_data)
            db.add(place_obj)
            inserted.append({"place_id": place_id, "name": name, "city": city})

    db.commit()

    return {
        "inserted_count": len(inserted),
        "skipped_count": len(skipped),
        "inserted": inserted,
        "skipped": skipped,
    }


@router.post("/generate_itinerary")
def generate_itinerary(
    city: str,
    days: int,
    suitable_for: str,
    trip_type: Optional[str] = None,
    radius_km: int = 100,  # search radius in km
    db: Session = Depends(get_db)
):
    """
    Generate a day-wise itinerary using AI based on DB places + nearby places.
    """

    # -------------------------
    # 1. Get city lat/lon from DB
    # -------------------------
    city_obj = db.query(Places).filter(Places.city.ilike(city)).first()
    if not city_obj or not city_obj.lat or not city_obj.lng:
        raise HTTPException(status_code=404, detail=f"No coordinates found for city {city}")

    city_lat = float(city_obj.lat)
    city_lon = float(city_obj.lng)

    # -------------------------
    # 2. Fetch candidate places within radius
    # -------------------------
    haversine_sql = text("""
    SELECT *,
           (6371 * acos(
                cos(radians(:lat)) * cos(radians(lat)) *
                cos(radians(lng) - radians(:lon)) +
                sin(radians(:lat)) * sin(radians(lat))
           )) AS distance_km
    FROM places
    WHERE lat IS NOT NULL AND lng IS NOT NULL
      AND (6371 * acos(
                cos(radians(:lat)) * cos(radians(lat)) *
                cos(radians(lng) - radians(:lon)) +
                sin(radians(:lat)) * sin(radians(lat))
           )) <= :radius
    ORDER BY distance_km ASC
""")


    candidates = db.execute(
        haversine_sql,
        {"lat": city_lat, "lon": city_lon, "radius": radius_km}
    ).fetchall()

    if not candidates:
        raise HTTPException(status_code=404, detail="No nearby places found in DB")

    # -------------------------
    # 3. Apply filters
    # -------------------------
    filtered = []
    for row in candidates:
        place = dict(row._mapping)
        if suitable_for and place.get("suitable_for"):
            if suitable_for not in place["suitable_for"]:
                continue
        if trip_type and place.get("tags"):
            if trip_type.lower() not in str(place["tags"]).lower():
                continue
        filtered.append(place)

    if not filtered:
        raise HTTPException(status_code=404, detail="No matching places found after filters")

    # -------------------------
    # 4. Format data for AI
    # -------------------------
    def safe_val(v):
        if isinstance(v, Decimal):
            return float(v)
        return v

    places_data = [
        {
            "name": safe_val(p["name"]),
            "category": safe_val(p.get("tags")),
            "tags": safe_val(p.get("tags")),
            "duration": safe_val(p.get("avg_visit_mins")),
            "rating": safe_val(p.get("rating")),
            "description": safe_val(p.get("description")),
            "distance_km": round(safe_val(p.get("distance_km", 0)), 2)
        }
        for p in filtered
    ]

    # -------------------------
    # 5. Build AI prompt
    # -------------------------
    prompt = f"""
You are a professional travel planner.

Task: Create a {days}-day itinerary for {city} (including nearby attractions within {radius_km} km).
Suitable for: {suitable_for}.
Trip type: {trip_type or "general"}.

Here are the available places with details:
{json.dumps(places_data, indent=2)}

Rules:
- Provide a JSON response only.
- Format: {{
  "Day 1": [{{"place": "X", "reason": "why chosen"}}],
  "Day 2": [...],
  ...
}}
- Each day must have 3–5 places.
- Balance famous landmarks + hidden gems.
- Respect approximate durations (~8 hrs/day).
- Prefer closer places first, but allow longer day trips if worth it.
- Ensure places fit the given trip type & suitable_for.
"""

    # -------------------------
    # 6. Query AI Model
    # -------------------------
    raw_response = query_llama(prompt)

    try:
        itinerary = json.loads(raw_response)
    except:
        itinerary = {"raw_response": raw_response}

    # -------------------------
    # 7. Return Response
    # -------------------------
    return {
        "city": city,
        "days": days,
        "suitable_for": suitable_for,
        "trip_type": trip_type or "general",
        "itinerary": itinerary,
    }

PlacesTable = Table("places", metadata, autoload_with=engine)

@router.post("/generate_itinerary1")
def generate_itinerary(
    city: str,
    days: int,
    suitable_for: Optional[str] = Query(default=None),
    db: Session = Depends(get_db)
):
    audience = (suitable_for or "").strip().lower() or None

    # 1) City coordinates
    city_row = db.execute(PlacesTable.select().where(PlacesTable.c.city.ilike(city))).fetchone()
    if not city_row or not city_row.lat or not city_row.lng:
        raise HTTPException(status_code=404, detail=f"No coordinates found for city {city}")[3]
    city_lat = float(city_row.lat)
    city_lon = float(city_row.lng)

    # 2) Auto radius
    radius_km = auto_radius_km(days)

    # 3) SQL Haversine fetch
    haversine_sql = text("""
        SELECT *,
            (6371 * acos(
                    cos(radians(:lat)) * cos(radians(lat)) *
                    cos(radians(lng) - radians(:lon)) +
                    sin(radians(:lat)) * sin(radians(lat))
            )) AS distance_km
        FROM places
        WHERE lat IS NOT NULL AND lng IS NOT NULL
        AND (6371 * acos(
                    cos(radians(:lat)) * cos(radians(lat)) *
                    cos(radians(lng) - radians(:lon)) +
                    sin(radians(:lat)) * sin(radians(lat))
            )) <= :radius
        ORDER BY distance_km ASC
    """)
    rows = db.execute(haversine_sql, {"lat": city_lat, "lon": city_lon, "radius": radius_km}).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="No nearby places found in DB")[3]

    # 4) Normalize candidates and compute hop time from city
    base: List[Dict[str, Any]] = []
    for row in rows:
        p = dict(row._mapping)
        obj = {
            "place_id": safe_val(p.get("place_id")),
            "name": safe_val(p.get("name")),
            "lat": float(safe_val(p.get("lat"))),
            "lng": float(safe_val(p.get("lng"))),
            "avg_visit_mins": parse_mins(safe_val(p.get("avg_visit_mins")), default=90),
            "rating": float(safe_val(p.get("rating"))) if p.get("rating") is not None else 0.0,
            "tags": safe_val(p.get("tags")),
            "description": safe_val(p.get("description")),
            "suitable_for_val": str(p.get("suitable_for") or ""),
            "distance_from_city_km": float(round(float(safe_val(p.get("distance_km", 0.0))), 2)),
            "city": safe_val(p.get("city")),
        }
        obj["hop_from_city_min"] = hop_time_from_city_minutes(obj, city_lat, city_lon)
        base.append(obj)

    # 5) Build candidate list for LLM (include far under policy cap)
    near = [x for x in base if x["distance_from_city_km"] <= 30.0]
    mid  = [x for x in base if 30.0 < x["distance_from_city_km"] <= 80.0]
    far  = [x for x in base if 80.0 < x["distance_from_city_km"] <= OUT_OF_CITY_ONE_WAY_KM_MAX]
    near.sort(key=lambda x: (x["distance_from_city_km"], -x["rating"], x["avg_visit_mins"]))
    mid.sort(key=lambda x: (x["distance_from_city_km"], -x["rating"], x["avg_visit_mins"]))
    far.sort(key=lambda x: (-x["rating"], x["distance_from_city_km"]))
    candidates_for_llm = near[:18] + mid[:12] + far[:12]
    candidates_for_llm = [
        {
            "place_id": c["place_id"], "name": c["name"],
            "lat": c["lat"], "lng": c["lng"],
            "visit_minutes": c["avg_visit_mins"], "rating": c["rating"],
            "distance_from_city_km": c["distance_from_city_km"],
            "hop_from_city_min": c["hop_from_city_min"],
            "city": c["city"]
        } for c in candidates_for_llm[:MAX_AI_CANDIDATES]
    ]

    # 6) Strict JSON schema and prompt (3–5 items/day; far-day guard)
    schema_hint = {
        "type": "object",
        "properties": {
            "itinerary": {
                "type": "object",
                "patternProperties": {
                    "^Day [1-9][0-9]*$": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "place_id": {"type": "string"},
                                "reason": {"type": "string"},
                                "notes": {"type": "string"}
                            },
                            "required": ["place_id"]
                        }
                    }
                },
                "additionalProperties": False
            }
        },
        "required": ["itinerary"]
    }
    prompt = f"""

Return STRICT JSON ONLY conforming to this schema (no prose): {json.dumps(schema_hint)}

Task: Generate a {days}-day itinerary for {city}. Use ONLY the places in Candidates. Arrange days to minimize travel by grouping nearby places.

Daily rules:

Aim for 3–5 places per day. Prefer 3–4 if time is tight.

Daily time budget: {DAY_BUDGET_MIN} minutes (travel + visits). Reserve {END_OF_DAY_BUFFER_MIN} minutes buffer.

Out-of-city day-trip rule (single-item day): If and ONLY if a place is outside the city (distance_from_city_km ≥ 60) AND hop_from_city_min2 + visit_minutes ≥ 0.7{DAY_BUDGET_MIN}, schedule that place alone on that day. Otherwise, do NOT return a single-item day.

Prefer higher rating and reasonable proximity; maintain variety across days.

Candidates (JSON array):
{json.dumps(candidates_for_llm, ensure_ascii=False)}
""".strip()
    # 7) Call LLM with structured outputs; fallback to subprocess; fallback to greedy
    def get_llm_itinerary_or_none(prompt: str, schema_hint: dict) -> Optional[dict]:
        try:
            raw = query_llama_structured(schema_hint, prompt, model=LLM_MODEL, base_url=OLLAMA_URL)[2][1]
            parsed = json.loads(raw)
            iti = parsed.get("itinerary", {})
            if isinstance(iti, dict) and iti:
                return iti
        except Exception:
            pass
        try:
            raw = query_llama_subprocess(prompt, model=LLM_MODEL)[5]
            parsed = json.loads(raw)
            iti = parsed.get("itinerary", {})
            if isinstance(iti, dict) and iti:
                return iti
        except Exception:
            pass
        return None

    itinerary = get_llm_itinerary_or_none(prompt, schema_hint)
    model_io_records = [{
        "stage": "llm_generate",
        "prompt_text": {"text": prompt},
        "raw_response_text": {"text": json.dumps(itinerary) if itinerary is not None else "LLM failed or returned empty"}
    }]

    # If model failed, seed a deterministic round-robin skeleton so days aren't empty
    if itinerary is None:
        ordered = sorted(base, key=lambda x: (x["distance_from_city_km"], -x["rating"], x["avg_visit_mins"]))
        seeds = [[] for _ in range(days)]
        for idx, poi in enumerate(ordered):
            # seed as a list of place_id dicts; validation will expand to full items
            seeds[idx % days].append({"place_id": poi["place_id"]})

        # Correct: just build the dict, no extra indexing
        itinerary = {f"Day {i+1}": seeds[i] for i in range(days)}

    # 8) Validate and repair plan; prefer 3–5 items/day; far-only single-item guard
    by_id = {c["place_id"]: c for c in base}

    def validate_and_repair_day(items: List[Dict[str, Any]],
                                min_items: int = 3,
                                max_items: int = MAX_ITEMS_PER_DAY) -> List[Dict[str, Any]]:
        day_plan = []
        time_used = 0
        cur_lat, cur_lon = city_lat, city_lon

        # Greedy accept while fitting time
        for it in items[:max_items]:
            pid = it.get("place_id")
            poi = by_id.get(pid)
            if not poi:
                continue
            hop = hop_time_minutes(cur_lat, cur_lon, poi["lat"], poi["lng"], city_lat, city_lon)
            projected = time_used + hop + poi["avg_visit_mins"]
            back_home = hop_time_minutes(poi["lat"], poi["lng"], city_lat, city_lon, city_lat, city_lon)
            if projected + back_home + END_OF_DAY_BUFFER_MIN <= DAY_BUDGET_MIN:
                day_plan.append({
                    "place": poi["name"], "place_id": poi["place_id"], "city": poi["city"],
                    "travel_from_prev_minutes": hop, "visit_minutes": poi["avg_visit_mins"],
                    "distance_from_city_km": poi["distance_from_city_km"],
                    "reason": it.get("reason") or "Model-selected"
                })
                time_used = projected
                cur_lat, cur_lon = poi["lat"], poi["lng"]

        # Try to reach min_items if possible
        if len(day_plan) < min_items:
            chosen = {dp["place_id"] for dp in day_plan}
            for it in items:
                if len(day_plan) >= min_items:
                    break
                pid = it.get("place_id")
                if pid in chosen:
                    continue
                poi = by_id.get(pid)
                if not poi:
                    continue
                hop = hop_time_minutes(cur_lat, cur_lon, poi["lat"], poi["lng"], city_lat, city_lon)
                projected = time_used + hop + poi["avg_visit_mins"]
                back_home = hop_time_minutes(poi["lat"], poi["lng"], city_lat, city_lon, city_lat, city_lon)
                if projected + back_home + END_OF_DAY_BUFFER_MIN <= DAY_BUDGET_MIN and len(day_plan) < max_items:
                    day_plan.append({
                        "place": poi["name"], "place_id": poi["place_id"], "city": poi["city"],
                        "travel_from_prev_minutes": hop, "visit_minutes": poi["avg_visit_mins"],
                        "distance_from_city_km": poi["distance_from_city_km"],
                        "reason": it.get("reason") or "Model-selected"
                    })
                    time_used = projected
                    cur_lat, cur_lon = poi["lat"], poi["lng"]

        return day_plan

    def greedy_fill_nearby(city_lat, city_lon, base, used_ids, max_items=3):
        cand = sorted(
            [c for c in base if c["place_id"] not in used_ids],
            key=lambda x: (haversine_km(city_lat, city_lon, x["lat"], x["lng"]), -x["rating"])
        )
        plan, time_used = [], 0
        cur_lat, cur_lon = city_lat, city_lon
        for c in cand:
            if len(plan) >= max_items:
                break
            hop = hop_time_minutes(cur_lat, cur_lon, c["lat"], c["lng"], city_lat, city_lon)
            projected = time_used + hop + c["avg_visit_mins"]
            back_home = hop_time_minutes(c["lat"], c["lng"], city_lat, city_lon, city_lat, city_lon)
            if projected + back_home + END_OF_DAY_BUFFER_MIN <= DAY_BUDGET_MIN:
                plan.append({
                    "place": c["name"], "place_id": c["place_id"], "city": c["city"],
                    "travel_from_prev_minutes": hop, "visit_minutes": c["avg_visit_mins"],
                    "distance_from_city_km": c["distance_from_city_km"],
                    "reason": "Greedy fill (LLM fallback)"
                })
                time_used = projected
                cur_lat, cur_lon = c["lat"], c["lng"]
        return plan[7]

    used_ids = set()
    validated: Dict[str, List[Dict[str, Any]]] = {}

    for d in range(1, days + 1):
        key = f"Day {d}"
        model_items = itinerary.get(key, [])
        model_items = [x for x in model_items if x.get("place_id") not in used_ids]
        day_plan = validate_and_repair_day(model_items, min_items=3, max_items=MAX_ITEMS_PER_DAY)

        # If single-item but not a true far day-trip, try to add more nearby feasible items
        if len(day_plan) == 1:
            pid = day_plan["place_id"]
            poi = by_id.get(pid)
            total = round_trip_minutes(poi, city_lat, city_lon)
            is_far = (poi["distance_from_city_km"] >= 60) or (hop_time_from_city_minutes(poi, city_lat, city_lon) >= 90)
            high_util = total >= int(0.7 * DAY_BUDGET_MIN)
            if not (is_far and high_util):
                # Try to enrich the day with greedy additions
                extra = greedy_fill_nearby(city_lat, city_lon, [c for c in base if c["place_id"] != pid], used_ids, max_items=2)
                day_plan.extend([e for e in extra if e["place_id"] not in {pid}])
                # Keep at most MAX_ITEMS_PER_DAY
                if len(day_plan) > MAX_ITEMS_PER_DAY:
                    day_plan = day_plan[:MAX_ITEMS_PER_DAY]

        # If still empty, attempt greedy fill; if still empty, consider far-day backstop
        if not day_plan:
            day_plan = greedy_fill_nearby(city_lat, city_lon, base, used_ids, max_items=3)

        if not day_plan:
            far_pool = [
                c for c in base
                if c["place_id"] not in used_ids and (
                    c["distance_from_city_km"] >= 60 or hop_time_from_city_minutes(c, city_lat, city_lon) >= 90
                )
            ]
            far_pool.sort(key=lambda x: (-x["rating"], x["distance_from_city_km"]))
            for c in far_pool:
                total = round_trip_minutes(c, city_lat, city_lon)
                if total + END_OF_DAY_BUFFER_MIN <= DAY_BUDGET_MIN and total >= int(0.7 * DAY_BUDGET_MIN):
                    day_plan = [{
                        "place": c["name"], "place_id": c["place_id"], "city": c["city"],
                        "reason": "Full-day out-of-city landmark; travel+visit fits daily budget",
                        "estimated_minutes": total,
                        "distance_from_city_km": c["distance_from_city_km"]
                    }]
                    break

        validated[key] = day_plan
        for it in day_plan:
            used_ids.add(it["place_id"])

    # 9) Persist: request, candidate snapshot (without hop_from_city_min if not in schema), model I/O, result
    req = ItineraryRequest(city=city, days=days, suitable_for=audience or None, version="v2.2.0")
    db.add(req); db.flush()

    cand_rows = [
        ItineraryCandidate(
            itinerary_request_id=req.id,
            place_id=c["place_id"], name=c["name"], lat=c["lat"], lng=c["lng"],
            avg_visit_mins=int(c["visit_minutes"]), rating=float(c.get("rating") or 0.0),
            distance_from_city_km=float(c.get("distance_from_city_km") or 0.0),
            # do not pass hop_from_city_min unless your model has this column
            city=c.get("city") or None
        ) for c in candidates_for_llm
    ]
    if cand_rows:
        db.add_all(cand_rows)

    # if model_io_records:
    #     io_rows = [
    #         ItineraryModelIO(
    #             itinerary_request_id=req.id,
    #             stage=rec.get("stage", "llm_generate"),
    #             prompt_text=rec.get("prompt_text", {"text": ""}),
    #             raw_response_text=rec.get("raw_response_text", {"text": ""})
    #         ) for rec in model_io_records
    #     ]
    #     db.add_all(io_rows)[8]

    auto_params_obj = {
        "candidate_radius_km": radius_km,
        "day_budget_minutes": DAY_BUDGET_MIN,
        "end_of_day_buffer_min": END_OF_DAY_BUFFER_MIN,
        "urban_speed_kmh": URBAN_SPEED_KMH,
        "intercity_speed_kmh": INTERCITY_SPEED_KMH,
        "per_hop_buffer_min": HOP_BUFFER_MIN,
        "out_of_city_one_way_km_max": OUT_OF_CITY_ONE_WAY_KM_MAX,
        "target_items_per_day": TARGET_ITEMS_PER_DAY,
        "max_items_per_day": MAX_ITEMS_PER_DAY
    }
    db.add(ItineraryResult(
        itinerary_request_id=req.id,
        itinerary_json=validated,
        auto_params_json=auto_params_obj
    ))
    db.commit()

    return {
        "request_id": req.id,
        "city": city,
        "days": days,
        "suitable_for": audience or "",
        "itinerary": validated,
        "auto_parameters": auto_params_obj
    }
