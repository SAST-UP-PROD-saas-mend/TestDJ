"""
Serialize data to/from JSON
"""

import datetime
import decimal
import json
import uuid

from django.core.serializers import base
from django.core.serializers.base import DeserializationError
from django.core.serializers.python import Deserializer as PythonDeserializer
from django.core.serializers.python import Serializer as PythonSerializer
from django.utils.duration import duration_iso_string
from django.utils.functional import Promise
from django.utils.timezone import is_aware


class Serializer(PythonSerializer):
    """Convert a queryset to JSON."""

    internal_use_only = False

    def _init_options(self):
        self._current = None
        self.json_kwargs = self.options.copy()
        self.json_kwargs.pop("stream", None)
        self.json_kwargs.pop("fields", None)
        if self.options.get("indent"):
            # Prevent trailing spaces
            self.json_kwargs["separators"] = (",", ": ")
        self.json_kwargs.setdefault("cls", DjangoJSONEncoder)
        self.json_kwargs.setdefault("ensure_ascii", False)

    def start_serialization(self):
        self._init_options()
        self.stream.write("[")

    def end_serialization(self):
        if self.options.get("indent"):
            self.stream.write("\n")
        self.stream.write("]")
        if self.options.get("indent"):
            self.stream.write("\n")

    def end_object(self, obj):
        # self._current has the field data
        indent = self.options.get("indent")
        if not self.first:
            self.stream.write(",")
            if not indent:
                self.stream.write(" ")
        if indent:
            self.stream.write("\n")
        json.dump(self.get_dump_object(obj), self.stream, **self.json_kwargs)
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
        if not isinstance(self.stream, (bytes, str)):
            self.stream = self.stream.read()
        if isinstance(self.stream, bytes):
            self.stream = self.stream.decode()
        try:
            objects = json.loads(self.stream)
            yield from PythonDeserializer(objects, **self.options)
        except (GeneratorExit, DeserializationError):
            raise
        except Exception as exc:
            raise DeserializationError() from exc


class DjangoJSONEncoder(json.JSONEncoder):
    """
    JSONEncoder subclass that knows how to encode date/time, decimal types, and
    UUIDs.
    """

    def default(self, o):
        # See "Date Time String Format" in the ECMA-262 specification.
        if isinstance(o, datetime.datetime):
            r = o.isoformat()
            if o.microsecond:
                r = r[:23] + r[26:]
            if r.endswith("+00:00"):
                r = r.removesuffix("+00:00") + "Z"
            return r
        elif isinstance(o, datetime.date):
            return o.isoformat()
        elif isinstance(o, datetime.time):
            if is_aware(o):
                raise ValueError("JSON can't represent timezone-aware times.")
            r = o.isoformat()
            if o.microsecond:
                r = r[:12]
            return r
        elif isinstance(o, datetime.timedelta):
            return duration_iso_string(o)
        elif isinstance(o, (decimal.Decimal, uuid.UUID, Promise)):
            return str(o)
        else:
            return super().default(o)
