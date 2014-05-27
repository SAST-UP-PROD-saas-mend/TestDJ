from freedom.test import LiveServerTestCase

from freedom.contrib.staticfiles.handlers import StaticFilesHandler


class StaticLiveServerCase(LiveServerTestCase):
    """
    Extends freedom.test.LiveServerTestCase to transparently overlay at test
    execution-time the assets provided by the staticfiles app finders. This
    means you don't need to run collectstatic before or as a part of your tests
    setup.
    """

    static_handler = StaticFilesHandler
