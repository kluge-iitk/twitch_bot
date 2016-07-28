#!/usr/bin/env python3
# TODO:
# - implement Logging/DEBUG (5.)
# - Make functions(commands) specific to a stream / generic (4.)
# - Properly implement a QUEUE structure (honestly this should be top priority) (1.)
# - Multi Streams feature or Package as an exe (6.)
# - If exe, have way for streamers to make CLIENT_ID , RIOT_API_KEY (7.)
# - Implement way to incorporate Rate Limits (2.)
# - Implement twitch TAGS (3.)

import re
import socket
from collections import deque
import time
from riotwatcher import RiotWatcher
import riotwatcher
import random
from urllib.request import urlopen
import json
import requests
import webbrowser
import threading
import configparser

# --------------------------------------------- Start Settings ----------------------------------------------------
parser = configparser.ConfigParser()
parser.read('config.ini')
artemis = parser['artemis']
HOST = artemis["HOST"]  # Hostname of the IRC-Server in this case twitch's
PORT = int(artemis["PORT"])  # Default IRC-Port
CHAN = artemis["chan"]  # Channelname = #{Nickname} all lower case
NICK = artemis["NICK"]  # Nickname = Twitch username
PASS = artemis["PASS"]  # www.twitchapps.com/tmi/ will help to retrieve the required authkey
RIOT_API = artemis["RIOT_API"]  # Riot_API_Key https://developer.riotgames.com/
VIEWERLIST_URL = 'https://tmi.twitch.tv/group/user/{}/chatters'
STREAM_URL = 'https://api.twitch.tv/kraken/streams/{}'
CLIENT_ID = artemis["CLIENT_ID"]
CHROME_PATH = 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe %s'

with open(artemis["artyquotes"], 'r') as f:
    artyquotes = json.load(f)
# --------------------------------------------- End Settings -------------------------------------------------------


# --------------------------------------------- Start Functions ----------------------------------------------------
def send_pong(msg):
    print(time.ctime(), ': PONG')
    con.send(bytes('PONG %s\r\n' % msg, 'UTF-8'))


def send_message(chan, msg):
    # print('Sending PRIVMSG %s :%s\r\n' % (chan, msg), 'UTF-8')
    con.send(bytes('PRIVMSG %s :%s\r\n' % (chan, msg), 'UTF-8'))


def send_nick(nick):
    con.send(bytes('NICK %s\r\n' % nick, 'UTF-8'))


def send_pass(password):
    con.send(bytes('PASS %s\r\n' % password, 'UTF-8'))


def join_channel(chan):
    con.send(bytes('JOIN %s\r\n' % chan, 'UTF-8'))


def part_channel(chan):
    con.send(bytes('PART %s\r\n' % chan, 'UTF-8'))


# --------------------------------------------- End Functions ------------------------------------------------------


# --------------------------------------------- Start Helper Functions ---------------------------------------------
regions = {'br': riotwatcher.BRAZIL,
           'eune': riotwatcher.EUROPE_NORDIC_EAST,
           'euw': riotwatcher.EUROPE_WEST,
           'kr': riotwatcher.KOREA,
           'lan': riotwatcher.LATIN_AMERICA_NORTH,
           'las': riotwatcher.LATIN_AMERICA_SOUTH,
           'na': riotwatcher.NORTH_AMERICA,
           'oce': riotwatcher.OCEANIA,
           'ru': riotwatcher.RUSSIA,
           'tr': riotwatcher.TURKEY}


def get_viewers(chan):
    r = urlopen(VIEWERLIST_URL.format(CHAN.strip('#'))).read().decode('UTF-8')
    q = json.loads(r)
    viewers = []
    for viewer_type, viewer in q['chatters'].items():
        viewers.extend(viewer)
    # viewers.remove('moobot')
    # viewers.remove('artemisrankbot')
    return viewers


def get_mods(chan):
    r = urlopen(VIEWERLIST_URL.format(CHAN.strip('#'))).read().decode('UTF-8')
    q = json.loads(r)
    mods = q['chatters']['moderators']
    # mods.remove('moobot')
    # mods.remove('artemisrankbot')
    return mods


