from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time
from app.database.db import get_db
from app.api.places.models import Places
from typing import List, Optional, Dict, Any
from app.utils.embeddings import get_embedding
import subprocess
from sqlalchemy import text, func, Table, MetaData, create_engine
import json, math, httpx, subprocess
from app.api.places.schema import WEEKDAYS, EntryFee, Accessibility, PlaceCreate
import os
from decimal import Decimal
from sqlalchemy import MetaData, create_engine
from app.utils.helper import URBAN_SPEED_KMH, INTERCITY_SPEED_KMH, EARTH_KM, MAX_AI_CANDIDATES, MAX_ITEMS_PER_DAY, TARGET_ITEMS_PER_DAY, OUT_OF_CITY_ONE_WAY_KM_MAX, END_OF_DAY_BUFFER_MIN, DAY_BUDGET_MIN, HOP_BUFFER_MIN, OLLAMA_URL, TRAVEL_BUFFER_MIN, DAILY_AVAILABLE_MINS, EARTH_RADIUS_KM, MAX_CANDIDATES, MAX_VISITS_PER_DAY, TARGET_VISITS_PER_DAY, OUTER_BOUNDARY_KM, END_BUFFER_MIN, DAY_MAX_MINUTES, DAY_END_HOUR, DAY_START_HOUR, LLM_MODEL
from app.api.itineraries.models import ItineraryRequest, ItineraryCandidate, ItineraryResult, ItineraryModelIO
from app.utils.helper import persist_itinerary, adjust_start_time_for_opening, is_within_open_hours, parse_time, round_trip_minutes, hop_time_minutes, hop_time_from_city_minutes, travel_minutes_est, AUDIENCE_TERMS, text_blob, auto_radius_km, parse_mins, ai_fill_with_llama, safe_val, haversine_km, query_llama, query_llama_local, query_llama_structured, query_llama_subprocess
router = APIRouter(prefix="/itinerary", tags=["Itinerary"])
metadata = MetaData()
engine = create_engine(os.getenv("DATABASE_URL"), future=True)

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
    # db.add(ItineraryResult(
    #     itinerary_request_id=req.id,
    #     itinerary_json=validated,
    #     auto_params_json=auto_params_obj
    # ))
    db.commit()

    return {
        "request_id": req.id,
        "city": city,
        "days": days,
        "suitable_for": audience or "",
        "itinerary": validated,
        "auto_parameters": auto_params_obj
    }

