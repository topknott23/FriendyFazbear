from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Max
from django.shortcuts import redirect, render
from apps.core.models import MatchScore, MiniGame, Profile
from apps.core.services import ensure_default_games, ensure_user_records


@login_required
def profile_view(request):
    profile, _ = ensure_user_records(request.user)
    ensure_default_games()

    if request.method == 'POST':
        new_email = request.POST.get('email', '').strip()
        if (
            new_email
            and User.objects.filter(email__iexact=new_email).exclude(id=request.user.id).exists()
        ):
            messages.error(request, 'That email address is already linked to another account.')
            return redirect('profile')

        request.user.first_name = request.POST.get('first_name', '').strip()[:150]
        request.user.last_name = request.POST.get('last_name', '').strip()[:150]
        request.user.email = new_email
        request.user.save(update_fields=['first_name', 'last_name', 'email'])

        profile.display_name = request.POST.get('display_name', profile.display_name).strip()[:60]
        avatar_choice = request.POST.get('avatar', profile.avatar)
        valid_avatars = {choice[0] for choice in Profile.AVATAR_CHOICES}
        if avatar_choice in valid_avatars:
            profile.avatar = avatar_choice
        profile.favorite_game = request.POST.get('favorite_game', profile.favorite_game).strip()[:100]
        profile.bio = request.POST.get('bio', profile.bio).strip()
        profile.save()
        messages.success(request, 'Player profile updated!')
        return redirect('profile')

    win_rate = round((profile.wins / profile.games_played) * 100) if profile.games_played > 0 else 0
    active_games = MiniGame.objects.filter(is_active=True)

    personal_bests = (
        MatchScore.objects.filter(user=request.user)
        .values('match__game__game_id', 'match__game__name')
        .annotate(best_score=Max('score'), plays=Count('id'))
        .order_by('-best_score')
    )

    return render(
        request,
        'profile/profile.html',
        {
            'profile': profile,
            'win_rate': win_rate,
            'active_games': active_games,
            'personal_bests': personal_bests,
        },
    )
