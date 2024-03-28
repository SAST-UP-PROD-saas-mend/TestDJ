import unittest

from django.db import connection
from django.db.models.query import MAX_GET_RESULTS
from django.db.models.query_utils import PathInfo
from django.db.models.sql import Query
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from .models import Comment, Tenant, User


def get_constraints(table):
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, table)


class BaseTestCase(TestCase):
    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create()
        cls.user = User.objects.create(tenant=cls.tenant, id=1)
        cls.comment = Comment.objects.create(tenant=cls.tenant, id=1, user=cls.user)


class CompositePKTests(BaseTestCase):
    def test_fields(self):
        self.assertIsInstance(self.tenant.pk, int)
        self.assertGreater(self.tenant.id, 0)
        self.assertEqual(self.tenant.pk, self.tenant.id)

        self.assertIsInstance(self.user.id, int)
        self.assertGreater(self.user.id, 0)
        self.assertEqual(self.user.tenant_id, self.tenant.id)
        self.assertEqual(self.user.pk, (self.user.tenant_id, self.user.id))
        self.assertEqual(self.user.composite_pk, self.user.pk)

        self.assertIsInstance(self.comment.id, int)
        self.assertGreater(self.comment.id, 0)
        self.assertEqual(self.comment.user_id, self.user.id)
        self.assertEqual(self.comment.tenant_id, self.tenant.id)
        self.assertEqual(self.comment.pk, (self.comment.tenant_id, self.comment.id))
        self.assertEqual(self.comment.composite_pk, self.comment.pk)

    def test_pk_updated_if_field_updated(self):
        user = User.objects.get(pk=self.user.pk)
        self.assertEqual(user.pk, (self.tenant.id, self.user.id))
        user.tenant_id = 9831
        self.assertEqual(user.pk, (9831, self.user.id))
        user.id = 4321
        self.assertEqual(user.pk, (9831, 4321))
        user.pk = (9132, 3521)
        self.assertEqual(user.tenant_id, 9132)
        self.assertEqual(user.id, 3521)

    def test_composite_pk_in_fields(self):
        user_fields = {f.name for f in User._meta.get_fields()}
        self.assertEqual(user_fields, {"id", "tenant", "composite_pk"})

        comment_fields = {f.name for f in Comment._meta.get_fields()}
        self.assertEqual(
            comment_fields, {"id", "tenant", "user_id", "user", "composite_pk"}
        )

    def test_error_on_pk_conflict(self):
        with self.assertRaises(Exception):
            User.objects.create(tenant=self.tenant, id=self.user.id)
        with self.assertRaises(Exception):
            Comment.objects.create(tenant=self.tenant, id=self.comment.id)

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific test")
    def test_pk_constraints_in_postgresql(self):
        user_constraints = get_constraints(User._meta.db_table)
        user_pk = user_constraints["composite_pk_user_pkey"]
        self.assertEqual(user_pk["columns"], ["tenant_id", "id"])
        self.assertTrue(user_pk["primary_key"])

        comment_constraints = get_constraints(Comment._meta.db_table)
        comment_pk = comment_constraints["composite_pk_comment_pkey"]
        self.assertEqual(comment_pk["columns"], ["tenant_id", "id"])
        self.assertTrue(comment_pk["primary_key"])

    @unittest.skipUnless(connection.vendor == "sqlite", "SQLite specific test")
    def test_pk_constraints_in_sqlite(self):
        user_constraints = get_constraints(User._meta.db_table)
        user_pk = user_constraints["__primary__"]
        self.assertEqual(user_pk["columns"], ["tenant_id", "id"])
        self.assertTrue(user_pk["primary_key"])

        comment_constraints = get_constraints(Comment._meta.db_table)
        comment_pk = comment_constraints["__primary__"]
        self.assertEqual(comment_pk["columns"], ["tenant_id", "id"])
        self.assertTrue(comment_pk["primary_key"])


