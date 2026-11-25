from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.shortcuts import redirect, render
from django.utils import timezone
from apps.core.models import GameMatch, MatchScore, MiniGame
from apps.core.services import (
    create_host_room,
    ensure_default_games,
    ensure_user_records,
    finalize_party_match,
    get_active_party_match,
    get_active_room_for_user,
    recalculate_party_match_rankings,
    start_party_match,
)


@login_required
def arena_view(request):
    profile, _ = ensure_user_records(request.user)
    ensure_default_games()

    room = get_active_room_for_user(request.user)
    requested_game_id = request.GET.get('game') or request.POST.get('game_id') or ''

    if not room:
        default_game = (
            MiniGame.objects.filter(game_id=requested_game_id, is_active=True).first()
            or MiniGame.objects.filter(is_active=True).first()
        )
        room = create_host_room(request.user, current_game=default_game)

    is_host = room.host_user_id == request.user.id
    auth_players = list(
        room.players.filter(user__isnull=False)
        .select_related('user', 'user__profile')
        .order_by('slot_number')
    )
    is_party_mode = len(auth_players) > 1

    # Handle host party control actions first
    if request.method == 'POST':
        action = request.POST.get('action', 'save_score')

        if action == 'return_to_lobby':
            if is_host:
                active = get_active_party_match(room)
                if active and active.scores.exists():
                    finalize_party_match(active)
                room.status = 'waiting'
                room.save(update_fields=['status'])
                messages.info(request, f'Returned Party #{room.room_code} to the Lobby.')
            return redirect('home')

        if action == 'new_party_round':
            if not is_host:
                messages.error(request, 'Only the host can start a new party round.')
                return redirect('arena')
            game = room.current_game or MiniGame.objects.filter(is_active=True).first()
            if game:
                start_party_match(room, game)
                messages.success(request, f'Started a new party round of {game.name}!')
                return redirect(f'/arena/?game={game.game_id}')
            return redirect('arena')

        if action == 'finish_party_match':
            if not is_host:
                messages.error(request, 'Only the host can finish the party match.')
                return redirect('arena')
            active = get_active_party_match(room)
            if active:
                finalize_party_match(active)
                winner = active.winner_user.username if active.winner_user else 'No winner'
                messages.success(request, f'Party round finished! Winner: {winner}')
            return redirect(f'/arena/?game={room.current_game_id or "fazbear_frenzy"}')

    # Enforce host-only game selection
    if not is_host:
        if room.status != 'in_game' or not room.current_game:
            messages.info(request, f'Waiting for host {room.host_user.username} to select a mini-game.')
            return redirect('home')
        game = room.current_game
        if request.method == 'GET' and requested_game_id and requested_game_id != game.game_id:
            messages.info(request, f'Only the host can switch games — synced to {game.name}.')
            return redirect(f'/arena/?game={game.game_id}')
    else:
        game = (
            MiniGame.objects.filter(game_id=requested_game_id, is_active=True).first()
            if requested_game_id
            else (room.current_game or MiniGame.objects.filter(is_active=True).first())
        )
        if not game:
            game = MiniGame.objects.filter(is_active=True).first()

        # When host enters Arena or switches game, sync the room for everyone.
        # Only pre-create an ongoing shared GameMatch when playing in multi-player party mode.
        active_match = get_active_party_match(room)
        if game and request.method == 'GET':
            if is_party_mode:
                if room.status != 'in_game' or room.current_game_id != game.game_id or not active_match:
                    start_party_match(room, game)
            else:
                if room.status != 'in_game' or room.current_game_id != game.game_id:
                    room.current_game = game
                    room.status = 'in_game'
                    room.save(update_fields=['current_game', 'status'])

    # Handle Score Submission (Solo vs Shared Competitive Party Match)
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

        if is_party_mode:
            active_match = get_active_party_match(room)
            if not active_match or active_match.game_id != game.game_id:
                active_match = GameMatch.objects.create(
                    room=room,
                    game=game,
                    status='ongoing',
                    duration_seconds=duration_val,
                )

            if duration_val > active_match.duration_seconds:
                active_match.duration_seconds = duration_val
                active_match.save(update_fields=['duration_seconds'])

            MatchScore.objects.update_or_create(
                match=active_match,
                user=request.user,
                defaults={'score': score_val},
            )
            ranked = recalculate_party_match_rankings(active_match)
            my_entry = next((e for e in ranked if e.user_id == request.user.id), None)
            my_rank = my_entry.rank_placement if my_entry else 1

            submitted_user_ids = set(active_match.scores.values_list('user_id', flat=True))
            expected_user_ids = {p.user_id for p in auth_players if p.user_id}

            if expected_user_ids.issubset(submitted_user_ids):
                finalize_party_match(active_match)
                winner_name = active_match.winner_user.username if active_match.winner_user else 'Tie'
                messages.success(
                    request,
                    f'Party round complete! You scored {score_val:,} pts (#{my_rank}). Winner: {winner_name}!',
                )
            else:
                remaining = len(expected_user_ids - submitted_user_ids)
                messages.success(
                    request,
                    f'Submitted {score_val:,} pts (currently #{my_rank} in party). Waiting on {remaining} player{"s" if remaining != 1 else ""}!',
                )
            return redirect(f'/arena/?game={game.game_id}')

        # Solo play flow (1 authenticated player in room)
        higher_scores = MatchScore.objects.filter(match__game=game, score__gt=score_val).count()
        placement = higher_scores + 1

        match = GameMatch.objects.create(
            room=room,
            game=game,
            winner_user=request.user if score_val > 0 else None,
            status='finished',
            duration_seconds=duration_val,
            ended_at=timezone.now(),
        )
        MatchScore.objects.create(
            match=match,
            user=request.user,
            score=score_val,
            rank_placement=placement,
        )
        profile.games_played += 1
        if score_val > 0:
            profile.wins += 1
        profile.save(update_fields=['games_played', 'wins', 'updated_at'])
        messages.success(
            request,
            f'Saved {score_val:,} pts in {game.name} ({duration_val}s) — Ranked #{placement}!',
        )
        return redirect(f'/arena/?game={game.game_id}')

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
    game_top_scores = (
        MatchScore.objects.filter(match__game=game)
        .values(
            'user__id',
            'user__username',
            'user__profile__display_name',
            'user__profile__avatar',
            'user__profile__gamer_tag',
        )
        .annotate(best_score=Max('score'))
        .order_by('-best_score')[:5]
        if game
        else []
    )

    room_players = list(room.players.select_related('user', 'user__profile').order_by('slot_number'))
    latest_party_match = get_active_party_match(room) or (
        GameMatch.objects.filter(room=room, game=game)
        .select_related('winner_user')
        .order_by('-started_at')
        .first()
    )

    scores_by_user = {}
    if latest_party_match:
        for ms in latest_party_match.scores.select_related('user').order_by('rank_placement', '-score'):
            scores_by_user[ms.user_id] = ms

    party_standings = []
    for p in room_players:
        ms = scores_by_user.get(p.user_id) if p.user_id else None
        party_standings.append(
            {
                'slot_number': p.slot_number,
                'alias': p.player_alias,
                'is_host': p.user_id == room.host_user_id,
                'is_me': p.user_id == request.user.id,
                'submitted': ms is not None,
                'score': ms.score if ms else None,
                'rank': ms.rank_placement if ms else None,
            }
        )
    party_standings.sort(key=lambda item: (0 if item['submitted'] else 1, item['rank'] or 99, item['slot_number']))

    my_submitted_in_match = request.user.id in scores_by_user
    starts_in_ms = None
    if latest_party_match and latest_party_match.status == 'ongoing' and latest_party_match.round_start_at:
        starts_in_ms = int((latest_party_match.round_start_at - timezone.now()).total_seconds() * 1000)

    return render(
        request,
        'arena/arena.html',
        {
            'game': game,
            'all_games': all_games,
            'room': room,
            'room_players': room_players,
            'is_host': is_host,
            'is_party_mode': is_party_mode,
            'latest_party_match': latest_party_match,
            'my_submitted_in_match': my_submitted_in_match,
            'starts_in_ms': starts_in_ms,
            'party_standings': party_standings,
            'recent_matches': recent_matches,
            'high_score': high_score,
            'game_top_scores': game_top_scores,
        },
    )
