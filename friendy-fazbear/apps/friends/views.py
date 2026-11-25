from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Max, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from apps.core.models import Friendship, GameRoom, PartyInvite, Profile
from apps.core.services import (
    are_friends,
    can_join_room,
    create_host_room,
    ensure_user_records,
    get_active_room_for_user,
    join_user_to_room,
)


@login_required
def friends_view(request):
    ensure_user_records(request.user)
    my_room = get_active_room_for_user(request.user)

    if request.method == 'POST':
        action = request.POST.get('action', 'add')

        if action == 'accept':
            friendship_id = request.POST.get('friendship_id')
            req = Friendship.objects.filter(
                id=friendship_id,
                addressee=request.user,
                status='pending',
            ).select_related('requester').first()
            if req:
                req.status = 'accepted'
                req.save(update_fields=['status', 'updated_at'])
                messages.success(request, f'Accepted {req.requester.username} into your Fazbear crew!')
            return redirect('friends')

        if action == 'decline':
            friendship_id = request.POST.get('friendship_id')
            deleted, _ = Friendship.objects.filter(
                id=friendship_id,
                addressee=request.user,
                status='pending',
            ).delete()
            if deleted:
                messages.info(request, 'Declined friend request.')
            return redirect('friends')

        if action == 'cancel':
            friendship_id = request.POST.get('friendship_id')
            deleted, _ = Friendship.objects.filter(
                id=friendship_id,
                requester=request.user,
                status='pending',
            ).delete()
            if deleted:
                messages.info(request, 'Cancelled outgoing friend request.')
            return redirect('friends')

        if action == 'remove':
            friendship_id = request.POST.get('friendship_id')
            deleted, _ = Friendship.objects.filter(
                id=friendship_id,
            ).filter(
                Q(requester=request.user) | Q(addressee=request.user)
            ).delete()
            if deleted:
                messages.success(request, 'Removed player from your Fazbear crew.')
            return redirect('friends')

        if action == 'invite_to_party':
            target_id = request.POST.get('target_user_id')
            target = User.objects.filter(id=target_id).first()
            if not target or not are_friends(request.user, target):
                messages.error(request, 'You can only invite accepted crew members to your party.')
                return redirect('friends')

            host_room = my_room if (my_room and my_room.host_user_id == request.user.id) else None
            if not host_room:
                host_room = create_host_room(request.user)

            if host_room.players.filter(user=target).exists():
                messages.info(request, f'{target.username} is already in your party (#{host_room.room_code}).')
                return redirect('friends')

            if host_room.players.count() >= host_room.max_players:
                messages.error(request, f'Your party #{host_room.room_code} is full.')
                return redirect('friends')

            _, created = PartyInvite.objects.get_or_create(
                room=host_room,
                sender=request.user,
                recipient=target,
                status='pending',
            )
            if created:
                messages.success(request, f'Invited {target.username} to Party #{host_room.room_code}!')
            else:
                messages.info(request, f'Party invite to {target.username} is already pending.')
            return redirect('friends')

        if action == 'accept_party_invite':
            invite_id = request.POST.get('invite_id')
            invite = (
                PartyInvite.objects.filter(
                    id=invite_id,
                    recipient=request.user,
                    status='pending',
                    room__status__in=['waiting', 'in_game'],
                )
                .select_related('room', 'room__current_game', 'sender')
                .first()
            )
            if not invite:
                messages.error(request, 'That party invite has expired or is no longer active.')
                return redirect('friends')

            seat, err = join_user_to_room(request.user, invite.room, device_identifier='CREW-PARTY')
            if err:
                messages.error(request, err)
                return redirect('friends')

            messages.success(request, f"Joined {invite.sender.username}'s party (Room #{invite.room.room_code}) as P{seat.slot_number}!")
            if invite.room.status == 'in_game' and invite.room.current_game:
                return redirect(f'/arena/?game={invite.room.current_game.game_id}')
            return redirect('home')

        if action == 'decline_party_invite':
            invite_id = request.POST.get('invite_id')
            updated = PartyInvite.objects.filter(
                id=invite_id,
                recipient=request.user,
                status='pending',
            ).update(status='declined')
            if updated:
                messages.info(request, 'Declined party invite.')
            return redirect('friends')

        if action == 'join_crew_party':
            room_code = request.POST.get('room_code', '').strip().lstrip('#')
            target_room = (
                GameRoom.objects.filter(room_code=room_code, status__in=['waiting', 'in_game'])
                .select_related('host_user', 'current_game')
                .first()
            )
            if not target_room:
                messages.error(request, 'That party lobby is no longer active.')
                return redirect('friends')

            allowed, reason = can_join_room(target_room, request.user)
            if not allowed:
                messages.error(request, reason)
                return redirect('friends')

            seat, err = join_user_to_room(request.user, target_room, device_identifier='CREW-PARTY')
            if err:
                messages.error(request, err)
                return redirect('friends')

            messages.success(request, f"Joined {target_room.host_user.username}'s party (Room #{target_room.room_code}) as P{seat.slot_number}!")
            if target_room.status == 'in_game' and target_room.current_game:
                return redirect(f'/arena/?game={target_room.current_game.game_id}')
            return redirect('home')

        # Default action: send friend request (auto-accepts if the other user already requested us!)
        target_query = request.POST.get('username', '').strip()
        if not target_query:
            messages.error(request, 'Please enter a username or gamer tag.')
            return redirect('friends')

        target = User.objects.filter(username__iexact=target_query).first()
        if not target and target_query.startswith('#'):
            prof = Profile.objects.select_related('user').filter(gamer_tag__iexact=target_query).first()
            if prof:
                target = prof.user

        if not target:
            messages.error(request, f'Player "{target_query}" was not found.')
            return redirect('friends')

        if target == request.user:
            messages.error(request, "You can't add yourself to your crew.")
            return redirect('friends')

        existing = Friendship.objects.filter(
            Q(requester=request.user, addressee=target) | Q(requester=target, addressee=request.user)
        ).first()

        if existing:
            if existing.status == 'accepted':
                messages.info(request, f'{target.username} is already in your crew.')
            elif existing.requester_id == target.id and existing.status == 'pending':
                existing.status = 'accepted'
                existing.save(update_fields=['status', 'updated_at'])
                messages.success(request, f'{target.username} already invited you — you are now in the same crew!')
            elif existing.status == 'pending':
                messages.info(request, f'Friend request to {target.username} is already pending.')
            else:
                messages.error(request, f'Unable to add {target.username}.')
        else:
            Friendship.objects.create(
                requester=request.user,
                addressee=target,
                status='pending',
            )
            messages.success(request, f'Sent a crew invite to {target.username}!')
        return redirect('friends')

    accepted_qs = (
        Friendship.objects.filter(status='accepted')
        .filter(Q(requester=request.user) | Q(addressee=request.user))
        .select_related(
            'requester', 'requester__profile', 'requester__settings',
            'addressee', 'addressee__profile', 'addressee__settings',
        )
        .order_by('-updated_at')
    )

    my_host_room = my_room if (my_room and my_room.host_user_id == request.user.id) else None
    my_party_user_ids = set(my_room.players.values_list('user_id', flat=True)) if my_room else set()
    pending_sent_invite_recipients = set(
        PartyInvite.objects.filter(
            sender=request.user,
            status='pending',
            room__status__in=['waiting', 'in_game'],
        ).values_list('recipient_id', flat=True)
    )

    crew_members = []
    crew_user_ids = {request.user.id}
    for f in accepted_qs:
        friend_user = f.addressee if f.requester_id == request.user.id else f.requester
        friend_profile, friend_settings = ensure_user_records(friend_user)
        crew_user_ids.add(friend_user.id)
        friend_room = (
            GameRoom.objects.filter(host_user=friend_user, status__in=['waiting', 'in_game'])
            .select_related('current_game')
            .first()
        )
        can_join_friend_room = False
        if friend_room and (not my_room or friend_room.id != my_room.id):
            allowed, _ = can_join_room(friend_room, request.user)
            can_join_friend_room = allowed and friend_room.players.count() < friend_room.max_players

        crew_members.append(
            {
                'friendship_id': f.id,
                'user': friend_user,
                'profile': friend_profile,
                'show_online': friend_settings.show_online_status,
                'in_my_party': friend_user.id in my_party_user_ids,
                'invite_pending': friend_user.id in pending_sent_invite_recipients,
                'friend_room': friend_room if can_join_friend_room else None,
            }
        )

    incoming_party_invites = (
        PartyInvite.objects.filter(
            recipient=request.user,
            status='pending',
            room__status__in=['waiting', 'in_game'],
        )
        .select_related('sender', 'sender__profile', 'room', 'room__current_game')
        .order_by('-created_at')
    )

    incoming_requests = (
        Friendship.objects.filter(addressee=request.user, status='pending')
        .select_related('requester', 'requester__profile')
        .order_by('-created_at')
    )
    outgoing_requests = (
        Friendship.objects.filter(requester=request.user, status='pending')
        .select_related('addressee', 'addressee__profile')
        .order_by('-created_at')
    )

    board_scope = request.GET.get('scope', 'global')
    if board_scope not in ('global', 'crew'):
        board_scope = 'global'

    leaderboard_qs = Profile.objects.select_related('user').annotate(
        total_score=Sum('user__match_scores__score'),
        best_score=Max('user__match_scores__score'),
    )
    if board_scope == 'crew':
        leaderboard_qs = leaderboard_qs.filter(user_id__in=crew_user_ids)

    leaderboard = leaderboard_qs.order_by('-wins', '-total_score', '-games_played')[:15]

    return render(
        request,
        'friends/friends.html',
        {
            'crew_members': crew_members,
            'incoming_party_invites': incoming_party_invites,
            'incoming_requests': incoming_requests,
            'outgoing_requests': outgoing_requests,
            'leaderboard': leaderboard,
            'board_scope': board_scope,
            'my_host_room': my_host_room,
            'my_room': my_room,
        },
    )


@login_required
def notifications_api(request):
    """Lightweight JSON endpoint for live Crew notification badge polling."""
    pending_friends = Friendship.objects.filter(addressee=request.user, status='pending').count()
    pending_invites = PartyInvite.objects.filter(
        recipient=request.user,
        status='pending',
        room__status__in=['waiting', 'in_game'],
    ).count()
    return JsonResponse(
        {
            'crew_notifications': pending_friends + pending_invites,
            'friend_requests': pending_friends,
            'party_invites': pending_invites,
        }
    )