class CompositePKDeleteTests(BaseTestCase):
    """
    Test the .delete() method of composite_pk models.
    """

    def test_delete_tenant_by_pk(self):
        t = Tenant._meta.db_table
        u = User._meta.db_table
        c = Comment._meta.db_table

        with CaptureQueriesContext(connection) as context:
            result = Tenant.objects.filter(pk=self.tenant.pk).delete()

        self.assertEqual(
            result,
            (
                3,
                {
                    "composite_pk.Comment": 1,
                    "composite_pk.User": 1,
                    "composite_pk.Tenant": 1,
                },
            ),
        )

        self.assertFalse(Tenant.objects.filter(id=self.tenant.id).exists())
        self.assertFalse(User.objects.filter(id=self.user.id).exists())
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

        self.assertEqual(len(context.captured_queries), 6)
        self.assertEqual(
            context.captured_queries[0]["sql"],
            f'SELECT "{t}"."id" FROM "{t}" WHERE "{t}"."id" = {self.tenant.id}',
        )
        self.assertEqual(
            context.captured_queries[1]["sql"],
            f'SELECT "{u}"."tenant_id", "{u}"."id" '
            f'FROM "{u}" '
            f'WHERE "{u}"."tenant_id" IN ({self.tenant.id})',
        )
        self.assertEqual(
            context.captured_queries[2]["sql"],
            f'DELETE FROM "{c}" '
            f'WHERE ("{c}"."tenant_id" = {self.tenant.id} '
            f'AND "{c}"."user_id" = {self.user.id})',
        )
        self.assertEqual(
            context.captured_queries[3]["sql"],
            f'DELETE FROM "{c}" WHERE "{c}"."tenant_id" IN ({self.tenant.id})',
        )
        self.assertEqual(
            context.captured_queries[4]["sql"],
            f'DELETE FROM "{u}" '
            f'WHERE ("{u}"."tenant_id" = {self.tenant.id} '
            f'AND "{u}"."id" = {self.user.id})',
        )
        self.assertEqual(
            context.captured_queries[5]["sql"],
            f'DELETE FROM "{t}" WHERE "{t}"."id" IN ({self.tenant.id})',
        )

    def test_delete_user_by_id(self):
        u = User._meta.db_table
        c = Comment._meta.db_table

        with CaptureQueriesContext(connection) as context:
            result = User.objects.filter(id=self.user.id).delete()

        self.assertEqual(
            result, (2, {"composite_pk.User": 1, "composite_pk.Comment": 1})
        )

        self.assertTrue(Tenant.objects.filter(id=self.tenant.id).exists())
        self.assertFalse(User.objects.filter(id=self.user.id).exists())
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

        self.assertEqual(len(context.captured_queries), 3)
        self.assertEqual(
            context.captured_queries[0]["sql"],
            f'SELECT "{u}"."tenant_id", "{u}"."id" '
            f'FROM "{u}" '
            f'WHERE "{u}"."id" = {self.user.id}',
        )
        self.assertEqual(
            context.captured_queries[1]["sql"],
            f'DELETE FROM "{c}" '
            f'WHERE ("{c}"."tenant_id" = {self.tenant.id} '
            f'AND "{c}"."user_id" = {self.user.id})',
        )
        self.assertEqual(
            context.captured_queries[2]["sql"],
            f'DELETE FROM "{u}" '
            f'WHERE ("{u}"."tenant_id" = {self.tenant.id} '
            f'AND "{u}"."id" = {self.user.id})',
        )

    def test_delete_user_by_pk(self):
        u = User._meta.db_table
        c = Comment._meta.db_table

        with CaptureQueriesContext(connection) as context:
            result = User.objects.filter(pk=self.user.pk).delete()

        self.assertEqual(
            result, (2, {"composite_pk.User": 1, "composite_pk.Comment": 1})
        )

        self.assertTrue(Tenant.objects.filter(id=self.tenant.id).exists())
        self.assertFalse(User.objects.filter(id=self.user.id).exists())
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

        self.assertEqual(len(context.captured_queries), 3)
        self.assertEqual(
            context.captured_queries[0]["sql"],
            f'SELECT "{u}"."tenant_id", "{u}"."id" '
            f'FROM "{u}" '
            f'WHERE ("{u}"."tenant_id" = {self.tenant.id} '
            f'AND "{u}"."id" = {self.user.id})',
        )
        self.assertEqual(
            context.captured_queries[1]["sql"],
            f'DELETE FROM "{c}" '
            f'WHERE ("{c}"."tenant_id" = {self.tenant.id} '
            f'AND "{c}"."user_id" = {self.user.id})',
        )
        self.assertEqual(
            context.captured_queries[2]["sql"],
            f'DELETE FROM "{u}" '
            f'WHERE ("{u}"."tenant_id" = {self.tenant.id} '
            f'AND "{u}"."id" = {self.user.id})',
        )


