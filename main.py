import fitbit
from fitbit import FitbitOauth2Client
import json
from flask import Flask, request
import threading
import sqlite3

with open("keys.json", "r") as the_file:
    KEYS = json.load(the_file)

flask_app = Flask(__name__)

fitbit_auth_client = FitbitOauth2Client(KEYS["fitbit_client_id"], KEYS["fitbit_client_secret"])
print(f"auth url: {fitbit_auth_client.authorize_token_url(scope=["activity", "sleep", "settings"], state=fitbit_auth_client.session.new_state())}")


def get_auth_url(slack_user_id, slack_display_name=""):
    state = fitbit_auth_client.session.new_state()
    fitbit_auth_client.authorize_token_url(scope=["activity", "sleep", "settings"], state=state)



@flask_app.route("/fitbit/oauth")
def fitbit_oauth_callback():
    if "code" in request.args:
        fitbit_token = fitbit_auth_client.fetch_access_token(request.args["code"])

        fitbit_client = fitbit.Fitbit(KEYS["fitbit_client_id"], KEYS["fitbit_client_secret"], access_token=fitbit_token["access_token"], refresh_token=fitbit_token["refresh_token"])
        activities = fitbit_client.activities() # this exists i promise
        print(activities)
        print(f"""
        Steps today: {activities["summary"]["steps"]} (lazy)
        Active time: {activities["summary"]["lightlyActiveMinutes"] + activities["summary"]["fairlyActiveMinutes"] + activities["summary"]["veryActiveMinutes"]} minutes
        {round((activities["summary"]["activityCalories"] / activities["summary"]["caloriesOut"]) * 100, 1)}% of burned calories spent on activity
        """)

        with open("oauth_webpage.html", "r") as the_html:
            return the_html.read().replace(
                "{main_text}", "Yay fitbit is now authenticated!").replace(
                "{sub_text}", "(you can close this tab now)").replace(
                "{text_colour}", "rgb(208, 238, 239)")
        # normal text colour: rgb(208, 238, 239)
        # error text colour: rgb(255, 122, 122)

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
        with conn.cursor() as cur:
            cur.execute(users_statement)
            conn.commit()
sql_setup()
threading.Thread(target=flask_app.run, kwargs={"port": 3100}).start()