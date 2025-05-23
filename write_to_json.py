import json

def write_to_json(data, filename):
    """
    Write data to a JSON file
    
    Args:
        data: The data to write (dict, list, etc.)
        filename: The name of the JSON file
    """
    with open(filename, 'w') as json_file:
        json.dump(data, json_file, indent=4)
        
if __name__ == "__main__":
    # Example data
    sample_data = {
        "name": "Agency 360",
        "accounts": [
            {"id": 1, "account_name": "Account A", "cost": 1250.75},
            {"id": 2, "account_name": "Account B", "cost": 850.25}
        ],
        "metrics": {
            "total_cost": 2101.00,
            "average_cost": 1050.50
        }
    }
    
    # Write data to JSON file
    write_to_json(sample_data, "output.json")
    print(f"Data successfully written to output.json")