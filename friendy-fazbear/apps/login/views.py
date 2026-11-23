from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from apps.core.models import Profile, UserSettings


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    next_url = request.GET.get('next') or request.POST.get('next') or ''

    if request.method == 'POST':
        identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=identifier, password=password)
        if user is None and identifier:
            # Allow signing in with email address or case-insensitive username
            matched_user = (
                User.objects.filter(email__iexact=identifier).first()
                or User.objects.filter(username__iexact=identifier).first()
            )
            if matched_user:
                user = authenticate(request, username=matched_user.username, password=password)

        if user is not None:
            Profile.objects.get_or_create(
                user=user,
                defaults={'display_name': user.username, 'gamer_tag': f'#FAZ-{user.id:02d}'},
            )
            UserSettings.objects.get_or_create(user=user)
            login(request, user)
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('home')

        messages.error(request, 'Invalid username/email or password. Please try again.')

    return render(request, 'login/login.html', {'next': next_url})


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been signed out safely.')
    return redirect('login')
