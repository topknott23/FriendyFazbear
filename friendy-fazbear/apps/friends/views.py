from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from apps.core.models import Friendship, Profile, UserSettings


@login_required
def friends_view(request):
    Profile.objects.get_or_create(
        user=request.user,
        defaults={'display_name': request.user.username, 'gamer_tag': f'#FAZ-{request.user.id:02d}'},
    )
    UserSettings.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action', 'add')

        if action == 'remove':
            friendship_id = request.POST.get('friendship_id')
            deleted, _ = Friendship.objects.filter(id=friendship_id, requester=request.user).delete()
            if deleted:
                messages.success(request, 'Removed player from your Fazbear crew.')
            return redirect('friends')

        target_query = request.POST.get('username', '').strip()
        if not target_query:
            messages.error(request, 'Please enter a username or gamer tag.')
            return redirect('friends')

        target = User.objects.filter(username__iexact=target_query).first()
        if not target and target_query.startswith('#'):
            prof = Profile.objects.select_related('user').filter(gamer_tag__iexact=target_query).first()
            if prof:
                target = prof.user

        if target == request.user:
            messages.error(request, "You can't add yourself to your crew.")
        elif target:
            _, created = Friendship.objects.get_or_create(
                requester=request.user,
                addressee=target,
                defaults={'status': 'accepted'},
            )
            if created:
                messages.success(request, f'Added {target.username} to your Fazbear crew!')
            else:
                messages.info(request, f'{target.username} is already in your crew.')
        else:
            messages.error(request, f'Player "{target_query}" was not found.')
        return redirect('friends')

    friendships = (
        Friendship.objects.filter(requester=request.user)
        .select_related('addressee', 'addressee__profile')
        .order_by('-created_at')
    )
    leaderboard = Profile.objects.select_related('user').order_by('-wins', '-games_played')[:10]
    return render(
        request,
        'friends/friends.html',
        {
            'friendships': friendships,
            'leaderboard': leaderboard,
        },
    )
