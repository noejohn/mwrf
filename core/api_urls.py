from django.urls import path

from .api_views import (
    ApiDashboardView,
    ApiEntityView,
    ApiLoginView,
    ApiMeView,
    ApiProfileView,
    ApiRequestActionView,
    ApiRequestDeleteView,
    ApiRegisterView,
    ApiRequestsView,
    ApiToggleUserStatusView,
    ApiTokenRefreshView,
)


urlpatterns = [
    path("auth/login/", ApiLoginView.as_view(), name="api_login"),
    path("auth/register/", ApiRegisterView.as_view(), name="api_register"),
    path("auth/refresh/", ApiTokenRefreshView.as_view(), name="api_refresh"),
    path("auth/me/", ApiMeView.as_view(), name="api_me"),
    path("dashboard/", ApiDashboardView.as_view(), name="api_dashboard"),
    path("profile/", ApiProfileView.as_view(), name="api_profile"),
    path("entities/<str:entity>/", ApiEntityView.as_view(), name="api_entity_list"),
    path("entities/<str:entity>/<int:pk>/", ApiEntityView.as_view(), name="api_entity_detail"),
    path("entities/users/<int:pk>/toggle-status/", ApiToggleUserStatusView.as_view(), name="api_toggle_user_status"),
    path("requests/", ApiRequestsView.as_view(), name="api_request_list"),
    path("requests/<str:filter_key>/", ApiRequestsView.as_view(), name="api_request_list_filtered"),
    path("requests/<int:pk>/<str:action>/", ApiRequestActionView.as_view(), name="api_request_action"),
    path("requests/<int:pk>/", ApiRequestDeleteView.as_view(), name="api_request_delete"),
]
