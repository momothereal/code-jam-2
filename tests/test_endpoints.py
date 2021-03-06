import pytest
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized

from tests.fixtures import client
from tests.util import assert_json_status, store_check_auth, with_bad_auth_headers, with_auth_headers, OK_STATUS, \
    CREDENTIALS_GOOD, CREDENTIALS_BAD, VARS, refresh_token, CREDENTIALS_ALT, from_username, other_user


# Tests
def test_index(client: client):
    response = client.get("/api/")
    assert_json_status(response, OK_STATUS)


def test_not_found(client: client):
    response = client.get("/api/not_a_route")
    assert_json_status(response, NotFound.code)


@pytest.mark.dependency
def test_register(client: client):
    # register with no credentials
    response = client.post("/api/auth/register", json={})
    assert_json_status(response, BadRequest.code)

    # register with credentials
    response = client.post("/api/auth/register", json=CREDENTIALS_GOOD)
    assert_json_status(response, OK_STATUS)

    # register alt with credentials
    response = client.post("/api/auth/register", json=CREDENTIALS_ALT)
    assert_json_status(response, OK_STATUS)


@pytest.mark.dependency(depends=["test_register"])
def test_login(client: client):
    # login with no credentials
    response = client.post("/api/auth/login", json={})
    assert_json_status(response, BadRequest.code)

    # login with incorrect credentials
    response = client.post("/api/auth/login", json=CREDENTIALS_BAD)
    assert_json_status(response, Unauthorized.code)

    # successful login
    response = client.post("/api/auth/login", json=CREDENTIALS_GOOD)
    assert_json_status(response, OK_STATUS)
    store_check_auth(response, credentials=CREDENTIALS_GOOD)

    # successful alt login
    response = client.post("/api/auth/login", json=CREDENTIALS_ALT)
    assert_json_status(response, OK_STATUS)
    store_check_auth(response, credentials=CREDENTIALS_ALT)


@pytest.mark.dependency(depends=["test_login"])
def test_refresh_token(client: client):
    # refresh token with no token
    response = client.post("/api/auth/refresh", json={})
    assert_json_status(response, BadRequest.code)

    # refresh token with incorrect token
    response = client.post("/api/auth/refresh", json={"refresh_token": "not a refresh token"})
    assert_json_status(response, Unauthorized.code)

    # refresh token with correct token
    response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token()})
    assert_json_status(response, OK_STATUS)
    store_check_auth(response)


@pytest.mark.dependency(depends=["test_login"])
def test_use_auth(client: client):
    # access auth'ed resource without auth
    response = client.get("/api/me")
    assert_json_status(response, Unauthorized.code)

    # access auth'ed resource with incorrect auth
    response = client.get("/api/me", headers=with_bad_auth_headers())
    assert_json_status(response, Unauthorized.code)

    # access auth'ed resource with correct auth
    response = client.get("/api/me", headers=with_auth_headers())
    assert_json_status(response, OK_STATUS)
    assert response.json["username"] == CREDENTIALS_GOOD["username"]


@pytest.mark.dependency(depends=["test_login"])
def test_user_list(client: client):
    response = client.get("/api/users")
    assert_json_status(response, OK_STATUS)


# GAME

@pytest.mark.dependency(depends=["test_login"])
def test_create_character(client: client):
    # create a character with too much stats
    response = client.post("/api/game/create_character", json={
        "name": "good",
        "description": "good",
        "strength": 10,
        "dexterity": 10,
        "health": 10,
        "special": "lightning"
    }, headers=with_auth_headers())
    assert_json_status(response, BadRequest.code)

    # create a character for "GOOD"
    response = client.post("/api/game/create_character", json={
        "name": "good",
        "description": "good",
        "strength": 5,
        "dexterity": 10,
        "health": 5,
        "special": "lightning"
    }, headers=with_auth_headers(credentials=CREDENTIALS_GOOD))
    assert_json_status(response, OK_STATUS)

    # create a character for "ALT"
    response = client.post("/api/game/create_character", json={
        "name": "alt",
        "description": "alt",
        "strength": 10,
        "dexterity": 1,
        "health": 9,
        "special": "wither"
    }, headers=with_auth_headers(credentials=CREDENTIALS_ALT))
    assert_json_status(response, OK_STATUS)


@pytest.mark.dependency(depends=["test_create_character"])
def test_create_challenge(client: client):
    # send a challenge from GOOD to ALT
    response = client.post("/api/game/challenge", json={
        "defender": CREDENTIALS_ALT["username"],
        "challenge_config": {
            "max_turns": 5,
            "character": "good"
        }
    }, headers=with_auth_headers())
    assert_json_status(response, OK_STATUS)
    VARS["challenge_id"] = response.json["challenge_id"]


@pytest.mark.dependency(depends=["test_create_challenge"])
def test_decide_challenge(client: client):
    # accept the challenge as ALT
    response = client.post("/api/game/challenge/decide", json={
        "id": VARS["challenge_id"],
        "accept": True,
        "character": "alt"
    }, headers=with_auth_headers(credentials=CREDENTIALS_ALT))
    assert_json_status(response, OK_STATUS)
    VARS["game_id"] = response.json["game_id"]


