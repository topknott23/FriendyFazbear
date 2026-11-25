from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from apps.core.models import GameMatch, GameRoom, MiniGame, RoomPlayer
from apps.core.services import (
    DEFAULT_GAMES,
    can_join_room,
    close_room,
    create_host_room,
    ensure_default_games,
    ensure_user_records,
    generate_unique_room_code,
    get_active_party_match,
    get_active_room_for_user,
    join_user_to_room,
    next_available_slot,
    start_party_match,
)

__all__ = [
    'DEFAULT_GAMES',
    'generate_unique_room_code',
    'home_view',
    'join_room_view',
    'room_status_api',
    'start_party_round_api',
]


@login_required
def home_view(request):
    profile, user_settings = ensure_user_records(request.user)
    ensure_default_games()

    room = get_active_room_for_user(request.user)
    if not room:
        room = create_host_room(request.user)

    is_host = room.host_user_id == request.user.id

    if request.method == 'POST':
        action = request.POST.get('action', 'new_room')

        if action == 'new_room':
            if is_host:
                close_room(room)
            else:
                RoomPlayer.objects.filter(room=room, user=request.user).delete()
            new_room = create_host_room(request.user)
            messages.success(request, f'New lobby created — Room Code #{new_room.room_code}')
            return redirect('home')

        if action == 'launch_game':
            if not is_host:
                messages.error(request, 'Only the party host can choose a mini-game.')
                return redirect('home')
            game_id = request.POST.get('game_id', '').strip()
            game = MiniGame.objects.filter(game_id=game_id, is_active=True).first()
            if not game:
                messages.error(request, 'Selected mini-game was not found.')
                return redirect('home')
            if room.players.filter(user__isnull=False).count() > 1:
                start_party_match(room, game)
            else:
                room.current_game = game
                room.status = 'in_game'
                room.save(update_fields=['current_game', 'status'])
            return redirect(f'/arena/?game={game.game_id}')

        if action == 'join_room':
            code = request.POST.get('room_code', '').strip().lstrip('#')
            target_room = GameRoom.objects.filter(room_code=code, status__in=['waiting', 'in_game']).first()
            if not target_room:
                messages.error(request, f'No active lobby found for code #{code or "----"}.')
                return redirect('home')

            if target_room.id == room.id:
                messages.info(request, f'You are already in Room #{target_room.room_code}.')
                return redirect('home')

            allowed, reason = can_join_room(target_room, request.user)
            if not allowed:
                messages.error(request, reason)
                return redirect('home')

            seat, err = join_user_to_room(request.user, target_room, device_identifier='WEB-PLAYER')
            if err:
                messages.error(request, err)
                return redirect('home')

            messages.success(request, f'Joined Room #{target_room.room_code} as P{seat.slot_number}!')
            if target_room.status == 'in_game' and target_room.current_game:
                return redirect(f'/arena/?game={target_room.current_game.game_id}')
            return redirect('home')

        if action == 'toggle_ready':
            seat = RoomPlayer.objects.filter(room=room, user=request.user).first()
            if seat:
                seat.is_ready = not seat.is_ready
                seat.save(update_fields=['is_ready'])
                messages.info(request, 'Status updated: Ready!' if seat.is_ready else 'Status updated: Not Ready.')
            return redirect('home')

        if action == 'add_local_player':
            if not is_host:
                messages.error(request, 'Only the lobby host can add local controllers.')
                return redirect('home')
            slot = next_available_slot(room)
            if slot is None:
                messages.error(request, 'All controller slots are full.')
                return redirect('home')
            alias = request.POST.get('player_alias', '').strip() or f'Local Player {slot}'
            device = request.POST.get('device_identifier', '').strip() or f'LOCAL-PAD-{slot}'
            RoomPlayer.objects.create(
                room=room,
                user=None,
                slot_number=slot,
                device_identifier=device[:100],
                player_alias=alias[:50],
                is_ready=True,
            )
            messages.success(request, f'Paired {alias[:50]} in Slot P{slot}.')
            return redirect('home')

        if action == 'kick_player':
            if not is_host:
                messages.error(request, 'Only the host can remove players.')
                return redirect('home')
            player_id = request.POST.get('player_id')
            target_seat = RoomPlayer.objects.filter(id=player_id, room=room).first()
            if target_seat and target_seat.user_id != room.host_user_id:
                alias = target_seat.player_alias
                target_seat.delete()
                messages.info(request, f'Disconnected {alias} from Room #{room.room_code}.')
            return redirect('home')

        if action == 'leave_room':
            if not is_host:
                RoomPlayer.objects.filter(room=room, user=request.user).delete()
                create_host_room(request.user)
                messages.info(request, f'Left Room #{room.room_code} and returned to your own lobby.')
            return redirect('home')

        return redirect('home')

    # If a non-host crew member opens Lobby while host is already in-game, auto-send them to the host's Arena!
    if not is_host and room.status == 'in_game' and room.current_game:
        return redirect(f'/arena/?game={room.current_game.game_id}')

    # If host returns directly to Lobby, reset room back to waiting so crew knows they are in lobby
    if is_host and room.status == 'in_game':
        room.status = 'waiting'
        room.save(update_fields=['status'])

    games = MiniGame.objects.filter(is_active=True)
    players = list(room.players.select_related('user').order_by('slot_number'))
    players_by_slot = {p.slot_number: p for p in players}
    slots = [
        {'slot_number': i, 'player': players_by_slot.get(i)}
        for i in range(1, room.max_players + 1)
    ]
    current_seat = next((p for p in players if p.user_id == request.user.id), None)
    win_rate = round((profile.wins / profile.games_played) * 100) if profile.games_played > 0 else 0
    join_url = request.build_absolute_uri(reverse('join_room_code', args=[room.room_code]))
    _, host_settings = ensure_user_records(room.host_user)

    return render(
        request,
        'home/home.html',
        {
            'room': room,
            'games': games,
            'players': players,
            'slots': slots,
            'profile': profile,
            'win_rate': win_rate,
            'is_host': is_host,
            'current_seat': current_seat,
            'join_url': join_url,
            'host_privacy': host_settings.get_lobby_privacy_display(),
        },
    )


