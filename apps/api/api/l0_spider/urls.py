from __future__ import annotations

from django.urls import path

from .views import HardSpecMetaView, HardSpecRecommendationsView

urlpatterns = [
    path("hard-spec/meta", HardSpecMetaView.as_view(), name="l0-spider-hard-spec-meta"),
    path("hard-spec/recommendations", HardSpecRecommendationsView.as_view(), name="l0-spider-hard-spec-recommendations"),
]
