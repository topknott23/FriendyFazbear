from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from apps.core.models import Friendship, Profile

@login_required
def friends_view(request):
    if request.method == 'POST':
        target_username = request.POST.get('username', '').strip()
        target = User.objects.filter(username=target_username).exclude(id=request.user.id).first()
        if target:
            Friendship.objects.get_or_create(requester=request.user, addressee=target, defaults={'status': 'accepted'})
            messages.success(request, f'Added {target.username} to your Fazbear crew!')
        else:
            messages.error(request, 'Player not found.')
        return redirect('friends')

    friendships = Friendship.objects.filter(requester=request.user)
    leaderboard = Profile.objects.select_related('user').order_by('-wins', '-games_played')[:10]
    return render(request, 'friends/friends.html', {'friendships': friendships, 'leaderboard': leaderboard})