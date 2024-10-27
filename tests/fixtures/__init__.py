import json
import os

def load_json_fixture(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), "r") as f:
        return json.load(f)
