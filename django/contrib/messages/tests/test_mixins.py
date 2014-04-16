from django.contrib.messages.tests.models import SomeObject
from django.contrib.messages.tests.urls import (
    ContactFormViewWithMsg, DeleteFormViewWithMsg,
)
from django.core.urlresolvers import reverse
from django.test import TestCase, override_settings


@override_settings(ROOT_URLCONF='django.contrib.messages.tests.urls')
class SuccessMessageMixinTests(TestCase):

    def test_set_messages_success(self):
        author = {'name': 'John Doe',
                  'slug': 'success-msg'}
        add_url = reverse('add_success_msg')
        req = self.client.post(add_url, author)
        self.assertIn(ContactFormViewWithMsg.success_message % author,
                      req.cookies['messages'].value)

    def test_set_messages_success_on_delete(self):
        object_to_delete = SomeObject.objects.create(name="MyObject")

        delete_url = reverse('success_msg_on_delete', args=[object_to_delete.pk])
        req = self.client.delete(delete_url)
        self.assertIn(DeleteFormViewWithMsg.success_message,
                      req.cookies['messages'].value)
