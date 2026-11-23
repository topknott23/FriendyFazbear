import random
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from apps.core.models import MiniGame, GameRoom, RoomPlayer, GameMatch, MatchScore, Profile, UserSettings
from apps.home.views import DEFAULT_GAMES, generate_unique_room_code


@login_required
def arena_view(request):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={'display_name': request.user.username, 'gamer_tag': f'#FAZ-{request.user.id:02d}'},
    )
    UserSettings.objects.get_or_create(user=request.user)

    if not MiniGame.objects.exists():
        for gid, name, genre, badge, desc in DEFAULT_GAMES:
            MiniGame.objects.get_or_create(
                game_id=gid,
                defaults={'name': name, 'genre': genre, 'badge': badge, 'description': desc},
            )

    game_id = request.GET.get('game') or request.POST.get('game_id') or 'fazbear_frenzy'
    game = MiniGame.objects.filter(game_id=game_id).first() or MiniGame.objects.first()
    room = GameRoom.objects.filter(host_user=request.user, status='waiting').first()

    if not room:
        code = generate_unique_room_code()
        room = GameRoom.objects.create(room_code=code, host_user=request.user, current_game=game)
        RoomPlayer.objects.create(
            room=room,
            user=request.user,
            slot_number=1,
            device_identifier='HOST-PC',
            player_alias=profile.display_name or request.user.username,
            is_ready=True,
        )

    if request.method == 'POST' and game and room:
        try:
            score_val = int(request.POST.get('score', 0))
        except (TypeError, ValueError):
            score_val = 0
        score_val = max(0, min(999999, score_val))

        try:
            duration_val = int(request.POST.get('duration_seconds', 30))
        except (TypeError, ValueError):
            duration_val = 30
        duration_val = max(1, min(3600, duration_val))

        match = GameMatch.objects.create(
            room=room,
            game=game,
            winner_user=request.user if score_val > 0 else None,
            status='finished',
            duration_seconds=duration_val,
            ended_at=timezone.now(),
        )
        MatchScore.objects.create(match=match, user=request.user, score=score_val, rank_placement=1)
        profile.games_played += 1
        if score_val > 0:
            profile.wins += 1
        profile.save()
        messages.success(request, f'Saved {score_val:,} pts in {game.name} ({duration_val}s)!')
        return redirect(f"/arena/?game={game.game_id}")

    all_games = MiniGame.objects.filter(is_active=True)
    recent_matches = (
        MatchScore.objects.filter(user=request.user)
        .select_related('match__game')
        .order_by('-recorded_at')[:8]
    )
    high_score = (
        MatchScore.objects.filter(user=request.user, match__game=game)
        .order_by('-score')
        .values_list('score', flat=True)
        .first()
        or 0
    )
    return render(
        request,
        'arena/arena.html',
        {
            'game': game,
            'all_games': all_games,
            'room': room,
            'recent_matches': recent_matches,
            'high_score': high_score,
        },
    )
