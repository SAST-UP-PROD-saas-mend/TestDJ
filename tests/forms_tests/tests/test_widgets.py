# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.admin.tests import AdminSeleniumWebDriverTestCase
from django.test import override_settings
from django.urls import reverse

from ..models import Article


@override_settings(ROOT_URLCONF='forms_tests.urls')
class LiveWidgetTests(AdminSeleniumWebDriverTestCase):

    available_apps = ['forms_tests'] + AdminSeleniumWebDriverTestCase.available_apps

    def test_textarea_trailing_newlines(self):
        """
        Test that a roundtrip on a ModelForm doesn't alter the TextField value
        """
        article = Article.objects.create(content="\nTst\n")
        self.selenium.get('%s%s' % (self.live_server_url,
            reverse('article_form', args=[article.pk])))
        self.selenium.find_element_by_id('submit').submit()
        article = Article.objects.get(pk=article.pk)
        # Should be "\nTst\n" after #19251 is fixed
        self.assertEqual(article.content, "\r\nTst\r\n")
