"""
Serialize data to/from JSON Lines
"""

import json

from django.core.serializers import base
from django.core.serializers.base import DeserializationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.serializers.python import Deserializer as PythonDeserializer
from django.core.serializers.python import Serializer as PythonSerializer


class Serializer(PythonSerializer):
    """Convert a queryset to JSON Lines."""

    internal_use_only = False

    def _init_options(self):
        self._current = None
        self.json_kwargs = self.options.copy()
        self.json_kwargs.pop("stream", None)
        self.json_kwargs.pop("fields", None)
        self.json_kwargs.pop("indent", None)
        self.json_kwargs["separators"] = (",", ": ")
        self.json_kwargs.setdefault("cls", DjangoJSONEncoder)
        self.json_kwargs.setdefault("ensure_ascii", False)

    def start_serialization(self):
        self._init_options()

    def end_object(self, obj):
        # self._current has the field data
        json.dump(self.get_dump_object(obj), self.stream, **self.json_kwargs)
        self.stream.write("\n")
        self._current = None

    def getvalue(self):
        # Grandparent super
        return super(PythonSerializer, self).getvalue()


class Deserializer(base.Deserializer):
    """Deserialize a stream or string of JSON data."""

    def __init__(self, stream_or_string, **options):
        super().__init__(stream_or_string, **options)
        self._iterator = None

    def __iter__(self):
        self._iterator = self._handle_object()
        return self._iterator

    def __next__(self):
        if self._iterator is None:
            self.__iter__()
        return next(self._iterator)

    def _handle_object(self):
        if isinstance(self.stream, bytes):
            self.stream = self.stream.decode()
        if isinstance(self.stream, (bytes, str)):
            self.stream = self.stream.split("\n")

        for line in self.stream:
            if not line.strip():
                continue
            try:
                yield from PythonDeserializer([json.loads(line)], **self.options)
            except (GeneratorExit, DeserializationError):
                raise
            except Exception as exc:
                raise DeserializationError() from exc
