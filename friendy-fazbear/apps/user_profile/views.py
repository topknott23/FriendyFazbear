from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def profile_view(request):
    profile = request.user.profile
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()
        profile.display_name = request.POST.get('display_name', profile.display_name)
        profile.avatar = request.POST.get('avatar', profile.avatar)
        profile.favorite_game = request.POST.get('favorite_game', profile.favorite_game)
        profile.bio = request.POST.get('bio', profile.bio)
        profile.save()
        messages.success(request, 'Player profile updated!')
        return redirect('profile')
    win_rate = round((profile.wins / profile.games_played) * 100) if profile.games_played > 0 else 0
    return render(request, 'profile/profile.html', {'profile': profile, 'win_rate': win_rate})