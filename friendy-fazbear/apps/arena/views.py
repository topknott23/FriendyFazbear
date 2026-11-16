import random
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.core.models import MiniGame, GameRoom, GameMatch, MatchScore

@login_required
def arena_view(request):
    game_id = request.GET.get('game', 'fazbear_frenzy')
    game = MiniGame.objects.filter(game_id=game_id).first() or MiniGame.objects.first()
    room = GameRoom.objects.filter(host_user=request.user, status='waiting').first()

    if request.method == 'POST' and game and room:
        score_val = int(request.POST.get('score', random.randint(450, 980)))
        match = GameMatch.objects.create(
            room=room, game=game, winner_user=request.user,
            status='finished', duration_seconds=random.randint(60, 180), ended_at=timezone.now()
        )
        MatchScore.objects.create(match=match, user=request.user, score=score_val, rank_placement=1)
        profile = request.user.profile
        profile.games_played += 1
        profile.wins += 1
        profile.save()
        return redirect('arena')

    recent_matches = MatchScore.objects.filter(user=request.user).select_related('match__game').order_by('-recorded_at')[:5]
    return render(request, 'arena/arena.html', {'game': game, 'room': room, 'recent_matches': recent_matches})