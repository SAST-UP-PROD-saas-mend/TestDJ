from freedom.conf.urls import url

from . import views


urlpatterns = [
    url(r'^request_attrs/$', views.request_processor),
]
