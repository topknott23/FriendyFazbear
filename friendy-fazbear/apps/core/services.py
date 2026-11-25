import random
import secrets
from django.db.models import Q
from django.utils import timezone
from apps.core.models import (
    Friendship,
    GameMatch,
    GameRoom,
    MatchScore,
    MiniGame,
    PartyInvite,
    Profile,
    RoomPlayer,
    UserSettings,
)

DEFAULT_GAMES = [
    (
        'fazbear_frenzy',
        'Fazbear Frenzy',
        '2D Survival Tag',
        'Featured',
        'Run, dodge, and outlast your friends in an energetic arcade tag arena!',
    ),
    (
        'pizza_dash',
        'Pizza Dash Sprint',
        'Party Racing',
        'Fast-Paced',
        'Tap frantically and swipe to collect pizza slices before the timer expires.',
    ),
    (
        'laser_havoc',
        'Laser Havoc Arena',
        'Top-Down Brawler',
        'Competitive',
        'Reflect lasers with mobile motion or digital D-pads in real time.',
    ),
    (
        'night_guard_duel',
        'Night Guard Duel',
        'Stealth Strategy',
        'New Release',
        'Manage power doors, security cams, and sneak past animatronics!',
    ),
]


def ensure_user_records(user):
    """Guarantee that an authenticated user has both Profile and UserSettings rows."""
    profile, _ = Profile.objects.get_or_create(
        user=user,
        defaults={
            'display_name': user.username,
            'gamer_tag': f'#FAZ-{user.id:02d}',
        },
    )
    if not profile.gamer_tag or (profile.gamer_tag == '#FAZ-01' and user.id != 1):
        profile.gamer_tag = f'#FAZ-{user.id:02d}'
        profile.save(update_fields=['gamer_tag'])

    user_settings, _ = UserSettings.objects.get_or_create(user=user)
    return profile, user_settings


def ensure_default_games():
    """Seed the four default arcade mini-games if missing."""
    for gid, name, genre, badge, desc in DEFAULT_GAMES:
        MiniGame.objects.get_or_create(
            game_id=gid,
            defaults={
                'name': name,
                'genre': genre,
                'badge': badge,
                'description': desc,
            },
        )


def generate_unique_room_code():
    for _ in range(50):
        code = str(random.randint(1000, 9999))
        if not GameRoom.objects.filter(room_code=code).exists():
            return code
    return str(random.randint(10000, 99999))


def create_host_room(user, current_game=None):
    """Create a fresh waiting lobby room for the host and attach them to Slot 1."""
    profile, user_settings = ensure_user_records(user)
    code = generate_unique_room_code()
    room = GameRoom.objects.create(
        room_code=code,
        host_user=user,
        current_game=current_game,
        qr_token=secrets.token_urlsafe(12),
    )
    RoomPlayer.objects.create(
        room=room,
        user=user,
        slot_number=1,
        device_identifier='HOST-PC',
        player_alias=profile.display_name or user.username,
        is_ready=user_settings.auto_ready,
    )
    return room


def get_active_room_for_user(user):
    """Return the active (waiting or in_game) room the user is currently hosting or joined to."""
    player_seat = (
        RoomPlayer.objects.filter(user=user, room__status__in=['waiting', 'in_game'])
        .select_related('room', 'room__host_user', 'room__current_game')
        .order_by('-joined_at')
        .first()
    )
    if player_seat:
        return player_seat.room

    return GameRoom.objects.filter(host_user=user, status__in=['waiting', 'in_game']).first()


def close_room(room):
    room.status = 'closed'
    room.closed_at = timezone.now()
    room.save(update_fields=['status', 'closed_at'])
    PartyInvite.objects.filter(room=room, status='pending').update(status='declined')


def next_available_slot(room):
    taken = set(room.players.values_list('slot_number', flat=True))
    for slot in range(1, room.max_players + 1):
        if slot not in taken:
            return slot
    return None


def are_friends(user_a, user_b):
    if not user_a or not user_b or not user_a.is_authenticated or not user_b.is_authenticated:
        return False
    if user_a.id == user_b.id:
        return True
    return Friendship.objects.filter(
        status='accepted',
    ).filter(
        Q(requester=user_a, addressee=user_b) | Q(requester=user_b, addressee=user_a)
    ).exists()


