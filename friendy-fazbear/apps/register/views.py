from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        if not username:
            messages.error(request, 'Username is required.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
        else:
            try:
                validate_password(password)
                user = User.objects.create_user(username=username, email=email, password=password)
                login(request, user)
                return redirect('home')
            except ValidationError as e:
                for err in e.messages:
                    messages.error(request, err)
    return render(request, 'register/register.html')