def get_followers():
    f_list = []
    cur_url = 'https://api.twitch.tv/kraken/channels/{}/follows?'.format(CHAN.strip('#'))
    headers = {'Cache-Control': 'no-cache, no-store, must-revalidate',
               'Pragma': 'no-cache',
               'Expires': '0'}

    while 1:
        # print("Current List: {}, {}".format(len(f_list), f_list))
        r = requests.get(cur_url, params={'client_id': CLIENT_ID, 'limit': '100'}, headers=headers, timeout=2).json()
        # print("{} \n\n".format(len(r['follows'])))
        if len(r['follows']) == 0:
            break
        for user in r['follows']:
            user_vals = user['user']
            f_list.append(user_vals['name'])
        cur_url = r['_links']['next']
        if r['follows'][-1]['user']['name'] in followers:
            break
    return f_list


def stream_status(chan):
    try:
        j = requests.get(STREAM_URL.format(chan), params={'client_id': CLIENT_ID}, timeout=2).json()
        status = j['stream']
        if j['stream']:
            return 1
        else:
            return 0
    except KeyError:
        return -1
    except Exception as e:
        return 0


class RateLimit:
    def __init__(self, allowed_requests, seconds):
        self.allowed_requests = allowed_requests
        self.seconds = seconds
        self.made_requests = deque()

    def __reload(self):
        t = time.time()
        while len(self.made_requests) > 0 and self.made_requests[0] < t:
            self.made_requests.popleft()

    def add_request(self):
        self.made_requests.append(time.time() + self.seconds)

    def request_available(self):
        self.__reload()
        return len(self.made_requests) < self.allowed_requests


class TwitchWatcher:
    def __init__(self, limits=(RateLimit(1, 5), RateLimit(1, 15), RateLimit(1, 20), RateLimit(1, 20))):
        self.ranklimit, self.infolimit, self.viewerslimit, self.stream = limits
        self.browser_open = False

    def can_send_msg(self, limit):
        if not limit.request_available():
            return False
        return True

    def stream_status(self, sender, _=None):
        _ = [k.lower() for k in _]
        if len(_) == 2:
            stream = _[1]
            r = stream_status(stream)
            if self.stream.request_available():
                if r == 0:
                    send_message(CHAN, "@{} Channel {} is OFFline".format(sender, stream))
                elif r == 1:
                    send_message(CHAN, "@{} Channel {} is ONline".format(sender, stream))
                elif r == -1:
                    send_message(CHAN, "@{} Channel {} not found".format(sender, stream))
                self.stream.add_request()

    def command_info(self, sender, _=None):
        if self.infolimit.request_available():
            send_message(CHAN, "This bot accepts the '!boosted' command to find your league" +
                         " LP. Type in '!boosted IGN REGION'" +
                         " REGION can take na/euw/eune/las/lan/oce/tr/ru/br/kr." + " 5 Second CD"
                         + " '!rv x': randomly selects [x] viewers (mod-only command)")
            self.infolimit.add_request()

    def command_rank(self, sender, _a=None):
        _a = [k.lower() for k in _a]
        # print(_a)
        _ = _a[-1]
        if _ in regions.keys():
            region = regions[_]
            _a.pop()
        else:
            region = riotwatcher.NORTH_AMERICA
        # print(_a, region)
        _a.pop(0)
        _a = ''.join(_a)
        # print(_a, region)
        try:
            requested = riotid.get_summoner(name=_a, region=region)
            requested_id = requested['id']
            # print('id',requested_id)
            stats = riotid.get_league_entry([requested_id], region=region)
            tier = stats[str(requested_id)][0]
            stats = tier['entries'][0]
            message = "{} ---- Player: {}, Region: {}, Rank: {} {} {} LP ----".format(sender,
                                                                                      stats['playerOrTeamName'],
                                                                                      region.upper(),
                                                                                      tier['tier'],
                                                                                      stats['division'],
                                                                                      stats['leaguePoints'])
        except Exception as e:
            print(e)
            if _a:
                message = "Can't find summoner"
            else:
                message = "Yes Artemis is a Boosted Animal"

        # print(message)
        if sender == CHAN.strip('#') or sender == "poppy92":
            send_message(CHAN, message)
        elif self.ranklimit.request_available():
            send_message(CHAN, message)
            self.ranklimit.add_request()

    def print_viewers(self, sender, _=None):
        v_list = get_viewers(CHAN)
        try:
            n = int(_[1])
        except:
            n = 1
        print(v_list)
        if self.viewerslimit.request_available() and sender in get_mods(CHAN):
            message = str(len(v_list)) + ' viewers.'
            send_message(CHAN, message)
            ##            try:
            ##                selected = random.sample(v_list, n)
            ##            except:
            ##                selected = ['there was an error']
            ##            print(selected)
            ##            send_message(CHAN, "testing- {} random viewers selected: {}".format(n,
            ##                ', '.join(selected)))
            self.viewerslimit.add_request()

    def set_duo(self, sender, _=None):
        if sender == CHAN.strip('#') or sender in get_mods(CHAN):
            try:
                self._duo = ' '.join(_[1:])
            except Exception as e:
                print('could not set duo', e)

    def duo(self, sender, _=None):
        try:
            send_message(CHAN, "Artemis is duo with {}".format(self._duo))
        except Exception as e:
            print('could not print duo', e)

    def discord(self, sender, _=None):
        send_message(CHAN, 'https://discord.gg/vJgyQDX')

    def twitter(self, sender, _=None):
        send_message(CHAN, 'https://twitter.com/CC_Artemis')

    def snapchat(self, sender, _=None):
        send_message(CHAN, 'Add Artemis on snapchat: Connordoyle11')

    def adc(self, sender, _=None):
        try:
            send_message(CHAN, self._adc)
        except Exception as e:
            send_message(CHAN, 'jhin > ashe / lucian > sivir > cait')

    def setadc(self, sender, _=None):
        if sender == CHAN.strip('#') or sender in get_mods(CHAN):
            try:
                self._adc = ' '.join(_[1:])
            except Exception as e:
                print('could not set duo', e)

    def mouse(self, sender, _=None):
        send_message(CHAN, '4th tick windows sensitivity, 1200 DPI, 30 in game')

    def quot(self, sender, _=None):
        if sender == CHAN.strip('#') or sender in get_mods(CHAN) or sender == "conandbarbarian":
            send_message(CHAN, random.choice(artyquotes))

    def addquot(self, sender, _=None):
        artyquotes.append(' '.join(_[1:]))
        with open('artyquot.lol', 'w') as f:
            f.write(artyquotes)