def can_join_room(room, user=None, allow_invited=True):
    """Check host lobby privacy settings before allowing a player into a room."""
    if room.status not in ('waiting', 'in_game'):
        return False, 'This room is no longer active.'

    if user and user.is_authenticated and user.id == room.host_user_id:
        return True, ''

    # Direct pending party invite from the host bypasses private/friends restriction
    if allow_invited and user and user.is_authenticated:
        if PartyInvite.objects.filter(room=room, recipient=user, status='pending').exists():
            return True, ''

    _, host_settings = ensure_user_records(room.host_user)
    privacy = host_settings.lobby_privacy

    if privacy == 'private':
        return False, 'This lobby is set to Private by the host.'
    if privacy == 'friends':
        if not user or not user.is_authenticated:
            return False, 'This lobby is Friends Only — please sign in with a crew account.'
        if not are_friends(room.host_user, user):
            return False, "This lobby is Friends Only. Join the host's crew first."
    return True, ''


def join_user_to_room(user, target_room, device_identifier='WEB-PLAYER', player_alias=''):
    """Move an authenticated user cleanly from their old room into target_room."""
    profile, user_settings = ensure_user_records(user)
    existing = RoomPlayer.objects.filter(room=target_room, user=user).first()
    if existing:
        return existing, None

    slot = next_available_slot(target_room)
    if slot is None:
        return None, f'Room #{target_room.room_code} is full ({target_room.max_players}/{target_room.max_players}).'

    old_room = get_active_room_for_user(user)
    if old_room and old_room.id != target_room.id:
        if old_room.host_user_id == user.id:
            close_room(old_room)
        else:
            RoomPlayer.objects.filter(room=old_room, user=user).delete()

    seat = RoomPlayer.objects.create(
        room=target_room,
        user=user,
        slot_number=slot,
        device_identifier=device_identifier[:100],
        player_alias=(player_alias or profile.display_name or user.username)[:50],
        is_ready=user_settings.auto_ready,
    )
    PartyInvite.objects.filter(room=target_room, recipient=user, status='pending').update(status='accepted')
    return seat, None


def get_active_party_match(room):
    """Return the currently ongoing GameMatch for a room, if any."""
    return (
        GameMatch.objects.filter(room=room, status='ongoing')
        .select_related('game', 'winner_user')
        .order_by('-started_at')
        .first()
    )


def start_party_match(room, game):
    """Host starts (or switches) the active game for the whole room."""
    # Finalize or abort any previous ongoing match in this room
    prev_ongoing = GameMatch.objects.filter(room=room, status='ongoing')
    for m in prev_ongoing:
        if m.scores.exists():
            finalize_party_match(m)
        else:
            m.status = 'aborted'
            m.ended_at = timezone.now()
            m.save(update_fields=['status', 'ended_at'])

    room.current_game = game
    room.status = 'in_game'
    room.save(update_fields=['current_game', 'status'])

    return GameMatch.objects.create(
        room=room,
        game=game,
        status='ongoing',
    )


def recalculate_party_match_rankings(match):
    """Rank all MatchScore entries in a shared match (1st, 2nd, 3rd, 4th) and set match winner."""
    scores = list(match.scores.select_related('user').order_by('-score', 'recorded_at'))
    if not scores:
        return scores

    for idx, entry in enumerate(scores, start=1):
        if entry.rank_placement != idx:
            entry.rank_placement = idx
            entry.save(update_fields=['rank_placement'])

    top = scores[0]
    match.winner_user = top.user if top.score > 0 else None
    match.save(update_fields=['winner_user'])
    return scores


def finalize_party_match(match):
    """Mark a shared match finished and award Profile stats (games_played to all, win to #1)."""
    if match.status == 'finished':
        return match

    scores = recalculate_party_match_rankings(match)
    match.status = 'finished'
    match.ended_at = timezone.now()
    match.save(update_fields=['status', 'ended_at'])

    if not scores:
        return match

    top_score = scores[0].score
    for entry in scores:
        prof, _ = ensure_user_records(entry.user)
        prof.games_played += 1
        if top_score > 0 and entry.score == top_score:
            prof.wins += 1
        prof.save(update_fields=['games_played', 'wins', 'updated_at'])

    return match