class CompositePKGetTests(BaseTestCase):
    """
    Test the .get() method of composite_pk models.
    """

    def test_get_tenant_by_pk(self):
        t = Tenant._meta.db_table
        test_cases = [
            {"id": self.tenant.id},
            {"pk": self.tenant.pk},
        ]

        for lookup in test_cases:
            with self.subTest(lookup=lookup):
                with CaptureQueriesContext(connection) as context:
                    obj = Tenant.objects.get(**lookup)

                self.assertEqual(obj, self.tenant)
                self.assertEqual(len(context.captured_queries), 1)
                self.assertEqual(
                    context.captured_queries[0]["sql"],
                    f'SELECT "{t}"."id" '
                    f'FROM "{t}" '
                    f'WHERE "{t}"."id" = {self.tenant.id} '
                    f"LIMIT {MAX_GET_RESULTS}",
                )

    def test_get_user_by_pk(self):
        u = User._meta.db_table
        test_cases = [
            {"pk": (self.tenant.id, self.user.id)},
            {"pk": self.user.pk},
        ]

        for lookup in test_cases:
            with self.subTest(lookup=lookup):
                with CaptureQueriesContext(connection) as context:
                    obj = User.objects.get(**lookup)

                self.assertEqual(obj, self.user)
                self.assertEqual(len(context.captured_queries), 1)
                self.assertEqual(
                    context.captured_queries[0]["sql"],
                    f'SELECT "{u}"."tenant_id", "{u}"."id" '
                    f'FROM "{u}" '
                    f'WHERE ("{u}"."tenant_id" = {self.tenant.id} '
                    f'AND "{u}"."id" = {self.user.id}) '
                    f"LIMIT {MAX_GET_RESULTS}",
                )

    def test_get_user_by_field(self):
        u = User._meta.db_table
        test_cases = [
            ({"id": self.user.id}, "id", self.user.id),
            ({"tenant": self.tenant}, "tenant_id", self.tenant.id),
            ({"tenant_id": self.tenant.id}, "tenant_id", self.tenant.id),
            ({"tenant__id": self.tenant.id}, "tenant_id", self.tenant.id),
            ({"tenant__pk": self.tenant.id}, "tenant_id", self.tenant.id),
        ]

        for lookup, column, value in test_cases:
            with self.subTest(lookup=lookup, column=column, value=value):
                with CaptureQueriesContext(connection) as context:
                    obj = User.objects.get(**lookup)

                self.assertEqual(obj, self.user)
                self.assertEqual(len(context.captured_queries), 1)
                self.assertEqual(
                    context.captured_queries[0]["sql"],
                    f'SELECT "{u}"."tenant_id", "{u}"."id" '
                    f'FROM "{u}" '
                    f'WHERE "{u}"."{column}" = {value} '
                    f"LIMIT {MAX_GET_RESULTS}",
                )

    def test_get_comment_by_pk(self):
        c = Comment._meta.db_table

        with CaptureQueriesContext(connection) as context:
            obj = Comment.objects.get(pk=(self.tenant.id, self.comment.id))

        self.assertEqual(obj, self.comment)
        self.assertEqual(len(context.captured_queries), 1)
        self.assertEqual(
            context.captured_queries[0]["sql"],
            f'SELECT "{c}"."tenant_id", "{c}"."id", "{c}"."user_id" '
            f'FROM "{c}" '
            f'WHERE ("{c}"."tenant_id" = {self.tenant.id} '
            f'AND "{c}"."id" = {self.comment.id}) '
            f"LIMIT {MAX_GET_RESULTS}",
        )

    def test_get_comment_by_field(self):
        c = Comment._meta.db_table
        test_cases = [
            ({"id": self.comment.id}, "id", self.comment.id),
            ({"user_id": self.user.id}, "user_id", self.user.id),
            ({"user__id": self.user.id}, "user_id", self.user.id),
            ({"tenant": self.tenant}, "tenant_id", self.tenant.id),
            ({"tenant_id": self.tenant.id}, "tenant_id", self.tenant.id),
            ({"tenant__id": self.tenant.id}, "tenant_id", self.tenant.id),
            ({"tenant__pk": self.tenant.id}, "tenant_id", self.tenant.id),
        ]

        for lookup, column, value in test_cases:
            with self.subTest(lookup=lookup, column=column, value=value):
                with CaptureQueriesContext(connection) as context:
                    obj = Comment.objects.get(**lookup)

                self.assertEqual(obj, self.comment)
                self.assertEqual(len(context.captured_queries), 1)
                self.assertEqual(
                    context.captured_queries[0]["sql"],
                    f'SELECT "{c}"."tenant_id", "{c}"."id", "{c}"."user_id" '
                    f'FROM "{c}" '
                    f'WHERE "{c}"."{column}" = {value} '
                    f"LIMIT {MAX_GET_RESULTS}",
                )

    def test_get_comment_by_user(self):
        c = Comment._meta.db_table

        with CaptureQueriesContext(connection) as context:
            obj = Comment.objects.get(user=self.user)

        self.assertEqual(obj, self.comment)
        self.assertEqual(len(context.captured_queries), 1)
        self.assertEqual(
            context.captured_queries[0]["sql"],
            f'SELECT "{c}"."tenant_id", "{c}"."id", "{c}"."user_id" '
            f'FROM "{c}" '
            f'WHERE ("{c}"."tenant_id" = {self.tenant.id} '
            f'AND "{c}"."user_id" = {self.user.id}) '
            f"LIMIT {MAX_GET_RESULTS}",
        )

    def test_get_comment_by_user_pk(self):
        c = Comment._meta.db_table
        u = User._meta.db_table

        with CaptureQueriesContext(connection) as context:
            obj = Comment.objects.get(user__pk=self.user.pk)

        self.assertEqual(obj, self.comment)
        self.assertEqual(len(context.captured_queries), 1)
        self.assertEqual(
            context.captured_queries[0]["sql"],
            f'SELECT "{c}"."tenant_id", "{c}"."id", "{c}"."user_id" '
            f'FROM "{c}" '
            f'INNER JOIN "{u}" ON ("{c}"."tenant_id" = "{u}"."tenant_id" '
            f'AND "{c}"."user_id" = "{u}"."id") '
            f'WHERE ("{u}"."tenant_id" = {self.tenant.id} '
            f'AND "{u}"."id" = {self.user.id}) '
            f"LIMIT {MAX_GET_RESULTS}",
        )


