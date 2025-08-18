from contextlib import closing

import fitbit
from fitbit import FitbitOauth2Client
import json
from flask import Flask, request
import threading
import sqlite3
import datetime
from slack_bolt import App as SlackApp
from slack_bolt.adapter.socket_mode import SocketModeHandler
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()

with open("keys.json", "r") as the_file:
    KEYS = json.load(the_file)

"""
keys.json is a file with the contents:

{
    "fitbit_client_id": "",
    "fitbit_client_secret": "",
    "slack_signing_secret": "",
    "slack_app_token": "",
    "slack_bot_token": "",
    "slack_bot_id": "",
    "port": 3100
}
"""

flask_app = Flask(__name__)

slack_app = SlackApp(signing_secret=KEYS["slack_signing_secret"], token=KEYS["slack_bot_token"])
fitbit_auth_client = FitbitOauth2Client(KEYS["fitbit_client_id"], KEYS["fitbit_client_secret"])
#print(f"auth url: {fitbit_auth_client.authorize_token_url(scope=["activity", "sleep", "settings"], state=fitbit_auth_client.session.new_state())}")



def get_auth_url(slack_user_id, slack_display_name=""):
    state = fitbit_auth_client.session.new_state()
    url = fitbit_auth_client.authorize_token_url(scope=["activity", "sleep", "settings"], state=state)
    fitbit_auth_client.refresh_token()
    try:
        with sqlite3.connect("main.db") as conn:
            with closing(conn.cursor()) as cur:
                cur.execute("SELECT channel_id, minimum_steps, send_daily_stats, send_sleep, do_ping_in_daily_stats, utc_daily_stats_time FROM users WHERE slack_user_id = ?", (slack_user_id,))
                config = cur.fetchone()
                if not config:
                    config = (0, 2000, 1, 1, 0, 2200)
                    cur.execute("REPLACE INTO users(slack_user_id, slack_display_name, fitbit_access_token, fitbit_refresh_token, fitbit_state, channel_id, minimum_steps, send_daily_stats, send_sleep, do_ping_in_daily_stats, utc_daily_stats_time)"
                                "values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (slack_user_id, slack_display_name, "", "", state, *config))
                else:
                    cur.execute("""UPDATE users
                                SET fitbit_state = ?
                                WHERE slack_user_id = ?""", (state, slack_user_id,))

    except Exception as e:
        print(f"error in oauth url generator sql: {e}")
        return "https://uhoh"

    return url


@flask_app.route("/fitbit/oauth")
def fitbit_oauth_callback():
    if "code" in request.args:
        try:
            fitbit_token = fitbit_auth_client.fetch_access_token(request.args["code"])

            fitbit_client = fitbit.Fitbit(KEYS["fitbit_client_id"], KEYS["fitbit_client_secret"], access_token=fitbit_token["access_token"], refresh_token=fitbit_token["refresh_token"])
            activities = fitbit_client.activities() # this exists i promise
            #print(fitbit_client.get_sleep(datetime.date.today()))
            #print(activities)
            #print(f"""
            #Steps today: {activities["summary"]["steps"]} (lazy)
            #Active time: {activities["summary"]["lightlyActiveMinutes"] + activities["summary"]["fairlyActiveMinutes"] + activities["summary"]["veryActiveMinutes"]} minutes
            #{round((activities["summary"]["activityCalories"] / activities["summary"]["caloriesOut"]) * 100, 1)}% of burned calories spent on activity
            #""")

            with sqlite3.connect("main.db") as conn:
                with closing(conn.cursor()) as cur:
                    cur.execute("""
                    UPDATE users
                    SET fitbit_access_token = ?,
                        fitbit_refresh_token = ?
                    WHERE fitbit_state = ?
                    """, (fitbit_token["access_token"], fitbit_token["refresh_token"], request.args["state"]))


            with open("oauth_webpage.html", "r") as the_html:
                return the_html.read().replace(
                    "{main_text}", "yay! fitbit is now authenticated!").replace(
                    "{sub_text}", "(you can close this tab now)").replace(
                    "{text_colour}", "rgb(208, 238, 239)")
            # normal text colour: rgb(208, 238, 239)
            # error text colour: rgb(255, 122, 122)
        except Exception as e:
            print(f"error in oauth callback: {e}")
            with open("oauth_webpage.html", "r") as the_html:
                return the_html.read().replace(
                    "{main_text}", "oh no there was an error!!").replace(
                    "{sub_text}", f"<p>:( better luck next time</p> <p>Error: {e}</p>\n<p>(Try generating a new login link?)</p>").replace(
                    "{text_colour}", "rgb(255, 122, 122)")
    else:
        with open("oauth_webpage.html", "r") as the_html:
            return the_html.read().replace(
                "{main_text}", "oh no there was an error!!").replace(
                "{sub_text}", f"<p>:( better luck next time</p> <p>Error: url doesn't have an auth code!</p>\n<p>(Try generating a new login link?)</p>").replace(
                "{text_colour}", "rgb(255, 122, 122)")

def sql_setup():
    users_statement = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        
        slack_user_id TEXT UNIQUE,
        slack_display_name TEXT,
        fitbit_access_token TEXT,
        fitbit_refresh_token TEXT,
        fitbit_state TEXT,
        channel_id TEXT,
        minimum_steps INT,
        send_daily_stats INT,
        send_sleep INT,
        do_ping_in_daily_stats INT,
        utc_daily_stats_time TEXT,
        fitbit_token_expires_at INT,
        banned INT,
        last_sleep_count INT,
        last_sleep_endtime TEXT
    )
    """
    with sqlite3.connect("main.db") as conn:
        with closing(conn.cursor()) as cur:
            cur.execute(users_statement)
            conn.commit()


def true_false_to_yes_no(val):
    if val:
        return "Yes!"
    else:
        return "No :("

def test_fitbit_authentication(access_token, refresh_token, slack_user_id, token_expires_at):
    try:
        def refresh_cb(token):
            print(f"refreshing fitbit access tokens")
            with sqlite3.connect("main.db") as conn:
                with closing(conn.cursor()) as cur:
                    cur.execute("""UPDATE users
                                   SET fitbit_access_token     = ?,
                                       fitbit_refresh_token    = ?,
                                       fitbit_token_expires_at = ?
                                   WHERE slack_user_id = ?
                                """,
                                (token["access_token"], token["refresh_token"], token["expires_at"], slack_user_id))
        fitbit.Fitbit(KEYS["fitbit_client_id"], KEYS["fitbit_client_secret"], access_token, refresh_token, token_expires_at, refresh_cb).activities()
        print(fitbit.Fitbit(KEYS["fitbit_client_id"], KEYS["fitbit_client_secret"], access_token, refresh_token, token_expires_at, refresh_cb).get_sleep(datetime.date.today()))
        return True
    except:
        return False

def app_home_steps_option(steps):
    return {
        "text": {
            "type": "plain_text",
            "text": f"{steps}",
            "emoji": True
        },
        "value": f"steps-option-{steps}"
    }

def generate_app_home_steps_options(steps=[0, 1000]):
    options = []
    for step in steps:
        options.append(app_home_steps_option(step))

    return options


send_daily_stats_checkbox = {
    "text": {
        "type": "mrkdwn",
        "text": "*Send daily stats*",
        "verbatim": False
    },
    "description": {
        "type": "mrkdwn",
        "text": "Send your daily steps, active time, and the percentage of calories burned for activity in your channel",
        "verbatim": False
    },
    "value": "value-send-daily-stats"
}
do_ping_in_daily_stats_checkbox = {
    "text": {
        "type": "mrkdwn",
        "text": "*Ping you in daily stats messages*",
        "verbatim": False
    },
    "description": {
        "type": "mrkdwn",
        "text": "Ping you in every daily stats message that is sent (not sleep data because then i'll just wake you up)",
        "verbatim": False
    },
    "value": "value-do_ping_in_daily_stats"
}
send_sleep_checkbox = {
    "text": {
        "type": "mrkdwn",
        "text": "*Send sleep data*",
        "verbatim": False
    },
    "description": {
        "type": "mrkdwn",
        "text": "Send a message when you wake up to say the duration of your sleep",
        "verbatim": False
    },
    "value": "value-send_sleep"
}

@slack_app.event("app_home_opened")
def update_home_tab(client, event):
    print(event)
    #try:
    if event["tab"] == "messages":
        slack_app.client.chat_postEphemeral(channel=event["user"], user=event["user"], text="Hey there! To configure this bot, go to the *home* tab, as in the image below", attachments="https://hc-cdn.hel1.your-objectstorage.com/s/v3/35b4c0c234a7d0f437f99245d469aac098b88635_image.png")

    with sqlite3.connect("main.db") as conn:
        with closing(conn.cursor()) as cur:
            cur.execute("SELECT fitbit_access_token, fitbit_refresh_token, channel_id, minimum_steps, send_daily_stats, send_daily_stats, send_sleep, do_ping_in_daily_stats, utc_daily_stats_time, fitbit_token_expires_at FROM users WHERE slack_user_id = ?", (event["user"],))
            retrieved = cur.fetchone()
            if retrieved:
                fitbit_access_token, fitbit_refresh_token, channel_id, minimum_steps, send_daily_stats, send_daily_stats, send_sleep, do_ping_in_daily_stats, utc_daily_stats_time, fitbit_token_expires_at = retrieved

                authenticated = test_fitbit_authentication(fitbit_access_token, fitbit_refresh_token, event["user"], fitbit_token_expires_at)

                reauth_button_green = {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Re-authenticate",
                                        "emoji": True
                                    },
                                    "style": "primary",
                                    "value": "button-reauth",
                                    "action_id": "button-reauth"
                                }
                reauth_button_default = {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Re-authenticate",
                                        "emoji": True
                                    },
                                    "value": "button-reauth",
                                    "action_id": "button-reauth"
                                }
                initial_checkbox_options = []
                if send_daily_stats: initial_checkbox_options.append(send_daily_stats_checkbox)
                if do_ping_in_daily_stats: initial_checkbox_options.append(do_ping_in_daily_stats_checkbox)
                if send_sleep: initial_checkbox_options.append(send_sleep_checkbox)

                if initial_checkbox_options:
                    checkboxes_accessory = {
                                    "type": "checkboxes",
                                    "initial_options": initial_checkbox_options,
                                    "options": [
                                        send_daily_stats_checkbox,

                                        do_ping_in_daily_stats_checkbox,

                                        send_sleep_checkbox
                                    ],
                                    "action_id": "checkboxes-action"
                                }
                else:
                    checkboxes_accessory = {
                        "type": "checkboxes",
                        "options": [
                            send_daily_stats_checkbox,

                            do_ping_in_daily_stats_checkbox,

                            send_sleep_checkbox
                        ],
                        "action_id": "checkboxes-action"
                    }

                client.views_publish(
                    user_id=event["user"],
                    view={
                        "type": "home",
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"Fitbit authenticated? {true_false_to_yes_no(authenticated)}"
                                },
                                "accessory": reauth_button_default if authenticated else reauth_button_green
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"Channel or conversation to send stats in (please do not choose a channel that isn't yours)\n*You will have to ping <@{slack_app.client.auth_test()["user_id"]}> in the channel to add the bot initially.*"
                                },
                                "accessory": {
                                    "type": "conversations_select",
                                    "initial_conversation": channel_id,
                                    "placeholder": {
                                        "type": "plain_text",
                                        "text": "Select conversations",
                                        "emoji": True
                                    },
                                    "action_id": "conversation-send-select"
                                }
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "Minimum steps to send stats for"
                                },
                                "accessory": {
                                    "type": "static_select",
                                    "placeholder": {
                                        "type": "plain_text",
                                        "text": "Select an item",
                                        "emoji": True
                                    },
                                    "initial_option": app_home_steps_option(minimum_steps),
                                    "options": generate_app_home_steps_options([0, 100, 500, 1000, 2000, 3000, 4000, 5000, 7500, 10000, 12500, 15000, 17500, 20000]),
                                    "action_id": "steps-selection"
                                }
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "Time to send daily stats at"
                                },
                                "accessory": {
                                    "type": "timepicker",
                                    "initial_time": tz_offset_slack_time(utc_daily_stats_time[:5], 0 - int(slack_app.client.users_info(user=event["user"])["user"]["tz_offset"])),
                                    "placeholder": {
                                        "type": "plain_text",
                                        "text": "Select time",
                                        "emoji": True
                                    },
                                    "action_id": "timepicker-send-stats"
                                }
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "Select the options you want!"
                                },

                                "accessory": checkboxes_accessory
                            }
                        ]
                    }
                )

            else:
                client.views_publish(
                    user_id=event["user"],
                    view={
                        "type": "home",
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"Hi! Lets start by getting your fitbit account linked by pressing the green button to the right.\nAfter that, ping <@{slack_app.client.auth_test()["user_id"]}> to add the bot to wherever you want it to send to, then come back here to configure it."
                                },
                                "accessory": {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Re-authenticate",
                                        "emoji": True
                                    },
                                    "style": "primary",
                                    "value": "button-reauth"
                                }
                            }
                        ]})

    #except Exception as e:
    #    print(f"error pushing slack app home tab: {e}")

@slack_app.action("button-reauth")
def reauth_button(ack, body, client):
    #print(body)
    user_id = body["user"]["id"]
    user_profile = client.users_profile_get(user=user_id)
    #print(slack_app.client.users_info(user=user_id))
    #print(user_profile["profile"])
    try:
        display_name = user_profile["profile"]["display_name"]
    except KeyError:
        display_name = user_profile["profile"]["real_name"]

    #print(str(get_auth_url(user_id, display_name)))
    #print(user_id)
    #print(display_name)
    ack()
    client.views_open(
        user_id=body["user"],
        view={
            "type": "modal",
            "title": {
                "type": "plain_text",
                "text": "Fitbit Login",
                "emoji": True
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Press the button to the right to login with your browser"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Authenticate"
                        },
                        "url": get_auth_url(user_id, display_name)[0],
                        "style": "primary",
                        "action_id": "button-web-ignore"
                    }
                }
            ]
        },
        trigger_id=body["trigger_id"]
    )

def button_sql_bits(user_id, value, column, ack):
    try:
        with sqlite3.connect("main.db") as conn:
            with closing(conn.cursor()) as cur:
                cur.execute(f"""
                UPDATE users
                SET {column} = ?
                WHERE slack_user_id = ?
                """, (value, user_id))     # Column name is assumed to be safe! don't user input it
                ack()
    except sqlite3.SQLITE_ERROR as e:
        print(f"Error saving config option {value} for {column}: {e}")
        # Don't acknowledge, to show something went wrong

@slack_app.action("button-web-ignore")
def ignored_button(ack):
    ack()

@slack_app.action("conversation-send-select")
def conversation_send_select(ack, body, client):
    #print(body)
    #print(body["actions"][0]["selected_conversation"])
    button_sql_bits(body["user"]["id"], body["actions"][0]["selected_conversation"], "channel_id", ack)

@slack_app.action("steps-selection")
def steps_selection(ack, body, client):
    button_sql_bits(body["user"]["id"], body["actions"][0]["selected_option"]["text"]["text"], "minimum_steps", ack)

@slack_app.action("timepicker-send-stats")
def timepicker_send_stats(ack, body, client):
    #print(body)
    #print(body["actions"][0])
    selected_time_raw = body["actions"][0]["selected_time"]
    timezone_offset = int(slack_app.client.users_info(user=body["user"]["id"])["user"]["tz_offset"])
    #print(slack_app.client.users_info(user="U07L45W79E1")["user"]["tz_offset"])
    utc_time_slackfriendly = tz_offset_slack_time(selected_time_raw, timezone_offset)
    print(utc_time_slackfriendly)
    button_sql_bits(body["user"]["id"], utc_time_slackfriendly, "utc_daily_stats_time", ack)

def tz_offset_slack_time(slack_time, tz_offset): # (timezone offset in seconds)
    selected_timedelta = datetime.timedelta(hours=int(slack_time[0:2]), minutes=int(slack_time.replace(":", "")[2:4]))
    utc_timedelta = selected_timedelta - datetime.timedelta(seconds=tz_offset)
    #print(utc_timedelta)
    if utc_timedelta.seconds < 0:
        utc_time_slackfriendly = f"{str(round(((24*60*60 + utc_timedelta.seconds) / 60) // 60)).zfill(2)}:{str(round(((24*60*60 + utc_timedelta.seconds) / 60) % 60)).zfill(2)}"
    else:
        utc_time_slackfriendly = f"{str(round((utc_timedelta.seconds / 60) // 60)).zfill(2)}:{str(round((utc_timedelta.seconds / 60) % 60)).zfill(2)}"

    return utc_time_slackfriendly

@slack_app.action("checkboxes-action")
def checkboxes_action(ack, body, client):
    #print(body["actions"][0])

    uid = body["user"]["id"]
    selected_options = body["actions"][0]["selected_options"]

    if send_daily_stats_checkbox in selected_options:
        button_sql_bits(uid, 1, "send_daily_stats", ack)
    else:
        button_sql_bits(uid, 0, "send_daily_stats", ack)

    if do_ping_in_daily_stats_checkbox in selected_options:
        button_sql_bits(uid, 1, "do_ping_in_daily_stats", ack)
    else:
        button_sql_bits(uid, 0, "do_ping_in_daily_stats", ack)

    if send_sleep_checkbox in selected_options:
        button_sql_bits(uid, 1, "send_sleep", ack)
    else:
        button_sql_bits(uid, 0, "send_sleep", ack)


def do_daily_stats():
    timenow = datetime.datetime.now(datetime.timezone.utc)
    time_slack_friendly = f"{str(round(timenow.hour)).zfill(2)}:{str(round(timenow.minute)).zfill(2)}"
    #print(time_slack_friendly)
    with sqlite3.connect("main.db") as conn:
        with closing(conn.cursor()) as cur:
            cur.execute("""
            SELECT slack_user_id, slack_display_name, fitbit_access_token, fitbit_refresh_token, channel_id, minimum_steps, do_ping_in_daily_stats, fitbit_token_expires_at FROM users
            WHERE utc_daily_stats_time = ? AND send_daily_stats = 1
            """, (time_slack_friendly,))
            retrieveds = cur.fetchall()
            if retrieveds:
                for record in retrieveds:
                    slack_user_id, slack_display_name, fitbit_access_token, fitbit_refresh_token, channel_id, minimum_steps, do_ping_in_daily_stats, fitbit_token_expires_at = record

                    def refresh_cb(token):
                        print(f"refreshing access tokens")
                        with sqlite3.connect("main.db") as conn:
                            with closing(conn.cursor()) as cur:
                                cur.execute("""UPDATE users
                                SET fitbit_access_token = ?,
                                    fitbit_refresh_token = ?,
                                    fitbit_token_expires_at = ?
                                WHERE slack_user_id = ?
                                """, (token["access_token"], token["refresh_token"], token["expires_at"], slack_user_id))

                    temp_fitbit_client = fitbit.Fitbit(KEYS["fitbit_client_id"], KEYS["fitbit_client_secret"], fitbit_access_token, fitbit_refresh_token, fitbit_token_expires_at, refresh_cb)
                    activities = temp_fitbit_client.activities()  # this exists i promise

                    if int(activities["summary"]["steps"]) > minimum_steps:
                        slack_app.client.chat_postMessage(channel=channel_id,
                                                          text=f"""*way to go!*
                                                      
