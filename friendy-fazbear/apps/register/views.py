from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from apps.core.services import ensure_user_records


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    form_data = {'username': '', 'email': ''}

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        form_data = {'username': username, 'email': email}

        if not username:
            messages.error(request, 'Please choose a username.')
        elif len(username) < 2:
            messages.error(request, 'Username must be at least 2 characters.')
        elif User.objects.filter(username__iexact=username).exists():
            messages.error(request, 'That username is already taken.')
        elif email and User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'An account with that email already exists.')
        elif len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters long.')
        elif password != confirm_password:
            messages.error(request, 'Passwords do not match.')
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            profile, _ = ensure_user_records(user)
            if not profile.display_name:
                profile.display_name = username
                profile.save(update_fields=['display_name'])
            login(request, user)
            messages.success(request, f'Welcome to Friendy Fazbear, {username}!')
            return redirect('home')

    return render(request, 'register/register.html', {'form_data': form_data})