def join_room_view(request, room_code=''):
    """Controller pairing view for authenticated players or local mobile guests."""
    code = (room_code or request.GET.get('code') or request.POST.get('room_code') or '').strip().lstrip('#')
    room = GameRoom.objects.filter(room_code=code, status__in=['waiting', 'in_game']).select_related('host_user').first() if code else None

    guest_seat = None
    guest_seat_id = request.session.get('guest_room_player_id')
    if guest_seat_id:
        guest_seat = (
            RoomPlayer.objects.filter(id=guest_seat_id, room__status__in=['waiting', 'in_game'])
            .select_related('room', 'room__host_user')
            .first()
        )
        if not guest_seat:
            request.session.pop('guest_room_player_id', None)

    if request.method == 'POST':
        action = request.POST.get('action', 'join')

        if action == 'toggle_guest_ready' and guest_seat:
            guest_seat.is_ready = not guest_seat.is_ready
            guest_seat.save(update_fields=['is_ready'])
            messages.success(request, 'Controller Ready!' if guest_seat.is_ready else 'Controller set to Standby.')
            return redirect('join_room_code', room_code=guest_seat.room.room_code)

        if action == 'leave_guest' and guest_seat:
            old_code = guest_seat.room.room_code
            guest_seat.delete()
            request.session.pop('guest_room_player_id', None)
            messages.info(request, f'Disconnected from Room #{old_code}.')
            return redirect('join_room')

        if not code:
            messages.error(request, 'Enter a 4-digit room code to pair your controller.')
            return redirect('join_room')

        target_room = GameRoom.objects.filter(room_code=code, status__in=['waiting', 'in_game']).select_related('host_user', 'current_game').first()
        if not target_room:
            messages.error(request, f'Room #{code} was not found or is already closed.')
            return redirect('join_room')

        allowed, reason = can_join_room(target_room, request.user if request.user.is_authenticated else None)
        if not allowed:
            messages.error(request, reason)
            return redirect('join_room_code', room_code=code)

        alias_input = request.POST.get('player_alias', '').strip()
        device_input = request.POST.get('device_type', 'MOBILE-PAD').strip() or 'MOBILE-PAD'

        if request.user.is_authenticated:
            seat, err = join_user_to_room(
                request.user,
                target_room,
                device_identifier=device_input,
                player_alias=alias_input,
            )
            if err:
                messages.error(request, err)
                return redirect('join_room_code', room_code=code)

            messages.success(request, f'Paired with Room #{target_room.room_code} as P{seat.slot_number}!')
            if target_room.status == 'in_game' and target_room.current_game:
                return redirect(f'/arena/?game={target_room.current_game.game_id}')
            return redirect('home')

        if guest_seat and guest_seat.room_id == target_room.id:
            messages.info(request, f'Already paired in Room #{target_room.room_code} as P{guest_seat.slot_number}.')
            return redirect('join_room_code', room_code=code)

        slot = next_available_slot(target_room)
        if slot is None:
            messages.error(request, f'Room #{target_room.room_code} is full.')
            return redirect('join_room_code', room_code=code)

        if guest_seat:
            guest_seat.delete()

        alias = (alias_input or f'Guest P{slot}')[:50]
        seat = RoomPlayer.objects.create(
            room=target_room,
            user=None,
            slot_number=slot,
            device_identifier=device_input[:100],
            player_alias=alias,
            is_ready=True,
        )
        request.session['guest_room_player_id'] = seat.id
        messages.success(request, f'Paired as P{slot} in Room #{target_room.room_code}!')
        return redirect('join_room_code', room_code=target_room.room_code)

    default_alias = ''
    if request.user.is_authenticated:
        profile, _ = ensure_user_records(request.user)
        default_alias = profile.display_name or request.user.username

    return render(
        request,
        'home/join_room.html',
        {
            'room_code': code,
            'room': room,
            'guest_seat': guest_seat,
            'default_alias': default_alias,
        },
    )