class CompositePKCreateTests(TestCase):
    """
    Test the .create(), .save(), .bulk_create() methods of composite_pk models.
    """

    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create()

    @unittest.skipUnless(connection.vendor == "sqlite", "SQLite specific test")
    def test_create_user_in_sqlite(self):
        u = User._meta.db_table
        test_cases = [
            ({"tenant": self.tenant, "id": 2412}, 2412),
            ({"tenant_id": self.tenant.id, "id": 5316}, 5316),
            ({"pk": (self.tenant.id, 7424)}, 7424),
        ]

        for fields, user_id in test_cases:
            with self.subTest(fields=fields, user_id=user_id):
                with CaptureQueriesContext(connection) as context:
                    obj = User.objects.create(**fields)

                self.assertEqual(obj.tenant_id, self.tenant.id)
                self.assertEqual(obj.id, user_id)
                self.assertEqual(obj.pk, (self.tenant.id, user_id))
                self.assertEqual(len(context.captured_queries), 1)
                self.assertEqual(
                    context.captured_queries[0]["sql"],
                    f'INSERT INTO "{u}" ("tenant_id", "id") '
                    f"VALUES ({self.tenant.id}, {user_id})",
                )

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific test")
    def test_create_user_in_postgresql(self):
        u = User._meta.db_table
        test_cases = [
            ({"tenant": self.tenant, "id": 5231}, 5231),
            ({"tenant_id": self.tenant.id, "id": 6123}, 6123),
            ({"pk": (self.tenant.id, 3513)}, 3513),
        ]

        for fields, user_id in test_cases:
            with self.subTest(fields=fields, user_id=user_id):
                with CaptureQueriesContext(connection) as context:
                    obj = User.objects.create(**fields)

                self.assertEqual(obj.tenant_id, self.tenant.id)
                self.assertEqual(obj.id, user_id)
                self.assertEqual(obj.pk, (self.tenant.id, user_id))
                self.assertEqual(len(context.captured_queries), 1)
                self.assertEqual(
                    context.captured_queries[0]["sql"],
                    f'INSERT INTO "{u}" ("tenant_id", "id") '
                    f"VALUES ({self.tenant.id}, {user_id}) "
                    f'RETURNING "{u}"."id"',
                )

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific test")
    def test_create_user_with_autofield_in_postgresql(self):
        u = User._meta.db_table
        test_cases = [
            {"tenant": self.tenant},
            {"tenant_id": self.tenant.id},
        ]

        for fields in test_cases:
            with CaptureQueriesContext(connection) as context:
                obj = User.objects.create(**fields)

            self.assertEqual(obj.tenant_id, self.tenant.id)
            self.assertIsInstance(obj.id, int)
            self.assertGreater(obj.id, 0)
            self.assertEqual(obj.pk, (self.tenant.id, obj.id))
            self.assertEqual(len(context.captured_queries), 1)
            self.assertEqual(
                context.captured_queries[0]["sql"],
                f'INSERT INTO "{u}" ("tenant_id") '
                f"VALUES ({self.tenant.id}) "
                f'RETURNING "{u}"."id"',
            )

    def test_save_user(self):
        user = User(tenant=self.tenant, id=9241)
        user.save()
        self.assertEqual(user.tenant_id, self.tenant.id)
        self.assertEqual(user.tenant, self.tenant)
        self.assertEqual(user.id, 9241)
        self.assertEqual(user.pk, (self.tenant.id, 9241))

    @unittest.skipUnless(connection.vendor == "sqlite", "SQLite specific test")
    def test_bulk_create_users_in_sqlite(self):
        u = User._meta.db_table
        objs = [
            User(tenant=self.tenant, id=8291),
            User(tenant_id=self.tenant.id, id=4021),
            User(pk=(self.tenant.id, 8214)),
        ]

        with CaptureQueriesContext(connection) as context:
            result = User.objects.bulk_create(objs)

        obj_1, obj_2, obj_3 = result
        self.assertEqual(obj_1.tenant_id, self.tenant.id)
        self.assertEqual(obj_1.id, 8291)
        self.assertEqual(obj_1.pk, (obj_1.tenant_id, obj_1.id))
        self.assertEqual(obj_2.tenant_id, self.tenant.id)
        self.assertEqual(obj_2.id, 4021)
        self.assertEqual(obj_2.pk, (obj_2.tenant_id, obj_2.id))
        self.assertEqual(obj_3.tenant_id, self.tenant.id)
        self.assertEqual(obj_3.id, 8214)
        self.assertEqual(obj_3.pk, (obj_3.tenant_id, obj_3.id))
        self.assertEqual(len(context.captured_queries), 1)
        self.assertEqual(
            context.captured_queries[0]["sql"],
            f'INSERT INTO "{u}" ("tenant_id", "id") '
            f"VALUES ({self.tenant.id}, 8291), ({self.tenant.id}, 4021), "
            f"({self.tenant.id}, 8214)",
        )

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific test")
    def test_bulk_create_users_in_postgresql(self):
        u = User._meta.db_table
        objs = [
            User(tenant=self.tenant, id=8361),
            User(tenant_id=self.tenant.id, id=2819),
            User(pk=(self.tenant.id, 9136)),
            User(tenant=self.tenant),
            User(tenant_id=self.tenant.id),
        ]

        with CaptureQueriesContext(connection) as context:
            result = User.objects.bulk_create(objs)

        obj_1, obj_2, obj_3, obj_4, obj_5 = result
        self.assertEqual(obj_1.tenant_id, self.tenant.id)
        self.assertEqual(obj_1.id, 8361)
        self.assertEqual(obj_1.pk, (obj_1.tenant_id, obj_1.id))
        self.assertEqual(obj_2.tenant_id, self.tenant.id)
        self.assertEqual(obj_2.id, 2819)
        self.assertEqual(obj_2.pk, (obj_2.tenant_id, obj_2.id))
        self.assertEqual(obj_3.tenant_id, self.tenant.id)
        self.assertEqual(obj_3.id, 9136)
        self.assertEqual(obj_3.pk, (obj_3.tenant_id, obj_3.id))
        self.assertEqual(obj_4.tenant_id, self.tenant.id)
        self.assertIsInstance(obj_4.id, int)
        self.assertGreater(obj_4.id, 0)
        self.assertEqual(obj_4.pk, (obj_4.tenant_id, obj_4.id))
        self.assertEqual(obj_5.tenant_id, self.tenant.id)
        self.assertIsInstance(obj_5.id, int)
        self.assertGreater(obj_5.id, obj_4.id)
        self.assertEqual(obj_5.pk, (obj_5.tenant_id, obj_5.id))
        self.assertEqual(len(context.captured_queries), 2)
        self.assertEqual(
            context.captured_queries[0]["sql"],
            f'INSERT INTO "{u}" ("tenant_id", "id") '
            f"VALUES ({self.tenant.id}, 8361), ({self.tenant.id}, 2819), "
            f"({self.tenant.id}, 9136) "
            f'RETURNING "{u}"."id"',
        )
        self.assertEqual(
            context.captured_queries[1]["sql"],
            f'INSERT INTO "{u}" ("tenant_id") '
            f"VALUES ({self.tenant.id}), ({self.tenant.id}) "
            f'RETURNING "{u}"."id"',
        )


