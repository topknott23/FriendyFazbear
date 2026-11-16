import random
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from apps.core.models import MiniGame, GameRoom, RoomPlayer

DEFAULT_GAMES = [
    ('fazbear_frenzy', 'Fazbear Frenzy', '2D Survival Tag', 'Featured', 'Run, dodge, and outlast your friends in an energetic arcade tag arena!'),
    ('pizza_dash', 'Pizza Dash Sprint', 'Party Racing', 'Fast-Paced', 'Tap frantically and swipe to collect pizza slices before the timer expires.'),
    ('laser_havoc', 'Laser Havoc Arena', 'Top-Down Brawler', 'Competitive', 'Reflect lasers with mobile motion or digital D-pads in real time.'),
    ('night_guard_duel', 'Night Guard Duel', 'Stealth Strategy', 'New Release', 'Manage power doors, security cams, and sneak past animatronics!'),
]

@login_required
def home_view(request):
    for gid, name, genre, badge, desc in DEFAULT_GAMES:
        MiniGame.objects.get_or_create(
            game_id=gid,
            defaults={'name': name, 'genre': genre, 'badge': badge, 'description': desc}
        )

    room = GameRoom.objects.filter(host_user=request.user, status='waiting').first()
    if not room or request.method == 'POST':
        if room:
            room.status = 'closed'
            room.save()
        code = str(random.randint(1000, 9999))
        room = GameRoom.objects.create(room_code=code, host_user=request.user)
        RoomPlayer.objects.create(
            room=room, user=request.user, slot_number=1,
            device_identifier='HOST-PC', player_alias=request.user.profile.display_name or request.user.username, is_ready=True
        )
        if request.method == 'POST':
            return redirect('home')

    games = MiniGame.objects.filter(is_active=True)
    players = room.players.all().order_by('slot_number')
    return render(request, 'home/home.html', {'room': room, 'games': games, 'players': players})