{f"<@{slack_user_id}>" if do_ping_in_daily_stats else slack_display_name} has done {activities["summary"]["steps"]} steps today!
and they spent {activities["summary"]["lightlyActiveMinutes"] + activities["summary"]["fairlyActiveMinutes"] + activities["summary"]["veryActiveMinutes"]} minutes active!!
and they used {round((activities["summary"]["activityCalories"] / activities["summary"]["caloriesOut"]) * 100, 1)}% of burned calories on activity
                    """)
                    # print(activities)
                    # print(f"""
                    # Steps today: {activities["summary"]["steps"]} (lazy)
                    # Active time: {activities["summary"]["lightlyActiveMinutes"] + activities["summary"]["fairlyActiveMinutes"] + activities["summary"]["veryActiveMinutes"]} minutes
                    # {round((activities["summary"]["activityCalories"] / activities["summary"]["caloriesOut"]) * 100, 1)}% of burned calories spent on activity
                    # """)

def do_sleep_stats():
    with sqlite3.connect("main.db") as conn:
        with closing(conn.cursor()) as cur:
            cur.execute("""SELECT slack_user_id, slack_display_name, fitbit_access_token, fitbit_refresh_token, channel_id, fitbit_token_expires_at, last_sleep_count, last_sleep_endtime FROM users
                WHERE send_sleep = 1
            """)
            retrieveds = cur.fetchall()

            if retrieveds:
                for retrieved in retrieveds:
                    slack_user_id, slack_display_name, fitbit_access_token, fitbit_refresh_token, channel_id, fitbit_token_expires_at, last_sleep_count, last_sleep_endtime = retrieved
                    def refresh_cb(token):
                        print(f"refreshing access tokens")
                        with sqlite3.connect("main.db") as conn:
                            with closing(conn.cursor()) as cur:
                                cur.execute("""UPDATE users
                                SET fitbit_access_token = ?,
                                    fitbit_refresh_token = ?,
                                    fitbit_token_expires_at = ?
                                WHERE slack_user_id = ?
                                """, (token["access_token"], token["refresh_token"], token["expires_at"], slack_user_id))



                    temp_fitbit_client = fitbit.Fitbit(KEYS["fitbit_client_id"], KEYS["fitbit_client_secret"], fitbit_access_token, fitbit_refresh_token, fitbit_token_expires_at, refresh_cb)
                    sleep_data = temp_fitbit_client.get_sleep(datetime.date.today())
                    timezone_offset = int(slack_app.client.users_info(user=slack_user_id)["user"]["tz_offset"])

                    """
                    if len(sleep_data["sleep"]) != last_sleep_count:
                        print(f"sleep number changed, was {last_sleep_count}, is now {sleep_data["sleep"]}")
                        cur.execute(\"\"\"UPDATE users
                        SET last_sleep_count = ?
                        WHERE slack_user_id = ?
                        \"\"\", (len(sleep_data["sleep"]), slack_user_id))

                    print(f"{datetime.datetime.now().time()}: {sleep_data}")
                    if len(sleep_data["sleep"]) > last_sleep_count:
                        print("fell asleep??\n\n\n\n\n\n\n")
                        slack_app.client.chat_postMessage(channel=channel_id,
                                                          text=f"uhhhhhh i think {slack_display_name} just fell asleep, shhhh")
                    """
                    if sleep_data["sleep"]:
                        if sleep_data["sleep"][-1]["endTime"] != last_sleep_endtime:
                            #print("endtime: " + sleep_data["sleep"][-1]["endTime"])
                            #print("endtime is different to the last one!")
                            #print(datetime.datetime.fromisoformat(sleep_data["sleep"][-1]["endTime"]))
                            endtime = datetime.datetime.fromisoformat(sleep_data["sleep"][-1]["endTime"])
                            if (datetime.datetime.now() - (endtime - datetime.timedelta(seconds=timezone_offset)) > datetime.timedelta(minutes=15) and datetime.datetime.now() - (endtime - datetime.timedelta(seconds=timezone_offset)) < datetime.timedelta(minutes=50)):
                                print("Woke up!!")
                                slack_app.client.chat_postMessage(channel=channel_id,
                                                                  text=f"gooooood morning! {slack_display_name} woke up about 15 minutes ago!\n"
                                                                       f"they slept for {round(sleep_data["sleep"][-1]["minutesAsleep"]//60)}h {round(sleep_data["sleep"][-1]["minutesAsleep"]%60)}m")

                                cur.execute("""UPDATE users
                                               SET last_sleep_endtime = ?
                                               WHERE slack_user_id = ?""",
                                            (sleep_data["sleep"][-1]["endTime"], slack_user_id))


def daily_stats_runner(counter):
    if counter <= 0:
        counter = 5
    counter -= 1
    #print(counter)
    threading.Timer(60, daily_stats_runner, args=(counter,)).start()
    threading.Thread(target=do_daily_stats).start()
    if counter == 4:
        threading.Thread(target=do_sleep_stats).start()




sql_setup()
threading.Thread(target=SocketModeHandler(slack_app, KEYS["slack_app_token"]).start).start()
threading.Thread(target=flask_app.run, kwargs={"port": KEYS["port"]}).start()
threading.Timer(60, daily_stats_runner, args=(5,)).start()

print(get_auth_url("U07DHR6J57U", "Gigi Cat"))

scheduler.start() # don't remove this if you do everything breaks because python is weird