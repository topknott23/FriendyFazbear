from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from apps.core.models import (
    Friendship,
    GameMatch,
    GameRoom,
    MatchScore,
    MiniGame,
    PartyInvite,
    Profile,
    RoomPlayer,
    UserSettings,
)


class CoreModelsAndAuthTests(TestCase):
    def test_user_creation_signal_creates_profile_and_settings(self):
        user = User.objects.create_user(username='freddy', email='freddy@fazbear.local', password='password123')
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertTrue(UserSettings.objects.filter(user=user).exists())
        self.assertEqual(user.profile.gamer_tag, f'#FAZ-{user.id:02d}')

    def test_register_rejects_mismatched_or_missing_confirm_password(self):
        resp = self.client.post(
            reverse('register'),
            {
                'username': 'bonnie',
                'email': 'bonnie@fazbear.local',
                'password': 'password123',
                'confirm_password': '',
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='bonnie').exists())

    def test_register_login_with_email_and_logout_flow(self):
        resp = self.client.post(
            reverse('register'),
            {
                'username': 'chica',
                'email': 'chica@fazbear.local',
                'password': 'password123',
                'confirm_password': 'password123',
            },
        )
        self.assertRedirects(resp, reverse('home'))
        self.assertTrue(User.objects.filter(username='chica').exists())

        logout_resp = self.client.post(reverse('logout'))
        self.assertRedirects(logout_resp, reverse('login'))

        login_resp = self.client.post(
            reverse('login'),
            {
                'username': 'CHICA@FAZBEAR.LOCAL',
                'password': 'password123',
            },
        )
        self.assertRedirects(login_resp, reverse('home'))


class MultiplayerLobbyTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username='host1', email='host1@test.local', password='password123')
        self.guest = User.objects.create_user(username='player2', email='p2@test.local', password='password123')
        self.client.force_login(self.host)

    def test_home_creates_room_and_seeds_games(self):
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(MiniGame.objects.count(), 4)
        room = GameRoom.objects.filter(host_user=self.host, status='waiting').first()
        self.assertIsNotNone(room)
        self.assertEqual(room.players.count(), 1)

    def test_new_room_closes_previous_room_with_timestamp(self):
        self.client.get(reverse('home'))
        old_room = GameRoom.objects.get(host_user=self.host, status='waiting')

        resp = self.client.post(reverse('home'), {'action': 'new_room'})
        self.assertRedirects(resp, reverse('home'))

        old_room.refresh_from_db()
        self.assertEqual(old_room.status, 'closed')
        self.assertIsNotNone(old_room.closed_at)

    def test_host_can_add_and_kick_local_player(self):
        self.client.get(reverse('home'))
        room = GameRoom.objects.get(host_user=self.host, status='waiting')

        self.client.post(reverse('home'), {'action': 'add_local_player', 'player_alias': 'Foxy Pad'})
        self.assertEqual(room.players.count(), 2)
        local_seat = room.players.get(slot_number=2)
        self.assertEqual(local_seat.player_alias, 'Foxy Pad')

        self.client.post(reverse('home'), {'action': 'kick_player', 'player_id': local_seat.id})
        self.assertEqual(room.players.count(), 1)

    def test_player_join_respects_lobby_privacy_and_updates_status_api(self):
        self.client.get(reverse('home'))
        room = GameRoom.objects.get(host_user=self.host, status='waiting')

        # Private blocks join
        self.host.settings.lobby_privacy = 'private'
        self.host.settings.save()
        guest_client = Client()
        guest_client.force_login(self.guest)
        guest_client.post(reverse('home'), {'action': 'join_room', 'room_code': room.room_code})
        self.assertEqual(room.players.count(), 1)

        # Friends-only blocks non-friend, allows accepted friend
        self.host.settings.lobby_privacy = 'friends'
        self.host.settings.save()
        guest_client.post(reverse('home'), {'action': 'join_room', 'room_code': room.room_code})
        self.assertEqual(room.players.count(), 1)

        Friendship.objects.create(requester=self.host, addressee=self.guest, status='accepted')
        guest_client.post(reverse('home'), {'action': 'join_room', 'room_code': room.room_code})
        self.assertEqual(room.players.count(), 2)

        api_resp = self.client.get(reverse('room_status_api', args=[room.room_code]))
        self.assertEqual(api_resp.status_code, 200)
        payload = api_resp.json()
        self.assertEqual(payload['player_count'], 2)
        self.assertEqual(len(payload['slots']), 4)
        self.assertTrue(payload['slots'][1]['occupied'])

    def test_guest_controller_can_pair_toggle_ready_and_leave(self):
        self.client.get(reverse('home'))
        room = GameRoom.objects.get(host_user=self.host, status='waiting')

        anon = Client()
        resp = anon.post(
            reverse('join_room_code', args=[room.room_code]),
            {'action': 'join', 'room_code': room.room_code, 'player_alias': 'Phone P2', 'device_type': 'MOBILE-TOUCH'},
        )
        self.assertRedirects(resp, reverse('join_room_code', args=[room.room_code]))
        seat = room.players.get(slot_number=2)
        self.assertEqual(seat.player_alias, 'Phone P2')
        self.assertTrue(seat.is_ready)

        anon.post(reverse('join_room_code', args=[room.room_code]), {'action': 'toggle_guest_ready'})
        seat.refresh_from_db()
        self.assertFalse(seat.is_ready)

        anon.post(reverse('join_room_code', args=[room.room_code]), {'action': 'leave_guest'})
        self.assertFalse(RoomPlayer.objects.filter(id=seat.id).exists())