class CompositePKUpdateTests(BaseTestCase):
    """
    Test the .update(), .save(), .bulk_update() methods of composite_pk models.
    """

    def test_update_user(self):
        u = User._meta.db_table

        with CaptureQueriesContext(connection) as context:
            result = User.objects.filter(pk=self.user.pk).update(id=8341)

        self.assertEqual(result, 1)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertEqual(User.objects.all().count(), 1)
        user = User.objects.get(pk=(self.tenant.id, 8341))
        self.assertEqual(user.tenant, self.tenant)
        self.assertEqual(user.tenant_id, self.tenant.id)
        self.assertEqual(user.id, 8341)
        self.assertEqual(len(context.captured_queries), 1)
        self.assertEqual(
            context.captured_queries[0]["sql"],
            f'UPDATE "{u}" '
            'SET "id" = 8341 '
            f'WHERE ("{u}"."tenant_id" = {self.tenant.id} '
            f'AND "{u}"."id" = {self.user.id})',
        )

    def test_save_comment(self):
        c = Comment._meta.db_table
        comment = Comment.objects.get(pk=self.comment.pk)
        comment.user = User.objects.create(tenant=self.tenant, id=8214)

        with CaptureQueriesContext(connection) as context:
            comment.save()

        self.assertEqual(Comment.objects.all().count(), 1)
        self.assertEqual(len(context.captured_queries), 1)
        self.assertEqual(
            context.captured_queries[0]["sql"],
            f'UPDATE "{c}" '
            f'SET "tenant_id" = {self.tenant.id}, "id" = {self.comment.id}, '
            f'"user_id" = 8214 '
            f'WHERE ("{c}"."tenant_id" = {self.tenant.id} '
            f'AND "{c}"."id" = {self.comment.id})',
        )

    @unittest.skipUnless(connection.vendor == "sqlite", "SQLite specific test")
    def test_bulk_update_comments_in_sqlite(self):
        c = Comment._meta.db_table
        user_1 = User.objects.create(pk=(self.tenant.id, 1352))
        user_2 = User.objects.create(pk=(self.tenant.id, 9314))
        comment_1 = Comment.objects.create(pk=(self.tenant.id, 1934), user=user_1)
        comment_2 = Comment.objects.create(pk=(self.tenant.id, 8314), user=user_1)
        comment_3 = Comment.objects.create(pk=(self.tenant.id, 9214), user=user_1)
        comment_1.user = user_2
        comment_2.user = user_2
        comment_3.user = user_2
        comments = [comment_1, comment_2, comment_3]

        with CaptureQueriesContext(connection) as context:
            result = Comment.objects.bulk_update(comments, ["user_id"])

        self.assertEqual(result, 3)
        self.assertEqual(len(context.captured_queries), 1)
        self.assertEqual(
            context.captured_queries[0]["sql"],
            f'UPDATE "{c}" '
            f'SET "user_id" = CASE '
            f'WHEN (("{c}"."tenant_id" = {self.tenant.id} AND "{c}"."id" = 1934)) '
            f"THEN 9314 "
            f'WHEN (("{c}"."tenant_id" = {self.tenant.id} AND "{c}"."id" = 8314)) '
            f"THEN 9314 "
            f'WHEN (("{c}"."tenant_id" = {self.tenant.id} AND "{c}"."id" = 9214)) '
            f"THEN 9314 ELSE NULL END "
            f'WHERE (("{c}"."tenant_id" = {self.tenant.id} AND "{c}"."id" = 1934) '
            f'OR ("{c}"."tenant_id" = {self.tenant.id} AND "{c}"."id" = 8314) '
            f'OR ("{c}"."tenant_id" = {self.tenant.id} AND "{c}"."id" = 9214))',
        )


