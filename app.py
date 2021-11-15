import atexit
import json
import time
import random
import sys
import signal

import requests
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

def send_message(message):
    url = "https://api.groupme.com/v3/bots/post"
    data = { "bot_id": bot_id, "text": message }
    requests.post(url, json.dumps(data))

def get_members(group_id):
    global token
    url = "https://api.groupme.com/v3/groups/{}?token={}".format(group_id, token)
    r = requests.get(url)
    members = r.json()["response"]["members"]
    member_ids = {}
    for m in members:
        member_ids[m["user_id"]] = m["nickname"]
    return member_ids

def hit_or_miss(duck_time, shoot_time, full_word):
    """
    Return chance to hit, lower chance if fast response (active chat)

    Odds are worse if the abbreviation (/ban, /bef) is typed instead 
    of full word (/bang, /befriend)

    Don't say anything if you find this in my source code, it's funny
    """
    if full_word:
        if 0 <= shoot_time - duck_time <= 30:
            chance = random.uniform(.6, .75)
        else:
            chance = random.uniform(.75, .9)
    else:
        if 0 <= shoot_time - duck_time <= 30:
            chance = random.uniform(.3, .4)
        else:
            chance = random.uniform(.4, .6)
    return chance

def bang(data, full_word):
    global game_status, duck_data, delayed
    if not game_status["game_on"]:
        send_message("No active game.")
        return
    sender_name = data["name"]

    try:
        with open("data/miss.json", "r") as f:
            d = json.load(f)
            miss_bang = d["miss_bang"]
    except:
        sys.stdout.write("data/miss.json not found or corrupted.")
        sys.stdout.flush()
        miss_bang = ["You missed, but the messages are broken."]

    if game_status["duck_active"]:
        shoot_time = time.time()
        sender_id = data["sender_id"]
        chance = hit_or_miss(game_status["duck_time"], shoot_time, full_word)
        
        if sender_id in delayed:
            if shoot_time <= delayed[sender_id]:
                send_message("{}, can you maybe chill?".format(sender_name))
                return
            else:
                del delayed[sender_id]

        if random.random() >= chance:
            # Miss
            delay_time = random.randint(15, 120)
            send_message(random.choice(miss_bang) + " {}, try again in {} seconds.".format(sender_name, str(delay_time)))
            delayed[sender_id] = shoot_time + delay_time
        else:
            taken = shoot_time - game_status["duck_time"]
            game_status["duck_active"] = False
            message = "{}, you shot a duck in {:.2f} seconds! You've shot {} "

            if sender_id in duck_data["bang"]:
                duck_data["bang"][sender_id] += 1
                message += "ducks."
                if duck_data["bang"][sender_id] % 100 == 69:
                    message += " (nice)"
            else:
                duck_data["bang"][sender_id] = 1
                message += "duck."
            message += "\n"
            send_message(message.format(sender_name, taken, duck_data["bang"][sender_id]))

    else:
        send_message("WTF {}, you tried to shoot a duck that's not there.".format(sender_name))

def befriend(data, full_word):
    global game_status, duck_data, delayed
    if not game_status["game_on"]:
        send_message("No active game.")
        return
    sender_name = data["name"]

    try:
        with open("data/miss.json", "r") as f:
            d = json.load(f)
            miss_befriend = d["miss_befriend"]
    except:
        sys.stdout.write("data/miss.json not found.")
        sys.stdout.flush()
        miss_befriend = ["You failed, but the messages are broken."]

    if game_status["duck_active"]:
        bef_time = time.time()
        sender_id = data["sender_id"]
        chance = hit_or_miss(game_status["duck_time"], bef_time, full_word)

        if sender_id in delayed:
            if bef_time <= delayed[sender_id]:
                send_message("{}, can you maybe chill?".format(sender_name))
                return
            else:
                del delayed[sender_id]

        if random.random() >= chance:
            # Fail
            delay_time = random.randint(15, 120)
            send_message(random.choice(miss_befriend) + " {}, try again in {} seconds.".format(sender_name, str(delay_time)))
            delayed[sender_id] = bef_time + delay_time
        else:
            # Success
            taken = bef_time - game_status["duck_time"]
            game_status["duck_active"] = False
            message = "{}, you made friends with a duck in {:.2f} seconds! You have {} duck "

            if sender_id in duck_data["befriend"]:
                duck_data["befriend"][sender_id] += 1
                message += "friends."
                if duck_data["befriend"][sender_id] % 100 == 69:
                    message += " (nice)"
            else:
                duck_data["befriend"][sender_id] = 1
                message += "friend."
            message += "\n"
            send_message(message.format(sender_name, taken, duck_data["befriend"][sender_id]))

    else:
        send_message("{}, you tried to befriend a duck that's not there, pretty creepy dude..".format(sender_name))

def duck_stats(data):
    global duck_data
    member_ids = get_members(data["group_id"])
    bang_data = []
    befriend_data = []
    strlen = 30
    namelen = 20 

    for uid in duck_data["bang"]:
        bang_data.append((uid, duck_data["bang"][uid]))
    for uid in duck_data["befriend"]:
        befriend_data.append((uid, duck_data["befriend"][uid]))

    bang_data.sort(reverse=True, key=lambda x: x[1])
    befriend_data.sort(reverse=True, key=lambda x: x[1])
    
    message = "Top duck shooters:\n"
    for uid, n in bang_data:
        nick = member_ids[uid][0:namelen]
        num_gap = strlen - len(nick) - len(str(n))
        underscores = "_" * num_gap
        message += "{}{}{}".format(nick, underscores, n) 
        if n % 100 == 69:
            message += " (nice)\n"
        else:
            message += "\n"

    message += "\nTop duck friends:\n"
    for uid, n in befriend_data:
        nick = member_ids[uid][0:namelen]
        num_gap = strlen - len(nick) - len(str(n))
        underscores = "_" * num_gap
        message += "{}{}{}".format(nick, underscores, n) 
        if n % 100 == 69:
            message += " (nice)\n"
        else:
            message += "\n"

    send_message(message)

