from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.core.models import UserSettings, Profile


def _clamp_vol(value, default):
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


@login_required
def settings_view(request):
    Profile.objects.get_or_create(
        user=request.user,
        defaults={'display_name': request.user.username, 'gamer_tag': f'#FAZ-{request.user.id:02d}'},
    )
    user_settings, _ = UserSettings.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_settings.master_volume = _clamp_vol(request.POST.get('master_volume'), 80)
        user_settings.sfx_volume = _clamp_vol(request.POST.get('sfx_volume'), 85)
        user_settings.music_volume = _clamp_vol(request.POST.get('music_volume'), 70)

        theme = request.POST.get('theme', 'dark')
        if theme in {c[0] for c in UserSettings.THEME_CHOICES}:
            user_settings.theme = theme

        privacy = request.POST.get('lobby_privacy', 'public')
        if privacy in {c[0] for c in UserSettings.PRIVACY_CHOICES}:
            user_settings.lobby_privacy = privacy

        user_settings.email_notifications = 'email_notifications' in request.POST
        user_settings.show_online_status = 'show_online_status' in request.POST
        user_settings.auto_ready = 'auto_ready' in request.POST
        user_settings.save()
        messages.success(request, 'Console settings saved!')
        return redirect('user_settings')

    return render(request, 'user_settings/user_settings.html', {'settings': user_settings})
