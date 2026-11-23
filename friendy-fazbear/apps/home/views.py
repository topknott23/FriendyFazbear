import random
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.core.models import MiniGame, GameRoom, RoomPlayer, Profile, UserSettings

DEFAULT_GAMES = [
    ('fazbear_frenzy', 'Fazbear Frenzy', '2D Survival Tag', 'Featured', 'Run, dodge, and outlast your friends in an energetic arcade tag arena!'),
    ('pizza_dash', 'Pizza Dash Sprint', 'Party Racing', 'Fast-Paced', 'Tap frantically and swipe to collect pizza slices before the timer expires.'),
    ('laser_havoc', 'Laser Havoc Arena', 'Top-Down Brawler', 'Competitive', 'Reflect lasers with mobile motion or digital D-pads in real time.'),
    ('night_guard_duel', 'Night Guard Duel', 'Stealth Strategy', 'New Release', 'Manage power doors, security cams, and sneak past animatronics!'),
]


def generate_unique_room_code():
    for _ in range(50):
        code = str(random.randint(1000, 9999))
        if not GameRoom.objects.filter(room_code=code).exists():
            return code
    return str(random.randint(10000, 99999))


@login_required
def home_view(request):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={'display_name': request.user.username, 'gamer_tag': f'#FAZ-{request.user.id:02d}'},
    )
    UserSettings.objects.get_or_create(user=request.user)

    for gid, name, genre, badge, desc in DEFAULT_GAMES:
        MiniGame.objects.get_or_create(
            game_id=gid,
            defaults={'name': name, 'genre': genre, 'badge': badge, 'description': desc},
        )

    room = GameRoom.objects.filter(host_user=request.user, status='waiting').first()
    if not room or request.method == 'POST':
        if room:
            room.status = 'closed'
            room.save()
        code = generate_unique_room_code()
        room = GameRoom.objects.create(room_code=code, host_user=request.user)
        RoomPlayer.objects.create(
            room=room,
            user=request.user,
            slot_number=1,
            device_identifier='HOST-PC',
            player_alias=profile.display_name or request.user.username,
            is_ready=True,
        )
        if request.method == 'POST':
            messages.success(request, f'New lobby created — Room Code #{code}')
            return redirect('home')

    games = MiniGame.objects.filter(is_active=True)
    players = room.players.all().order_by('slot_number')
    win_rate = round((profile.wins / profile.games_played) * 100) if profile.games_played > 0 else 0
    return render(
        request,
        'home/home.html',
        {
            'room': room,
            'games': games,
            'players': players,
            'profile': profile,
            'win_rate': win_rate,
        },
    )