def deploy_duck():
    """Sorta randomize the duck message."""
    global game_status
    try:
        with open("data/duck.json", "r") as f:
            d = json.load(f)
            duck_tail = d["duck_tail"]
            duck = d["duck"]
            duck_noise = d["duck_noise"]
    except:
        sys.stdout.write("data/duck.json not found or parsing failed.")
        sys.stdout.flush()
        game_status["duck_active"] = False
        return

    rt = random.randint(1, len(duck_tail) - 1)
    dtail = duck_tail[:rt] + u' \u200b ' + duck_tail[rt:]
    dbody = random.choice(duck)
    rb = random.randint(1, len(dbody) - 1)
    dbody = dbody[:rb] + u'\u200b' + dbody[rb:]
    dnoise = random.choice(duck_noise)
    rn = random.randint(1, len(dnoise) - 1)
    dnoise = dnoise[:rn] + u'\u200b' + dnoise[rn:]

    duck_string = dtail + dbody + dnoise
    game_status["duck_string"] = duck_string
    game_status["duck_noise"] = dnoise
    send_message(duck_string)

def check_duck():
    global game_status

    # If the duck has been sent but not verified, send another
    if game_status["game_on"] and game_status["duck_active"] and not game_status["msg_verified"]:
        sys.stdout.write("Re-deploying duck because verification failed...\n")
        send_message(game_status["duck_string"])

    # If there's no duck and no next duck time, then set a next duck time
    if game_status["game_on"] and not game_status["duck_active"] and not game_status["next_duck_time_set"]:
        sys.stdout.write("Setting next duck time...\n")
        # game_status["next_duck_time"] = random.randint(int(time.time()) + 10800, int(time.time()) + 21600) # 3 hours to 6 hours
        game_status["next_duck_time"] = random.randint(int(time.time()) + 21600, int(time.time()) + 43200) # 6 hours to 12 hours
        sys.stdout.write("Making duck. " + str(game_status["next_duck_time"] - time.time()) + " seconds from now\n")
        game_status["next_duck_time_set"] = True

    # If there's no duck and the next duck time has passed, then deploy a duck
    if game_status["game_on"] and not game_status["duck_active"] and game_status["next_duck_time_set"] and game_status["next_duck_time"] < time.time():
        sys.stdout.write("Deploying a new duck...\n")
        game_status["duck_active"] = True
        game_status["next_duck_time_set"] = False
        game_status["duck_time"] = time.time()
        deploy_duck()


    sys.stdout.flush()

def write_duck_data():
    global duck_data
    with open("duck_data.json", "w") as f:
        json.dump(duck_data, f)

def handle_exit(*args):
    global scheduler
    write_duck_data()
    try:
        scheduler.shutdown()
    except:
        pass

@app.route('/', methods=['POST'])
def new_message():
    global game_status
    data = json.loads(request.data)

    text = data["text"].strip()

    # Nice feature for debugging but ripe for abuse with public source code and no user verification
    # if text.lower().startswith("/duckstart"):
    #     game_status["game_on"] = True
    #     send_message("Started.")
    # if text.lower().startswith("/duckstop"):
    #     game_status["game_on"] = False
    #     send_message("Stopped.")

    if not game_status["game_on"]:
        return ""

    if game_status["next_duck_time_set"]:
        game_status["next_duck_time"] = game_status["next_duck_time"] - 90

    if data["sender_type"] == "bot":
        if game_status["duck_active"] and not game_status["msg_verified"] and game_status["duck_noise"] in text:
            game_status["msg_verified"] = True
        return ""
    
    if text.lower().startswith("/bang"):
        bang(data, True)
        return "" 

    if text.lower().startswith("/befriend"):
        befriend(data, True)
        return "" 

    if text.lower().startswith("/ban"):
        bang(data, False)
        return "" 
 
    if text.lower().startswith("/bef"):
        befriend(data, False)
        return "" 

    if text.lower().startswith("/duckstats"):
        duck_stats(data)
        return "" 




# Global variables
try:
    with open("bot_id.txt", "r") as f:
        bot_id = f.read()
except FileNotFoundError:
    sys.stdout.write("No bot ID found at bot_id.txt")
    sys.stdout.flush()
    sys.exit(1)

try:
    with open("token.txt", "r") as f:
        token = f.read()
except FileNotFoundError:
    sys.stdout.write("No user token found at token.txt")
    sys.stdout.flush()
    sys.exit(1)

try:
    with open("duck_data.json", "r") as f:
        duck_data = json.load(f)
except FileNotFoundError:
    sys.stdout.write("No duck_data.json found, creating a fresh entry.")
    sys.stdout.flush()
    duck_data = {
        "bang": {},
        "befriend": {}
    }


game_status = {
        "game_on": True,
        "duck_active": False,
        "duck_time": -1,
        "next_duck_time": -1,
        "next_duck_time_set": False,
        "duck_string": "",
        "duck_noise": "",
        "msg_verified": False
}
delayed = {}

# Initialize background tasks
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_duck, trigger="interval", seconds=60)
scheduler.add_job(func=write_duck_data, trigger="interval", hours=24)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(handle_exit)
signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

