from django.contrib import admin
from apps.core.models import (
    Profile,
    UserSettings,
    Friendship,
    MiniGame,
    GameRoom,
    RoomPlayer,
    GameMatch,
    MatchScore,
    PartyInvite,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_name', 'gamer_tag', 'avatar', 'games_played', 'wins', 'updated_at')
    list_filter = ('avatar',)
    search_fields = ('user__username', 'display_name', 'gamer_tag')


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'theme', 'lobby_privacy', 'master_volume', 'sfx_volume', 'music_volume', 'auto_ready')
    list_filter = ('theme', 'lobby_privacy', 'auto_ready', 'show_online_status')
    search_fields = ('user__username',)


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('requester', 'addressee', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('requester__username', 'addressee__username')


@admin.register(MiniGame)
class MiniGameAdmin(admin.ModelAdmin):
    list_display = ('game_id', 'name', 'genre', 'badge', 'min_players', 'max_players', 'is_active')
    list_filter = ('is_active', 'genre')
    search_fields = ('game_id', 'name')


class RoomPlayerInline(admin.TabularInline):
    model = RoomPlayer
    extra = 0


@admin.register(GameRoom)
class GameRoomAdmin(admin.ModelAdmin):
    list_display = ('room_code', 'host_user', 'current_game', 'status', 'max_players', 'created_at', 'closed_at')
    list_filter = ('status',)
    search_fields = ('room_code', 'host_user__username')
    inlines = [RoomPlayerInline]


@admin.register(RoomPlayer)
class RoomPlayerAdmin(admin.ModelAdmin):
    list_display = ('player_alias', 'room', 'slot_number', 'user', 'device_identifier', 'is_ready', 'joined_at')
    list_filter = ('is_ready', 'slot_number')
    search_fields = ('player_alias', 'room__room_code', 'user__username')


class MatchScoreInline(admin.TabularInline):
    model = MatchScore
    extra = 0


@admin.register(GameMatch)
class GameMatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'game', 'room', 'winner_user', 'status', 'duration_seconds', 'started_at', 'ended_at')
    list_filter = ('status', 'game')
    search_fields = ('room__room_code', 'winner_user__username')
    inlines = [MatchScoreInline]


@admin.register(MatchScore)
class MatchScoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'match', 'score', 'rank_placement', 'recorded_at')
    list_filter = ('rank_placement', 'match__game')
    search_fields = ('user__username',)


@admin.register(PartyInvite)
class PartyInviteAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'room', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('sender__username', 'recipient__username', 'room__room_code')
