import json
import random
import pandas as pd
from math import radians, cos, sin, asin, sqrt

# -----------------------------
# Helper: Haversine distance
# -----------------------------
def haversine(lon1, lat1, lon2, lat2):
    R = 6371  # Earth radius in km
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2*asin(sqrt(a))
    return R * c

# -----------------------------
# Auto-generate itineraries
# -----------------------------
def generate_itinerary(city_df, days, suitable_for, trip_type):
    places = city_df.to_dict("records")
    random.shuffle(places)

    daily_limit = 8  # hours per day
    used = set()
    itinerary = {}

    for d in range(1, days + 1):
        day_plan = []
        time_used = 0

        for p in places:
            if p["name"] in used:
                continue

            # --- Normalize suitable_for field ---
            raw_suitable = p.get("suitable_for")
            if raw_suitable is None or (isinstance(raw_suitable, float) and pd.isna(raw_suitable)):
                place_suitable = []
            elif isinstance(raw_suitable, str):
                # split by comma or braces
                place_suitable = [s.strip().lower() for s in raw_suitable.strip("{}").split(",") if s.strip()]
            elif isinstance(raw_suitable, list):
                place_suitable = [str(s).lower() for s in raw_suitable]
            else:
                place_suitable = []

            # --- Normalize tags ---
            place_tags = str(p.get("tags") or "").lower()

            # --- Filtering ---
            if suitable_for and suitable_for.lower() not in place_suitable:
                continue
            if trip_type and trip_type.lower() not in place_tags:
                continue

            # --- Duration ---
            try:
                dur = float(p.get("duration", 2))
            except (ValueError, TypeError):
                dur = 2.0

            if time_used + dur <= daily_limit:
                used.add(p["name"])
                time_used += dur
                day_plan.append({
                    "place": p["name"],
                    "reason": f"Fits {trip_type or 'general'} trip, approx {dur} hrs, rating {p.get('rating', 4)}"
                })

        if day_plan:
            itinerary[f"Day {d}"] = day_plan

    return itinerary


# -----------------------------
# Build training examples
# -----------------------------
def build_training_examples(df, n_samples=50):
    samples = []
    cities = df["city"].unique()

    for _ in range(n_samples):
        city = random.choice(cities)
        city_df = df[df["city"] == city]

        days = random.randint(2, 5)
        suitable_for = random.choice(["solo", "couple", "family", "group"])
        trip_type = random.choice(["spiritual", "leisure", "adventure", None])

        # Input prompt
        inp = {
            "city": city,
            "days": days,
            "suitable_for": suitable_for,
            "trip_type": trip_type or "general"
        }

        # Output itinerary
        out = generate_itinerary(city_df, days, suitable_for, trip_type)

        samples.append({
            "messages": [
                {"role": "user", "content": json.dumps(inp)},
                {"role": "assistant", "content": json.dumps(out)}
            ]
        })

    return samples

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    # Example: load dataset from CSV
    # Columns: name, city, state, lat, lng, duration, tags, suitable_for, rating, description
    df = pd.read_csv("places.csv")

    # Build 100 synthetic examples
    training_data = build_training_examples(df, n_samples=100)

    # Save as JSONL (fine-tuning ready)
    with open("itinerary_training.jsonl", "w", encoding="utf-8") as f:
        for ex in training_data:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print("✅ Training data saved to itinerary_training.jsonl")