class CompositePKFilterTests(BaseTestCase):
    """
    Test the .filter() method of composite_pk models.
    """

    def test_filter_and_count_user_by_pk(self):
        u = User._meta.db_table
        test_cases = [
            {"pk": self.user.pk},
            {"pk": (self.tenant.id, self.user.id)},
        ]

        for lookup in test_cases:
            with self.subTest(lookup=lookup):
                with CaptureQueriesContext(connection) as context:
                    result = User.objects.filter(**lookup).count()

                self.assertEqual(result, 1)
                self.assertEqual(len(context.captured_queries), 1)
                self.assertEqual(
                    context.captured_queries[0]["sql"],
                    'SELECT COUNT(*) AS "__count" '
                    f'FROM "{u}" '
                    f'WHERE ("{u}"."tenant_id" = {self.tenant.id} '
                    f'AND "{u}"."id" = {self.user.id})',
                )


class NamesToPathTests(TestCase):
    def test_id(self):
        query = Query(User)
        path, final_field, targets, rest = query.names_to_path(["id"], User._meta)

        self.assertEqual(path, [])
        self.assertEqual(final_field, User._meta.get_field("id"))
        self.assertEqual(targets, (User._meta.get_field("id"),))
        self.assertEqual(rest, [])

    def test_pk(self):
        query = Query(User)
        path, final_field, targets, rest = query.names_to_path(["pk"], User._meta)

        self.assertEqual(path, [])
        self.assertEqual(final_field, User._meta.get_field("composite_pk"))
        self.assertEqual(targets, (User._meta.get_field("composite_pk"),))
        self.assertEqual(rest, [])

    def test_tenant_id(self):
        query = Query(User)
        path, final_field, targets, rest = query.names_to_path(
            ["tenant", "id"], User._meta
        )

        self.assertEqual(
            path,
            [
                PathInfo(
                    from_opts=User._meta,
                    to_opts=Tenant._meta,
                    target_fields=(Tenant._meta.get_field("id"),),
                    join_field=User._meta.get_field("tenant"),
                    m2m=False,
                    direct=True,
                    filtered_relation=None,
                ),
            ],
        )
        self.assertEqual(final_field, Tenant._meta.get_field("id"))
        self.assertEqual(targets, (Tenant._meta.get_field("id"),))
        self.assertEqual(rest, [])

    def test_user_id(self):
        query = Query(Comment)
        path, final_field, targets, rest = query.names_to_path(
            ["user", "id"], Comment._meta
        )

        self.assertEqual(
            path,
            [
                PathInfo(
                    from_opts=Comment._meta,
                    to_opts=User._meta,
                    target_fields=(
                        User._meta.get_field("tenant"),
                        User._meta.get_field("id"),
                    ),
                    join_field=Comment._meta.get_field("user"),
                    m2m=False,
                    direct=True,
                    filtered_relation=None,
                ),
            ],
        )
        self.assertEqual(final_field, User._meta.get_field("id"))
        self.assertEqual(targets, (User._meta.get_field("id"),))
        self.assertEqual(rest, [])

    def test_user_tenant_id(self):
        query = Query(Comment)
        path, final_field, targets, rest = query.names_to_path(
            ["user", "tenant", "id"], Comment._meta
        )

        self.assertEqual(
            path,
            [
                PathInfo(
                    from_opts=Comment._meta,
                    to_opts=User._meta,
                    target_fields=(
                        User._meta.get_field("tenant"),
                        User._meta.get_field("id"),
                    ),
                    join_field=Comment._meta.get_field("user"),
                    m2m=False,
                    direct=True,
                    filtered_relation=None,
                ),
                PathInfo(
                    from_opts=User._meta,
                    to_opts=Tenant._meta,
                    target_fields=(Tenant._meta.get_field("id"),),
                    join_field=User._meta.get_field("tenant"),
                    m2m=False,
                    direct=True,
                    filtered_relation=None,
                ),
            ],
        )
        self.assertEqual(final_field, Tenant._meta.get_field("id"))
        self.assertEqual(targets, (Tenant._meta.get_field("id"),))
        self.assertEqual(rest, [])
