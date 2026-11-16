from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


# ==========================================
# 1. PROFILE MODEL
# ==========================================
class Profile(models.Model):
    AVATAR_CHOICES = [
        ('freddy', 'Freddy Fazbear'),
        ('bonnie', 'Bonnie Bunny'),
        ('chica', 'Chica Chicken'),
        ('foxy', 'Foxy the Pirate'),
        ('golden_freddy', 'Golden Freddy'),
        ('puppet', 'The Puppet'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=60, blank=True)
    gamer_tag = models.CharField(max_length=30, blank=True, default='#FAZ-01')
    avatar = models.CharField(max_length=30, choices=AVATAR_CHOICES, default='freddy')
    bio = models.TextField(blank=True, default="Ready to rock at Freddy's pizza arcade!")
    favorite_game = models.CharField(max_length=100, default='Fazbear Pizza Rush')
    games_played = models.PositiveIntegerField(default=0)
    wins = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_profile'

    def __str__(self):
        return f"{self.user.username}'s Profile"


# ==========================================
# 2. USER SETTINGS MODEL
# ==========================================
class UserSettings(models.Model):
    THEME_CHOICES = [
        ('dark', 'Fazbear Dark'),
        ('neon', 'Neon Cyberpunk'),
        ('arcade', 'Retro 80s Arcade'),
        ('midnight', 'Midnight Purple'),
    ]
    PRIVACY_CHOICES = [
        ('public', 'Public'),
        ('friends', 'Friends Only'),
        ('private', 'Private'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    master_volume = models.PositiveIntegerField(default=80)
    sfx_volume = models.PositiveIntegerField(default=85)
    music_volume = models.PositiveIntegerField(default=70)
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default='dark')
    lobby_privacy = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default='public')
    email_notifications = models.BooleanField(default=True)
    show_online_status = models.BooleanField(default=True)
    auto_ready = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_usersettings'

    def __str__(self):
        return f"{self.user.username}'s Settings"


# ==========================================
# 3. FRIENDSHIP MODEL
# ==========================================
class Friendship(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('blocked', 'Blocked'),
    ]

    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships_requested')
    addressee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships_received')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'friendship'
        unique_together = ('requester', 'addressee')

    def __str__(self):
        return f"{self.requester.username} -> {self.addressee.username} ({self.status})"


# ==========================================
# 4. MINI GAME MODEL
# ==========================================
class MiniGame(models.Model):
    game_id = models.CharField(max_length=50, primary_key=True)  # e.g., 'fazbear_frenzy'
    name = models.CharField(max_length=100)
    genre = models.CharField(max_length=50)
    min_players = models.IntegerField(default=2)
    max_players = models.IntegerField(default=4)
    badge = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'mini_game'

    def __str__(self):
        return self.name


# ==========================================
# 5. GAME ROOM (LOBBY) MODEL
# ==========================================
class GameRoom(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting for Players'),
        ('in_game', 'In Game'),
        ('closed', 'Closed'),
    ]

    room_code = models.CharField(max_length=10, unique=True)  # e.g., '8194'
    host_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_rooms')
    current_game = models.ForeignKey(MiniGame, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    max_players = models.IntegerField(default=4)
    qr_token = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'game_room'

    def __str__(self):
        return f"Room {self.room_code} ({self.status})"


# ==========================================
# 6. ROOM PLAYER MODEL
# ==========================================
class RoomPlayer(models.Model):
    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name='players')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='room_sessions')
    slot_number = models.IntegerField()  # 1=P1, 2=P2, 3=P3, 4=P4
    device_identifier = models.CharField(max_length=100)
    player_alias = models.CharField(max_length=50)
    is_ready = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'room_player'

    def __str__(self):
        return f"{self.player_alias} in Room {self.room.room_code} (Slot {self.slot_number})"


# ==========================================
# 7. GAME MATCH MODEL
# ==========================================
class GameMatch(models.Model):
    STATUS_CHOICES = [
        ('ongoing', 'Ongoing'),
        ('finished', 'Finished'),
        ('aborted', 'Aborted'),
    ]

    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name='matches')
    game = models.ForeignKey(MiniGame, on_delete=models.CASCADE, related_name='matches')
    winner_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches_won')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ongoing')
    duration_seconds = models.IntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'game_match'

    def __str__(self):
        return f"Match #{self.id} - {self.game.name} ({self.status})"


# ==========================================
# 8. MATCH SCORE MODEL
# ==========================================
class MatchScore(models.Model):
    match = models.ForeignKey(GameMatch, on_delete=models.CASCADE, related_name='scores')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='match_scores')
    score = models.IntegerField(default=0)
    rank_placement = models.IntegerField(default=1)  # 1st, 2nd, 3rd, 4th
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'match_score'

    def __str__(self):
        return f"{self.user.username}: {self.score} pts (Rank #{self.rank_placement})"



@receiver(post_save, sender=User)
def create_user_records(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance, defaults={'display_name': instance.username})
        UserSettings.objects.get_or_create(user=instance)