class ArenaFriendsProfileSettingsTests(TestCase):
    def setUp(self):
        self.u1 = User.objects.create_user(username='alice', email='alice@test.local', password='password123')
        self.u2 = User.objects.create_user(username='bob', email='bob@test.local', password='password123')
        self.client.force_login(self.u1)

    def test_arena_records_score_and_computes_rank_placement(self):
        # First score from alice
        resp1 = self.client.post(
            reverse('arena'),
            {'game_id': 'fazbear_frenzy', 'score': '1500', 'duration_seconds': '30'},
        )
        self.assertRedirects(resp1, '/arena/?game=fazbear_frenzy')
        self.assertEqual(GameMatch.objects.count(), 1)
        s1 = MatchScore.objects.get(user=self.u1)
        self.assertEqual(s1.rank_placement, 1)

        # Lower score from bob should be ranked #2
        c2 = Client()
        c2.force_login(self.u2)
        c2.post(
            reverse('arena'),
            {'game_id': 'fazbear_frenzy', 'score': '800', 'duration_seconds': '25'},
        )
        s2 = MatchScore.objects.get(user=self.u2)
        self.assertEqual(s2.rank_placement, 2)

        self.u1.profile.refresh_from_db()
        self.assertEqual(self.u1.profile.games_played, 1)
        self.assertEqual(self.u1.profile.wins, 1)

    def test_two_way_friend_request_accept_and_remove(self):
        # Alice invites Bob
        self.client.post(reverse('friends'), {'action': 'add', 'username': 'bob'})
        fr = Friendship.objects.get(requester=self.u1, addressee=self.u2)
        self.assertEqual(fr.status, 'pending')

        # Bob accepts
        c2 = Client()
        c2.force_login(self.u2)
        c2.post(reverse('friends'), {'action': 'accept', 'friendship_id': fr.id})
        fr.refresh_from_db()
        self.assertEqual(fr.status, 'accepted')

        # Crew leaderboard scope works
        resp = c2.get(f"{reverse('friends')}?scope=crew")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'alice')

        # Bob can also remove mutual friendship
        c2.post(reverse('friends'), {'action': 'remove', 'friendship_id': fr.id})
        self.assertFalse(Friendship.objects.filter(id=fr.id).exists())

    def test_profile_updates_and_rejects_duplicate_email(self):
        # Duplicate email rejected
        self.client.post(
            reverse('profile'),
            {
                'first_name': 'Alice',
                'last_name': 'Faz',
                'email': 'bob@test.local',
                'display_name': 'Ace',
                'avatar': 'foxy',
                'favorite_game': 'Pizza Dash Sprint',
                'bio': 'Hello!',
            },
        )
        self.u1.refresh_from_db()
        self.assertEqual(self.u1.email, 'alice@test.local')

        # Valid update succeeds
        self.client.post(
            reverse('profile'),
            {
                'first_name': 'Alice',
                'last_name': 'Faz',
                'email': 'alice.new@test.local',
                'display_name': 'Ace',
                'avatar': 'foxy',
                'favorite_game': 'Pizza Dash Sprint',
                'bio': 'Arcade champ',
            },
        )
        self.u1.refresh_from_db()
        self.u1.profile.refresh_from_db()
        self.assertEqual(self.u1.email, 'alice.new@test.local')
        self.assertEqual(self.u1.profile.avatar, 'foxy')
        self.assertEqual(self.u1.profile.display_name, 'Ace')

    def test_settings_clamps_volumes_and_updates_theme(self):
        self.client.post(
            reverse('user_settings'),
            {
                'master_volume': '999',
                'sfx_volume': '-10',
                'music_volume': '45',
                'theme': 'neon',
                'lobby_privacy': 'friends',
                'auto_ready': 'on',
            },
        )
        self.u1.settings.refresh_from_db()
        self.assertEqual(self.u1.settings.master_volume, 100)
        self.assertEqual(self.u1.settings.sfx_volume, 0)
        self.assertEqual(self.u1.settings.music_volume, 45)
        self.assertEqual(self.u1.settings.theme, 'neon')
        self.assertEqual(self.u1.settings.lobby_privacy, 'friends')
        self.assertTrue(self.u1.settings.auto_ready)
        self.assertFalse(self.u1.settings.show_online_status)


class CrewPartySyncAndShowdownTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username='host_freddy', email='host@faz.local', password='password123')
        self.crew = User.objects.create_user(username='crew_bonnie', email='crew@faz.local', password='password123')
        self.host_client = Client()
        self.crew_client = Client()
        self.host_client.force_login(self.host)
        self.crew_client.force_login(self.crew)

    def test_crew_notification_badge_counts_friend_requests_and_party_invites(self):
        # Host sends a friend request -> crew has 1 notification
        self.host_client.post(reverse('friends'), {'action': 'add', 'username': 'crew_bonnie'})
        resp = self.crew_client.get(reverse('home'))
        self.assertEqual(resp.context['crew_notifications_count'], 1)
        self.assertContains(resp, 'id="crewNotifBadge"')

        api_data = self.crew_client.get(reverse('notifications_api')).json()
        self.assertEqual(api_data['crew_notifications'], 1)
        self.assertEqual(api_data['friend_requests'], 1)
        self.assertEqual(api_data['party_invites'], 0)

        # Crew accepts friend request -> 0 notifications
        fr = Friendship.objects.get(requester=self.host, addressee=self.crew)
        self.crew_client.post(reverse('friends'), {'action': 'accept', 'friendship_id': fr.id})
        api_data = self.crew_client.get(reverse('notifications_api')).json()
        self.assertEqual(api_data['crew_notifications'], 0)

        # Host creates lobby & invites crew to party -> 1 notification again!
        self.host_client.get(reverse('home'))
        self.host_client.post(reverse('friends'), {'action': 'invite_to_party', 'target_user_id': self.crew.id})
        api_data = self.crew_client.get(reverse('notifications_api')).json()
        self.assertEqual(api_data['crew_notifications'], 1)
        self.assertEqual(api_data['party_invites'], 1)

    def test_only_host_can_choose_game_and_crew_auto_syncs(self):
        Friendship.objects.create(requester=self.host, addressee=self.crew, status='accepted')
        self.host_client.get(reverse('home'))
        self.host_client.post(reverse('friends'), {'action': 'invite_to_party', 'target_user_id': self.crew.id})

        invite = PartyInvite.objects.get(recipient=self.crew, status='pending')
        self.crew_client.post(reverse('friends'), {'action': 'accept_party_invite', 'invite_id': invite.id})

        room = GameRoom.objects.get(host_user=self.host, status='waiting')
        self.assertEqual(room.players.count(), 2)

        # Crew cannot launch a game from Lobby
        self.crew_client.post(reverse('home'), {'action': 'launch_game', 'game_id': 'pizza_dash'})
        room.refresh_from_db()
        self.assertEqual(room.status, 'waiting')
        self.assertIsNone(room.current_game)

        # Crew trying to enter Arena before host picks redirects back to Lobby
        arena_early = self.crew_client.get(reverse('arena'))
        self.assertRedirects(arena_early, reverse('home'))

        # Host launches Pizza Dash Sprint -> room switches to in_game and API exposes arena_url for auto-sync
        launch_resp = self.host_client.post(reverse('home'), {'action': 'launch_game', 'game_id': 'pizza_dash'})
        self.assertRedirects(launch_resp, '/arena/?game=pizza_dash')

        room.refresh_from_db()
        self.assertEqual(room.status, 'in_game')
        self.assertEqual(room.current_game_id, 'pizza_dash')

        api_payload = self.crew_client.get(reverse('room_status_api', args=[room.room_code])).json()
        self.assertEqual(api_payload['status'], 'in_game')
        self.assertEqual(api_payload['current_game_id'], 'pizza_dash')
        self.assertEqual(api_payload['arena_url'], '/arena/?game=pizza_dash')

        # If crew visits Lobby now, they are automatically redirected to host's chosen game
        crew_home = self.crew_client.get(reverse('home'))
        self.assertRedirects(crew_home, '/arena/?game=pizza_dash')

        # If crew tries to switch to another game in Arena, server locks them back to host's game
        crew_switch = self.crew_client.get('/arena/?game=laser_havoc')
        self.assertRedirects(crew_switch, '/arena/?game=pizza_dash')

    def test_shared_party_match_ranks_players_and_crowns_single_winner(self):
        Friendship.objects.create(requester=self.host, addressee=self.crew, status='accepted')
        self.host_client.get(reverse('home'))
        room = GameRoom.objects.get(host_user=self.host, status='waiting')
        self.crew_client.post(reverse('home'), {'action': 'join_room', 'room_code': room.room_code})

        # Host launches Laser Havoc for the party
        self.host_client.post(reverse('home'), {'action': 'launch_game', 'game_id': 'laser_havoc'})
        match = GameMatch.objects.get(room=room, status='ongoing')

        # Host submits 900 pts -> still ongoing, waiting on crew
        self.host_client.post(reverse('arena'), {'action': 'save_score', 'game_id': 'laser_havoc', 'score': '900', 'duration_seconds': '30'})
        match.refresh_from_db()
        self.assertEqual(match.status, 'ongoing')
        self.assertEqual(match.scores.count(), 1)

        # Crew submits 1600 pts -> beats host! Match finishes automatically, crew ranked #1 and wins
        self.crew_client.post(reverse('arena'), {'action': 'save_score', 'game_id': 'laser_havoc', 'score': '1600', 'duration_seconds': '30'})
        match.refresh_from_db()
        self.assertEqual(match.status, 'finished')
        self.assertEqual(match.winner_user_id, self.crew.id)

        crew_score = MatchScore.objects.get(match=match, user=self.crew)
        host_score = MatchScore.objects.get(match=match, user=self.host)
        self.assertEqual(crew_score.rank_placement, 1)
        self.assertEqual(host_score.rank_placement, 2)

        self.crew.profile.refresh_from_db()
        self.host.profile.refresh_from_db()
        self.assertEqual(self.crew.profile.games_played, 1)
        self.assertEqual(self.crew.profile.wins, 1)
        self.assertEqual(self.host.profile.games_played, 1)
        self.assertEqual(self.host.profile.wins, 0)

    def test_host_start_round_api_schedules_3s_countdown_and_blocks_non_host(self):
        Friendship.objects.create(requester=self.host, addressee=self.crew, status='accepted')
        self.host_client.get(reverse('home'))
        room = GameRoom.objects.get(host_user=self.host, status='waiting')
        self.crew_client.post(reverse('home'), {'action': 'join_room', 'room_code': room.room_code})
        self.host_client.post(reverse('home'), {'action': 'launch_game', 'game_id': 'fazbear_frenzy'})

        # Non-host cannot trigger the party countdown
        forbidden = self.crew_client.post(reverse('start_party_round_api', args=[room.room_code]))
        self.assertEqual(forbidden.status_code, 403)

        # Host triggers the synchronized 3-second countdown
        ok_resp = self.host_client.post(reverse('start_party_round_api', args=[room.room_code]))
        self.assertEqual(ok_resp.status_code, 200)
        start_data = ok_resp.json()
        self.assertIsNotNone(start_data['round_start_at'])
        self.assertGreater(start_data['starts_in_ms'], 2000)
        self.assertLessEqual(start_data['starts_in_ms'], 4000)

        # Crew's room status poll immediately sees the synchronized countdown timestamp
        poll_data = self.crew_client.get(reverse('room_status_api', args=[room.room_code])).json()
        self.assertEqual(poll_data['round_start_at'], start_data['round_start_at'])
        self.assertIsNotNone(poll_data['starts_in_ms'])
