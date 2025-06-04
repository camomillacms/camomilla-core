import json
import os
from django.core.files.uploadedfile import SimpleUploadedFile


def load_json_fixture(filename):
    with open(os.path.join(os.path.dirname(__file__), "json", filename), "r") as f:
        return json.load(f)


def load_asset(filename):
    with open(os.path.join(os.path.dirname(__file__), "assets", filename), "rb") as f:
        up_file = SimpleUploadedFile(filename, f.read())
        return up_file
