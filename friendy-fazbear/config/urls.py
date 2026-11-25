from django.contrib import admin
from django.urls import path
from apps.login.views import login_view, logout_view
from apps.register.views import register_view
from apps.home.views import home_view, join_room_view, room_status_api, start_party_round_api
from apps.user_profile.views import profile_view
from apps.user_settings.views import settings_view
from apps.arena.views import arena_view
from apps.friends.views import friends_view, notifications_api

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    path('', home_view, name='home'),
    path('join/', join_room_view, name='join_room'),
    path('join/<str:room_code>/', join_room_view, name='join_room_code'),
    path('api/room/<str:room_code>/', room_status_api, name='room_status_api'),
    path('api/room/<str:room_code>/start-round/', start_party_round_api, name='start_party_round_api'),
    path('api/notifications/', notifications_api, name='notifications_api'),
    path('profile/', profile_view, name='profile'),
    path('settings/', settings_view, name='user_settings'),
    path('arena/', arena_view, name='arena'),
    path('friends/', friends_view, name='friends'),
]
