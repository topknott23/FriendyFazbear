from apps.core.models import Friendship, PartyInvite
from apps.core.services import ensure_user_records


def player_context(request):
    """Safely expose player_profile, player_settings, and Crew notification count to all templates."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'player_profile': None,
            'player_settings': None,
            'crew_notifications_count': 0,
        }

    profile, user_settings = ensure_user_records(request.user)
    pending_friend_requests = Friendship.objects.filter(
        addressee=request.user,
        status='pending',
    ).count()
    pending_party_invites = PartyInvite.objects.filter(
        recipient=request.user,
        status='pending',
        room__status__in=['waiting', 'in_game'],
    ).count()

    return {
        'player_profile': profile,
        'player_settings': user_settings,
        'crew_notifications_count': pending_friend_requests + pending_party_invites,
    }