def get_sender(msg):
    result = ""
    for char in msg:
        if char == "!":
            break
        if char != ":":
            result += char
    return result


def get_message(msg):
    result = ""
    i = 3
    length = len(msg)
    while i < length:
        result += msg[i] + " "
        i += 1
    result = result.lstrip(':')
    return result


def parse_message(sender, msg, _id):
    if len(msg) >= 1:
        msg = msg.strip().split(' ')
        options = {'!how2': _id.command_info,
                   '!boosted': _id.command_rank,
                   '!rv': _id.print_viewers,
                   '!isitonline': _id.stream_status,
                   '!setduo': _id.set_duo,
                   '!duo': _id.duo,
                   '!discord': _id.discord,
                   '!twitter': _id.twitter,
                   '!snapchat': _id.snapchat,
                   '!adc': _id.adc,
                   '!setadc': _id.setadc,
                   '!mouse': _id.mouse,
                   '!quote': _id.quot,
                   '!addquote': _id.addquot}
        if msg[0].lower() in options:
            options[msg[0]](sender, msg)


# --------------------------------------------- End Helper Functions -----------------------------------------------


# --------------------------------------------- Start Command Functions --------------------------------------------

# --------------------------------------------- End Command Functions ----------------------------------------------

con = socket.socket()
con.connect((HOST, PORT))
# print('reached CON')
with open(artemis["followers"], 'r') as f:
    m = json.load(f)
    followers = set(m.keys())

print(len(followers))

print('reached FOLLOWERS')
send_pass(PASS)
send_nick(NICK)
con.send(bytes('CAP REQ :twitch.tv/membership\r\n', 'UTF-8'))
con.send(bytes('CAP REQ :twitch.tv/commands\r\n', 'UTF-8'))
# con.send(bytes('CAP REQ :twitch.tv/tags\r\n', 'UTF-8'))
join_channel(CHAN)
# send_message(CHAN, "Joining boosted {}'s stream:".format(CHAN.strip('#'))+
#             " MrDestructoid")

