from django.db import NotSupportedError
from django.db.models.constants import LOOKUP_SEP
from django.db.models.expressions import Func, Value
from django.db.models.fields.json import compile_json_path
from django.db.models.functions import Cast


class JSONSet(Func):
    def __init__(self, expression, output_field=None, **fields):
        if not fields:
            raise TypeError("JSONSet requires at least one key-value pair to be set.")
        self.fields = fields
        super().__init__(expression, output_field=output_field)

    def as_sql(
        self,
        compiler,
        connection,
        function=None,
        template=None,
        arg_joiner=None,
        **extra_context,
    ):
        if not connection.features.supports_partial_json_update:
            raise NotSupportedError(
                "JSONSet() is not supported on this database backend."
            )
        copy = self.copy()
        new_source_expression = copy.get_source_expressions()

        for key, value in self.fields.items():
            key_paths = key.split(LOOKUP_SEP)
            key_paths_join = compile_json_path(key_paths)
            new_source_expression.extend(
                (
                    Value(key_paths_join),
                    # Use Value to serialize the data to string,
                    # then use Cast to ensure the string is treated as JSON.
                    Cast(
                        Value(value, output_field=self.output_field),
                        output_field=self.output_field,
                    ),
                )
            )

        copy.set_source_expressions(new_source_expression)

        return super(JSONSet, copy).as_sql(
            compiler,
            connection,
            function="JSON_SET",
            **extra_context,
        )

    def as_postgresql(self, compiler, connection, **extra_context):
        copy = self.copy()

        all_items = list(self.fields.items())
        key, value = all_items[0]
        rest = all_items[1:]

        # JSONB_SET does not support arbitrary number of arguments,
        # so convert multiple updates into recursive calls.
        if rest:
            copy.fields = {key: value}
            return JSONSet(copy, **dict(rest)).as_postgresql(
                compiler, connection, **extra_context
            )
        else:
            new_source_expression = copy.get_source_expressions()
            key_paths = key.split(LOOKUP_SEP)
            key_paths_join = ",".join(key_paths)
            new_source_expression.extend(
                (
                    Value(f"{{{key_paths_join}}}"),
                    Value(value, output_field=self.output_field),
                )
            )
            copy.set_source_expressions(new_source_expression)
        return super(JSONSet, copy).as_sql(
            compiler, connection, function="JSONB_SET", **extra_context
        )

    def as_oracle(self, compiler, connection, **extra_context):
        if not connection.features.supports_partial_json_update:
            raise NotSupportedError(
                "JSONSet() is not supported on this database backend."
            )
        copy = self.copy()

        all_items = list(self.fields.items())
        key, value = all_items[0]
        rest = all_items[1:]

        # JSON_TRANSFORM does not support arbitrary number of arguments,
        # so convert multiple updates into recursive calls.
        if rest:
            copy.fields = {key: value}
            return JSONSet(copy, **dict(rest)).as_oracle(
                compiler, connection, **extra_context
            )
        else:
            new_source_expression = copy.get_source_expressions()
            key_paths = key.split(LOOKUP_SEP)
            key_paths_join = compile_json_path(key_paths)
            new_source_expression.extend(
                (Value(value, output_field=self.output_field),)
            )
            copy.set_source_expressions(new_source_expression)

        class ArgJoiner:
            def join(self, args):
                # Interpolate the JSON path directly to the query string, because
                # Oracle does not support passing the JSON path using parameter binding.
                return f"{args[0]}, SET '{key_paths_join}' = {args[-1]} FORMAT JSON"

        return super(JSONSet, copy).as_sql(
            compiler,
            connection,
            function="JSON_TRANSFORM",
            arg_joiner=ArgJoiner(),
            **extra_context,
        )


class JSONRemove(Func):
    def __init__(self, expression, *paths):
        if not paths:
            raise TypeError("JSONRemove requires at least one path to remove")
        self.paths = paths
        super().__init__(expression)

    def as_sql(
        self,
        compiler,
        connection,
        function=None,
        template=None,
        arg_joiner=None,
        **extra_context,
    ):
        if not connection.features.supports_partial_json_update:
            raise NotSupportedError(
                "JSONRemove() is not supported on this database backend."
            )
        copy = self.copy()
        new_source_expression = copy.get_source_expressions()

        for path in self.paths:
            key_paths = path.split(LOOKUP_SEP)
            key_paths_join = compile_json_path(key_paths)
            new_source_expression.append(Value(key_paths_join))

        copy.set_source_expressions(new_source_expression)

        return super(JSONRemove, copy).as_sql(
            compiler,
            connection,
            function="JSON_REMOVE",
            **extra_context,
        )

    def as_postgresql(self, compiler, connection, **extra_context):
        copy = self.copy()
        path, *rest = self.paths

        if rest:
            copy.paths = (path,)
            return JSONRemove(copy, *rest).as_postgresql(
                compiler, connection, **extra_context
            )
        else:
            new_source_expression = copy.get_source_expressions()
            key_paths = path.split(LOOKUP_SEP)
            key_paths_join = ",".join(key_paths)
            new_source_expression.append(Value(f"{{{key_paths_join}}}"))
            copy.set_source_expressions(new_source_expression)

        return super(JSONRemove, copy).as_sql(
            compiler,
            connection,
            template="%(expressions)s",
            arg_joiner="#- ",
            **extra_context,
        )

    def as_oracle(self, compiler, connection, **extra_context):
        if not connection.features.supports_partial_json_update:
            raise NotSupportedError(
                "JSONRemove() is not supported on this database backend."
            )

        copy = self.copy()

        all_items = self.paths
        path, *rest = all_items

        if rest:
            copy.paths = (path,)
            return JSONRemove(copy, *rest).as_oracle(
                compiler, connection, **extra_context
            )
        else:
            key_paths = path.split(LOOKUP_SEP)
            key_paths_join = compile_json_path(key_paths)

        class ArgJoiner:
            def join(self, args):
                return f"{args[0]}, REMOVE '{key_paths_join}'"

        return super(JSONRemove, copy).as_sql(
            compiler,
            connection,
            function="JSON_TRANSFORM",
            arg_joiner=ArgJoiner(),
            **extra_context,
        )