@pytest.mark.dependency(depends=["test_decide_challenge"])
def test_play_game(client: client):
    # first, check if the game exists
    response = client.get("/api/game/play?id={0}".format(VARS["game_id"]))
    assert_json_status(response, OK_STATUS)
    turn_username = response.json["data"]["turn"]
    assert turn_username in (c["username"] for c in (CREDENTIALS_GOOD, CREDENTIALS_ALT))

    turn_credentials = from_username(turn_username)
    not_turn_credentials = other_user(credentials=turn_credentials)

    # try to play when it isn't our turn
    response = client.post("/api/game/play", json={
        "id": VARS["game_id"],
        "move": "grapple"
    }, headers=with_auth_headers(credentials=not_turn_credentials))
    assert_json_status(response, BadRequest.code)

    # make a valid play
    response = client.post("/api/game/play", json={
        "id": VARS["game_id"],
        "move": "punch"
    }, headers=with_auth_headers(credentials=turn_credentials))
    assert_json_status(response, OK_STATUS)
    assert response.json["data"]["turn"] == not_turn_credentials["username"]


# STORIES


@pytest.mark.dependency(depends=["test_login"])
def test_create_story(client: client):
    # create story without auth
    response = client.post("/api/story")
    assert_json_status(response, Unauthorized.code)

    # create story with defaults
    response = client.post("/api/story", headers=with_auth_headers())
    assert_json_status(response, OK_STATUS)
    VARS["story_public"] = response.json
    assert "id" in VARS["story_public"]
    assert "sentences" in VARS["story_public"]
    assert "public" in VARS["story_public"]
    assert "media" in VARS["story_public"]
    assert "url" in VARS["story_public"]
    assert VARS["story_public"]["public"] is True

    # create private story
    response = client.post("/api/story", headers=with_auth_headers(), json={"public": False})
    assert_json_status(response, OK_STATUS)
    VARS["story_private"] = response.json
    assert "id" in VARS["story_private"]
    assert "sentences" in VARS["story_private"]
    assert "public" in VARS["story_private"]
    assert "media" in VARS["story_private"]
    assert "url" in VARS["story_private"]
    assert VARS["story_private"]["public"] is False


@pytest.mark.dependency(depends=["test_create_story"])
def test_list_own_stories(client: client):
    # list own stories without auth
    response = client.get("/api/stories")
    assert_json_status(response, Unauthorized.code)

    # list own stories with auth
    response = client.get("/api/stories", headers=with_auth_headers())
    assert_json_status(response, OK_STATUS)
    assert len(response.json) is 2


@pytest.mark.dependency(depends=["test_create_story"])
def test_list_user_stories(client: client):
    # list public stories (without auth)
    response = client.get("/api/stories/user/{0}".format(CREDENTIALS_GOOD["username"]))
    assert_json_status(response, OK_STATUS)
    for story in response.json:
        assert story["public"] is True

    # list all stories (with auth)
    response = client.get("/api/stories/user/{0}".format(CREDENTIALS_GOOD["username"]), headers=with_auth_headers())
    assert_json_status(response, OK_STATUS)


@pytest.mark.dependency(depends=["test_create_story"])
def test_get_story_info(client: client):
    # get public story (without auth)
    response = client.get("/api/story/{0}".format(VARS["story_public"]["id"]))
    assert_json_status(response, OK_STATUS)
    assert response.json["id"] == VARS["story_public"]["id"]
    assert response.json["author"] == CREDENTIALS_GOOD["username"]

    # get private story (without auth)
    response = client.get("/api/story/{0}".format(VARS["story_private"]["id"]))
    assert_json_status(response, Unauthorized.code)

    # get private story (with auth)
    response = client.get("/api/story/{0}".format(VARS["story_private"]["id"]), headers=with_auth_headers())
    assert_json_status(response, OK_STATUS)
    assert response.json["id"] == VARS["story_private"]["id"]
    assert response.json["author"] == CREDENTIALS_GOOD["username"]

    # get non-existent story
    response = client.get("/api/story/{0}".format("not_a_story"))
    assert_json_status(response, NotFound.code)


@pytest.mark.dependency(depends=["test_create_story"])
def test_play_story(client: client):
    # play public story (without auth)
    response = client.get("/api/story/{0}/play".format(VARS["story_public"]["id"]))
    assert response.status_code == OK_STATUS

    # play private story (without auth)
    response = client.get("/api/story/{0}/play".format(VARS["story_private"]["id"]))
    assert response.status_code == Unauthorized.code

    # play private story (with auth)
    response = client.get("/api/story/{0}/play".format(VARS["story_private"]["id"]), headers=with_auth_headers())
    assert response.status_code == OK_STATUS

    # play non-existent story (without auth)
    response = client.get("/api/story/{0}/play".format("not_a_story"))
    assert response.status_code == NotFound.code


@pytest.mark.dependency(depends=["test_play_story"])
def test_edit_story(client: client):
    # edit story (without auth)
    response = client.put("/api/story/{0}".format(VARS["story_private"]["id"]), json={"public": True})
    assert_json_status(response, Unauthorized.code)

    # edit story (with auth)
    response = client.put("/api/story/{0}".format(VARS["story_private"]["id"]), json={"public": True},
                          headers=with_auth_headers())
    assert_json_status(response, OK_STATUS)

    # check if story is now public
    response = client.get("/api/story/{0}".format(VARS["story_private"]["id"]))
    assert_json_status(response, OK_STATUS)


@pytest.mark.dependency(depends=["test_play_story"])
def test_delete_story(client: client):
    # delete story (without auth)
    response = client.delete("/api/story/{0}".format(VARS["story_public"]["id"]))
    assert_json_status(response, Unauthorized.code)

    # delete story (with auth)
    response = client.delete("/api/story/{0}".format(VARS["story_public"]["id"]), headers=with_auth_headers())
    assert_json_status(response, OK_STATUS)

    # check if deleted story is really gone
    response = client.get("/api/story/{0}".format(VARS["story_public"]["id"]))
    assert_json_status(response, NotFound.code)
