from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),
    path("settings/profile/", views.profile_settings, name="profile_settings"),
    path("entity/<str:entity>/", views.entity_list, name="entity_list"),
    path("entity/<str:entity>/<int:pk>/edit/", views.entity_edit, name="entity_edit"),
    path("entity/<str:entity>/<int:pk>/delete/", views.entity_delete, name="entity_delete"),
    path("entity/users/<int:pk>/toggle-status/", views.toggle_user_status, name="toggle_user_status"),
    path("requests/", views.request_list, name="request_list"),
    path("requests/make/", views.request_list, {"user_page_mode": "make"}, name="request_make"),
    path("requests/my/", views.request_list, {"user_page_mode": "my"}, name="request_my"),
    path("requests/<int:pk>/user-verify/", views.request_user_verify, name="request_user_verify"),
    path("requests/<int:pk>/user-backjob/", views.request_user_backjob, name="request_user_backjob"),
    path("requests/<int:pk>/reference-file/", views.request_reference_file, name="request_reference_file"),
    path("requests/<str:filter_key>/", views.request_list, name="request_list_filtered"),
    path("requests/<int:pk>/delete/", views.request_delete, name="request_delete"),
    path("requests/<int:pk>/<str:action>/", views.request_action, name="request_action"),
]
