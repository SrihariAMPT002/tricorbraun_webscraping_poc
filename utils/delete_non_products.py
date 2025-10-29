import json

# Set of product IDs to delete
codes_to_delete = {
    "#v4770B71",
    "#v4700B01",
    "#v4770B61",
    "#v4699B31",
    "#v4699B41",
    "#v4699B01",
    "#v4232B01-B",
    "#v4232B01",
    "#v4225B01",
    "#v4001B73",
    "#v4001B03-B",
    "#v3522B01-B",
    "#v4771B01-B",
    "#v4700B01-B",
    "#v4699B01-B",
    "#v4998B84BLK",
    "#v4701B01-B",
    "#v5016B44-B",
    "#v5016B44",
    "#vCJUG",
    "#vBC4METAL",
    "#vAB4",
    "#vAB1",
    "#vCB16",
    "#vROL",
    "#v9888B01",
    "#v9021B01",
    "#v8624B01",
    "#v6001B01",
    "#v4900B01",
    "#v9888B01-B",
    "#v9021B01-B",
    "#v8624B01-B",
    "#v5014B44-B",
    "#v4998B65",
    "#v4999B63",
    "#v4902B21",
    "#v4902B01-B",
    "#v4900B01-B",
    "#v4833B01-B",
}

# Input and output file paths
input_file = "demo_batch_data/berlin_new_data_normalised.json"
output_file = "demo_batch_data/berlin_new_data_normalised.json"

# Load JSON data
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# Ensure the data is a list
if not isinstance(data, list):
    raise ValueError("Expected a JSON array at the root of the file")

# Filter items
filtered_data = []
for item in data:
    product_id = item.get("product_id")
    if product_id not in codes_to_delete:
        filtered_data.append(item)

# Save the filtered result
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(filtered_data, f, ensure_ascii=False, indent=2)

print(f"Filtered data saved to {output_file}")
print(f"Removed {len(data) - len(filtered_data)} matching items.")