def room_status_api(request, room_code):
    """Lightweight JSON polling endpoint for live lobby sync, host game selection, and party match standings."""
    code = room_code.strip().lstrip('#')
    room = GameRoom.objects.filter(room_code=code).select_related('host_user', 'current_game').first()
    if not room:
        return JsonResponse({'error': 'Room not found'}, status=404)

    players = list(room.players.select_related('user').order_by('slot_number'))
    players_by_slot = {p.slot_number: p for p in players}
    slots = []
    for slot_num in range(1, room.max_players + 1):
        p = players_by_slot.get(slot_num)
        if p:
            slots.append(
                {
                    'slot_number': slot_num,
                    'occupied': True,
                    'player_id': p.id,
                    'user_id': p.user_id,
                    'player_alias': p.player_alias,
                    'device_identifier': p.device_identifier,
                    'is_ready': p.is_ready,
                    'is_host': p.user_id == room.host_user_id,
                }
            )
        else:
            slots.append(
                {
                    'slot_number': slot_num,
                    'occupied': False,
                }
            )

    active_match = get_active_party_match(room)
    latest_match = active_match or (
        GameMatch.objects.filter(room=room)
        .select_related('game', 'winner_user')
        .order_by('-started_at')
        .first()
    )
    match_scores = []
    if latest_match:
        for ms in latest_match.scores.select_related('user', 'user__profile').order_by('rank_placement', '-score'):
            match_scores.append(
                {
                    'user_id': ms.user_id,
                    'username': ms.user.username,
                    'display_name': getattr(getattr(ms.user, 'profile', None), 'display_name', '') or ms.user.username,
                    'score': ms.score,
                    'rank_placement': ms.rank_placement,
                }
            )

    now = timezone.now()
    round_start_at = latest_match.round_start_at if (latest_match and latest_match.status == 'ongoing') else None
    starts_in_ms = int((round_start_at - now).total_seconds() * 1000) if round_start_at else None

    current_game_id = room.current_game.game_id if room.current_game else None
    return JsonResponse(
        {
            'room_code': room.room_code,
            'status': room.status,
            'host': room.host_user.username,
            'host_id': room.host_user_id,
            'max_players': room.max_players,
            'player_count': len(players),
            'all_ready': len(players) > 0 and all(p.is_ready for p in players),
            'current_game_id': current_game_id,
            'current_game_name': room.current_game.name if room.current_game else None,
            'arena_url': f'/arena/?game={current_game_id}' if current_game_id else None,
            'lobby_url': reverse('home'),
            'active_match_id': latest_match.id if latest_match else None,
            'active_match_status': latest_match.status if latest_match else None,
            'round_start_at': round_start_at.isoformat() if round_start_at else None,
            'server_now_ms': int(now.timestamp() * 1000),
            'starts_in_ms': starts_in_ms,
            'winner_username': latest_match.winner_user.username if (latest_match and latest_match.winner_user) else None,
            'match_scores': match_scores,
            'slots': slots,
        }
    )


@login_required
def start_party_round_api(request, room_code):
    """Host-only POST endpoint that schedules a synchronized 3-second countdown for the whole party."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    code = room_code.strip().lstrip('#')
    room = GameRoom.objects.filter(room_code=code, status__in=['waiting', 'in_game']).select_related('current_game').first()
    if not room:
        return JsonResponse({'error': 'Room not found'}, status=404)

    if room.host_user_id != request.user.id:
        return JsonResponse({'error': 'Only the party host can start the round.'}, status=403)

    game = room.current_game or MiniGame.objects.filter(is_active=True).first()
    if not game:
        return JsonResponse({'error': 'No mini-game selected.'}, status=400)

    match = get_active_party_match(room)
    if not match or match.game_id != game.game_id:
        match = start_party_match(room, game)

    now = timezone.now()
    # Set a fresh 3.4s server-synced start time so polling crew members catch the full 3-2-1 countdown
    if not match.round_start_at or match.round_start_at < now - timedelta(seconds=35):
        match.round_start_at = now + timedelta(milliseconds=3400)
        match.save(update_fields=['round_start_at'])

    starts_in_ms = int((match.round_start_at - now).total_seconds() * 1000)
    return JsonResponse(
        {
            'match_id': match.id,
            'game_id': game.game_id,
            'round_start_at': match.round_start_at.isoformat(),
            'server_now_ms': int(now.timestamp() * 1000),
            'starts_in_ms': starts_in_ms,
        }
    )
