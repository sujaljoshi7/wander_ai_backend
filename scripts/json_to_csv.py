import json
import csv

def json_to_csv(json_file, csv_file):
    # Load JSON
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Ensure it's a list
    if not isinstance(data, list):
        data = [data]

    # Replace IDs with P_00001 format
    for i, item in enumerate(data, start=1):
        item["id"] = f"P_{i:05d}"

    # Flatten nested fields (entry_fee, open_hours, etc.)
    flattened_data = []
    for item in data:
        flat = item.copy()

        # Handle nested dicts: entry_fee
        if "entry_fee" in flat:
            for k, v in flat["entry_fee"].items():
                flat[f"entry_fee_{k}"] = v
            del flat["entry_fee"]

        # Handle nested dicts: open_hours
        if "open_hours" in flat:
            for k, v in flat["open_hours"].items():
                flat[f"open_hours_{k}"] = v
            del flat["open_hours"]

        # Convert lists (tags, best_months, famous_for) into comma-separated strings
        for field in ["tags", "best_months", "famous_for"]:
            if field in flat and isinstance(flat[field], list):
                flat[field] = ", ".join(flat[field])

        flattened_data.append(flat)

    # Get CSV headers
    headers = set()
    for item in flattened_data:
        headers.update(item.keys())
    headers = list(headers)

    # Write CSV
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(flattened_data)

    print(f"✅ Successfully converted {json_file} → {csv_file}")

# Example usage
json_to_csv("../Data/places.json", "places.csv")
