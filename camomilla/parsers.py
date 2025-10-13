import json

from django.http.multipartparser import MultiPartParser as DjangoMultiPartParser
from django.http.multipartparser import MultiPartParserError
from django.conf import settings
from rest_framework import parsers
from rest_framework.exceptions import ParseError


def set_key(data, key, val):
    if isinstance(data, list):
        key = int(key)
        if key < len(data):
            data[key] = val
        else:
            data.append(val)
        return data
    data[key] = val
    return data


def get_key(data, key, default):
    if isinstance(data, list):
        try:
            return data[int(key)]
        except IndexError:
            return default
    return data.get(key, default)


def compile_payload(data, path, value):
    key = path.pop(0)
    if not len(path):
        return set_key(data, key, value)
    default = [] if path[0].isdigit() else {}
    return set_key(data, key, compile_payload(get_key(data, key, default), path, value))


class MultipartJsonParser(parsers.BaseParser):
    media_type = "multipart/form-data"

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        request = parser_context["request"]
        encoding = parser_context.get("encoding", settings.DEFAULT_CHARSET)
        meta = request.META.copy()
        meta["CONTENT_TYPE"] = media_type
        upload_handlers = request.upload_handlers

        try:
            parser = DjangoMultiPartParser(meta, stream, upload_handlers, encoding)
            data, files = parser.parse()
            result = parsers.DataAndFiles(data, files)
            data = {}
            data = json.loads(result.data["data"])
            for key, value in result.files.items():
                data = compile_payload(data, key.split("."), value)
            return data
        except MultiPartParserError as exc:
            raise ParseError("Multipart form parse error - %s" % str(exc))