twitchid = TwitchWatcher()
riotid = RiotWatcher(RIOT_API)


def follows_thread():
    global followers
    print(time.ctime(), 'starting followers thread\n')
    while 1:
        new_f = set(get_followers())

        diff = new_f - followers
        # print(time.ctime(), diff)
        if diff:
            for user in diff:
                try:
                    r = requests.get('https://api.twitch.tv/kraken/channels/{}/'.format(user),
                                     params={'client_id': CLIENT_ID},
                                     headers={'User-agent': 'Mozilla/5.0'}, timeout=2).json()
                    m[user] = r['display_name']
                    send_message(CHAN, "Welcome to the Boosted Animals HeyGuys {}!".format(m[user]))
                except Exception as e:
                    pass

        followers.update(diff)
        if diff:
            with open('artemis_follows.haha', 'w') as f:
                f.write(json.dumps(m))

        stream = stream_status(CHAN.strip('#'))
        # print(time.ctime(), 'stream status:', stream)
        if stream == 1:
            # print (time.ctime(), 'if', twitchid.browser_open)
            if not twitchid.browser_open:
                twitchid.browser_open = True
                webbrowser.get(CHROME_PATH).open_new_tab('twitch.tv/{}'.format(CHAN.strip('#')))
            time.sleep(20)
        else:
            # print(time.ctime(), 'going to sleep 2 min')
            twitchid.browser_open = False
            # print(time.ctime(), 'else', twitchid.browser_open)
            time.sleep(120)


def main_thread():
    global con
    con = socket.socket()
    con.connect((HOST, PORT))
    send_pass(PASS)
    send_nick(NICK)
    con.send(bytes('CAP REQ :twitch.tv/membership\r\n', 'UTF-8'))
    con.send(bytes('CAP REQ :twitch.tv/commands\r\n', 'UTF-8'))
    join_channel(CHAN)
    data = ""
    print(time.ctime(), 'starting main thread', CHAN, '\n')
    start = time.time()
    while 1:
        if len(data) == 0:
            data = ""
        received = con.recv(1024).decode('UTF-8')
        if time.time() - start > 30:
            print(time.ctime(), ": MAIN THREAD :", repr(received))
            start = time.time()
        data = data + received
        data_split = re.split(r"[~\r\n]+", data)
        data = data_split.pop()

        for line in data_split:
            line = str.rstrip(line)
            line = str.split(line)
            # print(line)
            if len(line) >= 1:
                if line[0] == 'PING':
                    send_pong(line[1])

                if line[1] == 'PRIVMSG':
                    sender = get_sender(line[0])
                    message = get_message(line)
                    parse_message(sender, message, twitchid)
                    try:
                        print(time.ctime(), sender + ": " + message)
                        pass
                    except Exception as e:
                        print(time.ctime(), e)


def thread_wrap(func):
    def wrapper():
        global con
        while True:
            try:
                func()
            except socket.error as e:
                print(time.ctime(), func.__name__, e, "Socket died")
                stream = stream_status(CHAN.strip('#'))
                if stream == 1:
                    time.sleep(5)
                else:
                    time.sleep(30)
            except socket.timeout as e:
                print(time.ctime(), func.__name__, e, "Socket timeout")
                stream = stream_status(CHAN.strip('#'))
                if stream:
                    time.sleep(5)
                else:
                    time.sleep(30)
            except Exception as e:
                print(time.ctime(), func.__name__, '{!r}; restarting thread'.format(e))
                stream = stream_status(CHAN.strip('#'))
                time.sleep(60)
            else:
                print(time.ctime(), func.__name__, 'exited normally, bad thread; restarting')
            if func.__name__ == "main_thread":
                # con.shutdown(socket.SHUT_RDWR)
                con.close()

    return wrapper


# import pdb
# pdb.run('')
if __name__ == "__main__":
    chan = input("Enter the channel name prefixed with # (#scarra):").lower().strip()
    if chan:
        CHAN = chan
    followers_stream = threading.Thread(target=thread_wrap(follows_thread))  # or could decorate the thread functions
    followers_stream.start()

    mains_thread = threading.Thread(target=thread_wrap(main_thread))  # with @thread_wrap
    mains_thread.start()

    followers_stream.join()
    mains_thread.join()
