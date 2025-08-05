from contextlib import closing

import fitbit
from fitbit import FitbitOauth2Client
import json
from flask import Flask, request
import threading
import sqlite3
import datetime

with open("keys.json", "r") as the_file:
    KEYS = json.load(the_file)

flask_app = Flask(__name__)

fitbit_auth_client = FitbitOauth2Client(KEYS["fitbit_client_id"], KEYS["fitbit_client_secret"])
print(f"auth url: {fitbit_auth_client.authorize_token_url(scope=["activity", "sleep", "settings"], state=fitbit_auth_client.session.new_state())}")


def get_auth_url(slack_user_id, slack_display_name=""):
    state = fitbit_auth_client.session.new_state()
    url = fitbit_auth_client.authorize_token_url(scope=["activity", "sleep", "settings"], state=state)

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
        utc_daily_stats_time INT
    )
    """
    with sqlite3.connect("main.db") as conn:
        with closing(conn.cursor()) as cur:
            cur.execute(users_statement)
            conn.commit()

sql_setup()
threading.Thread(target=flask_app.run, kwargs={"port": 3100}).start()
print(get_auth_url("U07DHR6J57U", "Gigi Cat"))