@router.post("/generate_itinerary3")
def generate_itinerary(
    city: str,
    days: int,
    suitable_for: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    audience = (suitable_for or "").strip().lower() or None

    # 1) Fetch city coordinates
    city_row = db.execute(PlacesTable.select().where(PlacesTable.c.city.ilike(city))).first()
    if not city_row or not city_row.lat or not city_row.lng:
        raise HTTPException(404, f"No coordinates found for city {city}")
    city_lat = float(city_row.lat)
    city_lon = float(city_row.lng)

    # 2) Determine search radius based on days
    def auto_radius(days: int) -> int:
        if days <= 1: return 25
        elif days == 2: return 60
        elif days == 3: return 120
        elif days == 4: return 160
        return 220
    radius_km = auto_radius(days)

    # 3) Fetch candidate places within radius
    sql = text("""
        SELECT *, ({} * acos(
            cos(radians(:lat)) * cos(radians(lat)) *
            cos(radians(lng) - radians(:lon)) +
            sin(radians(:lat)) * sin(radians(lat))
        )) AS distance_km
        FROM places
        WHERE lat IS NOT NULL AND lng IS NOT NULL
        AND ({} * acos(
            cos(radians(:lat)) * cos(radians(lat)) *
            cos(radians(lng) - radians(:lon)) +
            sin(radians(:lat)) * sin(radians(lat))
        )) <= :radius
        ORDER BY distance_km ASC
    """.format(EARTH_KM, EARTH_KM))
    rows = db.execute(sql, {"lat": city_lat, "lon": city_lon, "radius": radius_km}).fetchall()

    if not rows:
        raise HTTPException(404, "No nearby places found")

    # 4) Normalize and annotate candidates
    base_candidates = []
    for r in rows:
        p = dict(r._mapping)
        candidate = {
            "place_id": safe_val(p.get("place_id")),
            "name": safe_val(p.get("name")),
            "lat": float(safe_val(p.get("lat"))),
            "lng": float(safe_val(p.get("lng"))),
            "avg_visit_mins": parse_mins(safe_val(p.get("avg_visit_mins")), 90),
            "rating": float(safe_val(p.get("rating")) or 0),
            "tags": safe_val(p.get("tags")),
            "description": safe_val(p.get("description")),
            "suitable_for": safe_val(p.get("suitable_for")),
            "distance_km": float(round(p.get("distance_km", 0), 2)),
            "city": safe_val(p.get("city")),
        }
        candidate["hop_time"] = hop_time_from_city_minutes(candidate, city_lat, city_lon)
        base_candidates.append(candidate)

    # 5) Prepare candidates to send to LLM (merging near+mid+far categories)
    near = [c for c in base_candidates if c["distance_km"] <= 30]
    mid = [c for c in base_candidates if 30 < c["distance_km"] <= 80]
    far = [c for c in base_candidates if 80 < c["distance_km"] <= OUT_OF_CITY_ONE_WAY_KM_MAX]
    near.sort(key=lambda c: (c["distance_km"], -c["rating"], c["avg_visit_mins"]))
    mid.sort(key=lambda c: (c["distance_km"], -c["rating"], c["avg_visit_mins"]))
    far.sort(key=lambda c: (-c["rating"], c["distance_km"]))
    candidates_for_llm = near[:18] + mid[:12] + far[:12]
    if len(candidates_for_llm) > MAX_AI_CANDIDATES:
        candidates_for_llm = candidates_for_llm[:MAX_AI_CANDIDATES]

    # Prepare clean dicts for LLM input
    llm_input_candidates = [{
        "place_id": c["place_id"],
        "name": c["name"],
        "lat": c["lat"],
        "lng": c["lng"],
        "visit_mins": c["avg_visit_mins"],
        "rating": c["rating"],
        "distance_km": c["distance_km"],
        "hop_time": c["hop_time"],
        "city": c["city"],
        "description": c["description"]
    } for c in candidates_for_llm]

    # 6) Build prompt & schema
    schema = {
        "type": "object",
        "properties": {
            "itinerary": {
                "type": "object",
                "patternProperties": {
                    "^Day \d+$": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "place_id": {"type": "string"},
                                "activities": {"type": "string"},
                                "description": {"type": "string"},
                                "start_time": {"type": "string"}
                            },
                            "required": ["place_id", "activities", "start_time"]
                        }
                    }
                }
            }
        },
        "required": ["itinerary"],
        "additionalProperties": False
    }

    prompt = f"""
You are a professional travel planner assistant.

Generate a detailed {days}-day itinerary starting each day at 10:00 AM. For each visit specify:
- start time,
- place name,
- planned list of activities,
- descriptions,
- fit 3-5 places per day,
- consider travel and visit durations within 8 hours/day (with buffer).

Use ONLY the following places (in JSON). Provide output as STRICT JSON conforming to the attached schema:

Places:
{json.dumps(llm_input_candidates, indent=2)}

Format:
{json.dumps(schema, indent=2)}
"""

    # 7) Call LLM (try structured calls with fallback)
    def call_model(prompt, schema):
        try:
            res = query_llama_structured(schema, prompt, model=LLM_MODEL, base_url=OLLAMA_URL)
            return json.loads(res)
        except Exception:
            try:
                res = query_llama_subprocess(prompt, model=LLM_MODEL)
                return json.loads(res)
            except Exception:
                return None

    raw_result = call_model(prompt, schema)
    itinerary_json = raw_result.get("itinerary") if raw_result else None

    # Fallback deterministic planner if LLM fails or no result
    if not itinerary_json:
        # Simple round-robin distribution of candidates with sequential scheduling starting 10:00 AM
        itinerary_json = {}
        start_hour = 10
        for day in range(1, days + 1):
            itinerary_json[f"Day {day}"] = []

        for idx, c in enumerate(candidates_for_llm):
            day = (idx % days) + 1
            itinerary_json[f"Day {day}"].append({
                "place_id": c["place_id"],
                "activities": "Visit",
                "description": c.get("description", ""),
                "start_time": f"{start_hour + 0:02d}:00 AM"
            })

    # 8) Build human-readable itinerary string
    lines = []
    for day in range(1, days + 1):
        day_key = f"Day {day}"
        lines.append(f"Day {day} in {city}\n")
        current_time = datetime.combine(datetime.today(), datetime.min.time()) + timedelta(hours=10)
        visits = itinerary_json.get(day_key, [])
        if not visits:
            lines.append("No scheduled visits.\n\n")
            continue
        for v in visits:
            start_time = v.get("start_time")
            place_name = next((c["name"] for c in candidates_for_llm if c["place_id"] == v["place_id"]), "Unknown place")
            activities = v.get("activities", "Visit")
            descr = v.get("description", "No description available.")
            lines.append(f"{start_time}: {place_name}\n")
            lines.append(f"  Activities: {activities}\n")
            lines.append(f"  Description: {descr}\n\n")

    # 9) Save to file
    folder = "saved_itineraries"
    os.makedirs(folder, exist_ok=True)
    filename = f"{city}_{days}days_itinerary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(folder, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # 10) Persist in DB (existing paradigm)
    # Note: you can adjust for your DB schema

    req = ItineraryRequest(city=city, days=days, suitable_for=audience, version="v1")
    db.add(req)
    db.flush()

    # Save candidates without hop_time (if not DB field)
    cand_rows = [
        ItineraryCandidate(
            itinerary_request_id=req.id or 0,
            place_id=c["place_id"],
            name=c["name"],
            lat=c["lat"],
            lng=c["lng"],
            avg_visit_mins=c["avg_visit_mins"],
            rating=c["rating"],
            city=c.get("city")
        )
        for c in llm_input_candidates
    ]
    db.add_all(cand_rows)

    # Save itinerary and parameters
    params = {
        "candidate_radius": radius_km,
        "day_budget": DAY_BUDGET_MIN,
        "buffer": END_OF_DAY_BUFFER_MIN,
        "urban_speed": URBAN_SPEED_KMH,
        "intercity_speed": INTERCITY_SPEED_KMH,
        "max_items_per_day": MAX_ITEMS_PER_DAY,
        "target_items_per_day": TARGET_ITEMS_PER_DAY,
    }
    db.add(ItineraryResult(
        itinerary_json=itinerary_json,
        auto_params_json=params,
        itinerary_request_id=req.id or 0
    ))
    db.commit()

    return {
        "request_id": req.id,
        "city": city,
        "days": days,
        "suitable_for": audience,
        "itinerary_path": filepath,
        "message": "Itinerary generated and saved successfully."
    }






