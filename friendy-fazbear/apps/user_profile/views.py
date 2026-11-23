from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.core.models import Profile, UserSettings


@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={'display_name': request.user.username, 'gamer_tag': f'#FAZ-{request.user.id:02d}'},
    )
    UserSettings.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '').strip()
        request.user.last_name = request.POST.get('last_name', '').strip()
        request.user.email = request.POST.get('email', '').strip()
        request.user.save()

        profile.display_name = request.POST.get('display_name', profile.display_name).strip()
        avatar_choice = request.POST.get('avatar', profile.avatar)
        valid_avatars = {choice[0] for choice in Profile.AVATAR_CHOICES}
        if avatar_choice in valid_avatars:
            profile.avatar = avatar_choice
        profile.favorite_game = request.POST.get('favorite_game', profile.favorite_game).strip()
        profile.bio = request.POST.get('bio', profile.bio).strip()
        profile.save()
        messages.success(request, 'Player profile updated!')
        return redirect('profile')

    win_rate = round((profile.wins / profile.games_played) * 100) if profile.games_played > 0 else 0
    return render(request, 'profile/profile.html', {'profile': profile, 'win_rate': win_rate})
