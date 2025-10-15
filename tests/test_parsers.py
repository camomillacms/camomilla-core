import io
import json
import pytest
from django.conf import settings
from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from camomilla.parsers import MultipartJsonParser


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_multipart_json_parser_parses_json_and_files(monkeypatch):
    # Prepare multipart data
    json_data = json.dumps(
        {
            "foo": "bar",
            "nested": {"baz": 1},
            "nested_list": [{"qux": "quux"}, {"corge": "grault"}],
        }
    )
    file_content = b"filecontent"
    upload = SimpleUploadedFile("test.txt", file_content, content_type="text/plain")

    # Simulate multipart POST
    factory = RequestFactory()
    data = {
        "data": json_data,
        "nested.file": upload,
        "nested_list.1.file": upload,
    }
    request = factory.post("/", data)
    request.upload_handlers = []
    request.META["CONTENT_TYPE"] = "multipart/form-data; boundary=BoUnDaRy"

    # Patch DjangoMultiPartParser to return our data
    class DummyParser:
        def __init__(self, *a, **kw):
            pass

        def parse(self):
            return (
                {"data": json_data},
                {
                    "nested.file": upload,
                    "nested_list.1.file": upload,
                },
            )

    monkeypatch.setattr("camomilla.parsers.DjangoMultiPartParser", DummyParser)

    parser = MultipartJsonParser()
    parsed = parser.parse(io.BytesIO(b""), "multipart/form-data", {"request": request})
    assert parsed["foo"] == "bar"
    assert parsed["nested"]["baz"] == 1
    assert isinstance(parsed["nested"]["file"], SimpleUploadedFile)
    assert isinstance(parsed["nested_list"][1]["file"], SimpleUploadedFile)
    parsed["nested"]["file"].seek(0)
    assert parsed["nested"]["file"].read() == file_content
    parsed["nested_list"][1]["file"].seek(0)
    assert parsed["nested_list"][1]["file"].read() == file_content


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_multipart_json_parser_handles_parse_error(monkeypatch):
    factory = RequestFactory()
    request = factory.post("/", {})
    request.upload_handlers = []
    request.META["CONTENT_TYPE"] = "multipart/form-data; boundary=BoUnDaRy"

    class DummyParser:
        def __init__(self, *a, **kw):
            pass

        def parse(self):
            from django.http.multipartparser import MultiPartParserError

            raise MultiPartParserError("fail")

    monkeypatch.setattr("camomilla.parsers.DjangoMultiPartParser", DummyParser)
    parser = MultipartJsonParser()
    from rest_framework.exceptions import ParseError

    with pytest.raises(ParseError) as exc:
        parser.parse(io.BytesIO(b""), "multipart/form-data", {"request": request})
    assert "Multipart form parse error" in str(exc.value)