@router.post("/generate_itinerary4")
def generate_itinerary(city: str, days: int, suitable_for: Optional[str] = Query(None), db: Session = Depends(get_db)):
    audience = (suitable_for or "").strip() or None

    # 1. Get city lat/lng
    city_row = db.execute(PlacesTable.select().where(PlacesTable.c.city.ilike(city))).first()
    if not city_row or not city_row.lat or not city_row.lng:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found or missing coordinates")
    city_lat, city_lon = float(city_row.lat), float(city_row.lng)

    # 2. Determine search radius
    def radius_for_days(n): return {1: 25, 2: 60, 3: 120, 4: 160}.get(n, OUTER_BOUNDARY_KM)
    radius = radius_for_days(days)

    # 3. Retrieve places within radius
    sql = text(f"""
        SELECT *, ({EARTH_RADIUS_KM} * acos(
            cos(radians(:lat)) * cos(radians(lat)) * cos(radians(lng) - radians(:lon))
            + sin(radians(:lat)) * sin(radians(lat))
        )) AS distance_km
        FROM places
        WHERE lat IS NOT NULL AND lng IS NOT NULL
          AND ({EARTH_RADIUS_KM} * acos(
            cos(radians(:lat)) * cos(radians(lat)) * cos(radians(lng) - radians(:lon))
            + sin(radians(:lat)) * sin(radians(lat))
          )) <= :radius
        ORDER BY distance_km ASC
    """)
    rows = db.execute(sql, {"lat": city_lat, "lon": city_lon, "radius": radius}).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No places found near {city} within {radius} km")

    # 4. Normalize places
    places = []
    for r in rows:
        d = dict(r._mapping)
        place = {
            "place_id": safe_val(d.get("place_id")),
            "name": safe_val(d.get("name")),
            "lat": float(safe_val(d.get("lat"))),
            "lng": float(safe_val(d.get("lng"))),
            "avg_time": parse_mins(d.get("avg_visiting_time"), 60),
            "rating": float(safe_val(d.get("rating") or 0)),
            "description": safe_val(d.get("description") or ""),
            "distance": round(float(d.get("distance_km") or 0), 2),
            "city": safe_val(d.get("city")),
            "opening_hours": json.loads(d.get("opening_hours") or "{}")  # assuming JSON stored
        }
        place["hop_time"] = hop_time_from_city_minutes(place, city_lat, city_lon)
        places.append(place)

    # 5. Categorize and select candidates for LLM
    near = [p for p in places if p["distance"] <= 30]
    mid = [p for p in places if 30 < p["distance"] <= 80]
    far = [p for p in places if 80 < p["distance"] <= OUTER_BOUNDARY_KM]
    near.sort(key=lambda x: (x["distance"], -x["rating"], x["avg_time"]))
    mid.sort(key=lambda x: (x["distance"], -x["rating"], x["avg_time"]))
    far.sort(key=lambda x: (-x["rating"], x["distance"]))
    candidates = (near[:18] + mid[:12] + far[:12])[:MAX_CANDIDATES]

    candidates_for_llm = [{
        "place_id": c["place_id"],
        "name": c["name"],
        "lat": c["lat"],
        "lng": c["lng"],
        "avg_time": c["avg_time"],
        "rating": c["rating"],
        "distance": c["distance"],
        "hop_time": c["hop_time"],
        "city": c["city"],
        "description": c["description"],
        "opening_hours": c["opening_hours"],
    } for c in candidates]

    # 6. Prepare LLM prompt & schema
    schema = {
        "type": "object",
        "properties": {
            "itinerary": {
                "type": "object",
                "patternProperties": {
                    "^Day \\d+$": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "place_id": {"type": "string"},
                                "activities": {"type": "string"},
                                "description": {"type": "string"},
                                "start_time": {"type": "string"}
                            },
                            "required": ["place_id", "activities", "start_time"]
                        }
                    }
                },
                "additionalProperties": False
            }
        },
        "required": ["itinerary"]
    }

    prompt = f"""
You are a travel planner creating a {days}-day itinerary for {city}.
Assign visit start times starting from {DAY_START_HOUR}:00 daily.
Ensure visits and travel fit into {DAY_MAX_MINUTES}-minute day with breaks and respecting opening hours:
venues may be closed outside opening_hours field.

Here are candidate places:
{json.dumps(candidates_for_llm, indent=2)}

Please respond ONLY with JSON matching this schema:
{json.dumps(schema, indent=2)}
"""

    def call_llm(prompt_text, schema):
        try:
            resp = query_llama_structured(prompt_text, schema, model=LLM_MODEL, base_url=OLLAMA_URL)
            return json.loads(resp)
        except:
            try:
                resp = query_llama_structured(prompt_text, model=LLM_MODEL)
                return json.loads(resp)
            except:
                return None

    response = call_llm(prompt, schema)
    itinerary_json = response.get("itinerary") if response else None

    if not itinerary_json:
        # Simple fallback assign visits round-robin with 1-hour slots ignoring opening_hours
        itinerary_json = {f"Day {i+1}": [] for i in range(days)}
        for idx, place in enumerate(candidates_for_llm):
            day = f"Day {(idx % days) + 1}"
            hour = DAY_START_HOUR + (idx // days)
            itinerary_json[day].append({
                "place_id": place["place_id"],
                "activities": "Visit",
                "description": place["description"],
                "start_time": f"{hour}:00"
            })

    # 7. Format human-readable itinerary, respecting opening hours and travel times
    def format_realistic_itinerary(itinerary, city, days, city_lat, city_lon, candidate_map):
        lines = []
        day_start_time = datetime.combine(datetime.today(), time(hour=DAY_START_HOUR))

        for day in range(1, days + 1):
            lines.append(f"Day {day} in {city}\n")
            current_time = day_start_time
            prev_place = None

            visits = itinerary.get(f"Day {day}", [])
            if not visits:
                lines.append("No planned visits.\n\n")
                continue

            for visit in visits:
                place_id = visit["place_id"]
                place = candidate_map.get(place_id, None)
                if not place:
                    continue

                # Calculate travel time from previous place
                if prev_place:
                    travel_mins = hop_time_minutes(prev_place["lat"], prev_place["lng"], place["lat"], place["lng"], city_lat, city_lon)
                else:
                    travel_mins = 0
                current_time += timedelta(minutes=travel_mins + HOP_BUFFER_MIN)

                # Adjust for opening hours
                opening_hours = place.get("opening_hours", {})
                if opening_hours:
                    adjusted_time = adjust_start_time_for_opening(current_time, opening_hours)
                    if adjusted_time > current_time:
                        # Wait for opening
                        current_time = adjusted_time

                visit_duration = place.get("avg_time", 60)
                end_time = current_time + timedelta(minutes=visit_duration)

                lines.append(f"{current_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}: {place['name']}\n")
                lines.append(f"  Activities: {visit.get('activities', 'Visit')}\n")
                lines.append(f"  Description: {visit.get('description', place.get('description',''))}\n\n")

                current_time = end_time + timedelta(minutes=15)  # break before next visit
                prev_place = place

            lines.append("\n")

        return "".join(lines)

    candidate_map = {c["place_id"]: c for c in candidates_for_llm}
    readable_itinerary = format_realistic_itinerary(itinerary_json, city, days, city_lat, city_lon, candidate_map)

    # 8. Save itinerary to file
    output_dir = "saved_itineraries"
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{city}_itinerary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(readable_itinerary)

    # 9. Persist to database
    req = ItineraryRequest(city=city, days=days, suitable_for=audience, version="1.0")
    db.add(req)
    db.flush()

    cand_entities = []
    for p in candidates_for_llm:
        entity = ItineraryCandidate(
            itinerary_request_id=req.id or 0,
            place_id=p["place_id"],
            name=p["name"],
            lat=p["lat"],
            avg_visit_mins=p["avg_time"],
            lng=p["lng"],
            rating=p["rating"],
            city=p["city"]
        )
        cand_entities.append(entity)
    db.add_all(cand_entities)

    params = {
        "radius": radius,
        "daily_budget_minutes": DAY_MAX_MINUTES,
        "daily_start_hour": DAY_START_HOUR,
        "buffer_minutes": END_BUFFER_MIN,
        "urban_speed_kmh": URBAN_SPEED_KMH,
        "intercity_speed_kmh": INTERCITY_SPEED_KMH,
        "max_visits_per_day": MAX_VISITS_PER_DAY,
        "target_visits_per_day": TARGET_VISITS_PER_DAY,
    }

    result_entity = ItineraryResult(
        itinerary_request_id=req.id,
        itinerary_json=itinerary_json,
        auto_params_json=params,
    )

    db.add(result_entity)
    db.commit()

    return {
        "request_id": req.id,
        "city": city,
        "days": days,
        "itinerary_text_file": filepath,
        "message": "Itinerary generated with opening hours and travel times."
    }

@router.post("/generate_itinerary_fresh")
def generate_itinerary_fresh(
    city: str,
    days: int,
    suitable_for: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    audience = (suitable_for or "").strip() or None

    # 1. Get city lat/lng
    city_row = db.execute(PlacesTable.select().where(PlacesTable.c.city.ilike(city))).first()
    if not city_row or not city_row.lat or not city_row.lng:
        raise HTTPException(404, f"City '{city}' not found or missing coordinates")
    city_lat, city_lon = float(city_row.lat), float(city_row.lng)

    # 2. Radius by days
    radius_map = {1: 25, 2: 60, 3: 120, 4: 160}
    radius = radius_map.get(days, 220)

    # 3. Query places with distance & assume JSON string 'opening_hours' in DB column
    sql = text(f"""
        SELECT *, ({EARTH_RADIUS_KM} * acos(
                cos(radians(:lat)) * cos(radians(lat)) *
                cos(radians(lng) - radians(:lon)) +
                sin(radians(:lat)) * sin(radians(lat))
            )) AS distance_km
        FROM places
        WHERE lat IS NOT NULL AND lng IS NOT NULL
        AND ({EARTH_RADIUS_KM} * acos(
                cos(radians(:lat)) * cos(radians(lat)) *
                cos(radians(lng) - radians(:lon)) +
                sin(radians(:lat)) * sin(radians(lat))
            )) <= :radius
        ORDER BY distance_km ASC
    """)

    rows = db.execute(sql, {"lat": city_lat, "lon": city_lon, "radius": radius}).fetchall()
    if not rows:
        raise HTTPException(404, f"No places found within {radius}km of {city}")

    # 4. Build candidate list with opening hours parsed
    candidates = []
    import json as pyjson
    for r in rows:
        d = dict(r._mapping)
        oh_json = d.get("opening_hours") or "{}"
        try:
            opening_hours = pyjson.loads(oh_json)
        except Exception:
            opening_hours = {}

        candidate = {
            "place_id": d.get("place_id"),
            "name": d.get("name"),
            "lat": float(d.get("lat")),
            "lng": float(d.get("lng")),
            "avg_time": parse_mins(d.get("avg_time") or d.get("avg_visiting_time") or 60),
            "rating": float(d.get("rating") or 0),
            "description": d.get("description") or "",
            "distance": round(float(d.get("distance_km") or 0), 2),
            "city": d.get("city"),
            "opening_hours": opening_hours,
        }
        candidate["hop_time"] = hop_time_minutes(city_lat, city_lon, candidate["lat"], candidate["lng"], city_lat, city_lon)
        candidates.append(candidate)

    # Sort and limit candidates
    candidates.sort(key=lambda c: (c["distance"], -c["rating"]))
    candidates = candidates[:MAX_CANDIDATES]

    # 5. Prepare prompt and schema for LLM
    schema = {
        "type": "object",
        "properties": {
            "itinerary": {
                "type": "object",
                "patternProperties": {
                    "^Day \\d+$": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "place_id": {"type": "string"},
                                "activities": {"type": "string"},
                                "description": {"type": "string"},
                                "start_time": {"type": "string"},
                            },
                            "required": ["place_id", "activities", "start_time"],
                        },
                    }
                },
                "additionalProperties": False,
            }
        },
        "required": ["itinerary"],
    }

    prompt = f"""
You are a professional travel planner generating a {days}-day itinerary for {city}. 
Assign start times, daily begin at {DAY_START_HOUR}AM, fit 3-5 visits/day within approx {int(DAILY_AVAILABLE_MINS/60)} hours. 
Consider travel time and venue opening hours (given as 'opening_hours' JSON).
Output JSON strictly confirms attached schema.
Here are candidate places with details:
{json.dumps(candidates, indent=2)}
Schema:
{json.dumps(schema, indent=2)}
"""

    def call_llm(prompt_text: str, schema: dict):
        try:
            resp = query_llama_structured(prompt_text, schema, model=LLM_MODEL, base_url=OLLAMA_URL)
            return json.loads(resp)
        except Exception:
            try:
                resp = query_llama_subprocess(prompt_text, model=LLM_MODEL)
                return json.loads(resp)
            except Exception:
                return None

    result = call_llm(prompt, schema)
    itinerary_json = result.get("itinerary") if result else None

    # Fallback — assign sequentially ignoring advanced constraints
    if not itinerary_json:
        itinerary_json = {f"Day {i+1}": [] for i in range(days)}
        hour = DAY_START_HOUR
        for idx, c in enumerate(candidates):
            d = f"Day {(idx % days) + 1}"
            itinerary_json[d].append({
                "place_id": c["place_id"],
                "activities": "Visit",
                "description": c["description"],
                "start_time": f"{hour}:00",
            })

    # Map candidates by ID
    candid_map = {c["place_id"]: c for c in candidates}

    # 6. Format detailed itinerary respecting opening hours & travel times
    def format_itinerary(itin, city, cand_map):
        lines = []
        for day_n in sorted(itin.keys(), key=lambda x: int(x.split()[1])):
            lines.append(f"{day_n} in {city}\n")
            visits = itin[day_n]
            current_dt = datetime.combine(datetime.today(), time(hour=DAY_START_HOUR))
            prev_place = None

            for v in visits:
                place = cand_map.get(v.get("place_id"))
                if not place:
                    continue

                # Calculate travel time from prev place
                if prev_place:
                    travel_mins = hop_time_minutes(prev_place["lat"], prev_place["lng"], place["lat"], place["lng"], city_lat, city_lon)
                else:
                    travel_mins = 0
                # Include buffer
                current_dt += timedelta(minutes=travel_mins + TRAVEL_BUFFER_MIN)

                # Adjust start time for opening hours
                opening_hours = place.get("opening_hours", {})
                current_dt = adjust_start_time_for_opening(current_dt, opening_hours)

                visit_dur = place.get("avg_time", 60)
                end_dt = current_dt + timedelta(minutes=visit_dur)

                lines.append(f"{current_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}: {place['name']}\n")
                lines.append(f"  Activities: {v.get('activities', 'Visit')}\n")
                lines.append(f"  Description: {v.get('description', place.get('description', ''))}\n\n")

                current_dt = end_dt + timedelta(minutes=15)  # small break before next visit
                prev_place = place

            lines.append("\n")
        return "".join(lines)

    readable_itinerary = format_itinerary(itinerary_json, city, candid_map)

    # 7. Save to file
    out_dir = "saved_itineraries"
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{city}_itinerary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(out_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(readable_itinerary)

    # 8. Persist in DB
    req = ItineraryRequest(city=city, days=days, suitable_for=audience, version="1.0")
    db.add(req)
    db.flush()

    cand_entities = []
    for c in candidates:
        entity = ItineraryCandidate(
            itinerary_request_id=req.id,
            place_id=c["place_id"],
            name=c["name"],
            lat=c["lat"],
            lng=c["lng"],
            avg_visit_mins=c["avg_time"],
            rating=c["rating"],
            city=c["city"],
        )
        cand_entities.append(entity)
    db.add_all(cand_entities)

    params = {
        "radius_km": radius,
        "day_start_hour": DAY_START_HOUR,
        "day_end_hour": DAY_END_HOUR,
        "daily_available_mins": DAILY_AVAILABLE_MINS,
        "buffer_mins": TRAVEL_BUFFER_MIN,
        "max_visits_per_day": MAX_VISITS_PER_DAY,
        "target_visits_per_day": TARGET_VISITS_PER_DAY,
        "version": "1.0"
    }

    result = ItineraryResult(
        itinerary_request_id=req.id,
        itinerary_json=itinerary_json,
        auto_params_json=params,
    )
    db.add(result)
    db.commit()

    return {
        "request_id": req.id,
        "city": city,
        "days": days,
        "itinerary_file_path": filepath,
        "message": "Itinerary generated respecting timings and opening hours."
    }