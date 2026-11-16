from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def settings_view(request):
    user_settings = request.user.settings
    if request.method == 'POST':
        user_settings.master_volume = int(request.POST.get('master_volume', 80))
        user_settings.sfx_volume = int(request.POST.get('sfx_volume', 85))
        user_settings.music_volume = int(request.POST.get('music_volume', 70))
        user_settings.theme = request.POST.get('theme', 'dark')
        user_settings.lobby_privacy = request.POST.get('lobby_privacy', 'public')
        user_settings.email_notifications = 'email_notifications' in request.POST
        user_settings.auto_ready = 'auto_ready' in request.POST
        user_settings.save()
        messages.success(request, 'Console settings saved!')
        return redirect('user_settings')
    return render(request, 'user_settings/user_settings.html', {'settings': user_settings})