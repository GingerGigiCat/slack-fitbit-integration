import fitbit
from fitbit import FitbitOauth2Client
import json

with open("keys.json", "r") as the_file:
    KEYS = json.load(the_file)

fitbit_auth_client = FitbitOauth2Client(KEYS["fitbit_client_id"], KEYS["fitbit_client_secret"])
print(f"auth url: {fitbit_auth_client.authorize_token_url()}")
fitbit_token = fitbit_auth_client.fetch_access_token(input("enter auth code: "))


fitbit_client = fitbit.Fitbit(KEYS["fitbit_client_id"], KEYS["fitbit_client_secret"], access_token=fitbit_token["access_token"], refresh_token=fitbit_token["refresh_token"])
activities = fitbit_client.activities()
print(activities)
print(f"""
Steps today: {activities["summary"]["steps"]} (lazy)
Active time: {activities["summary"]["lightlyActiveMinutes"] + activities["summary"]["fairlyActiveMinutes"] + activities["summary"]["veryActiveMinutes"]} minutes
{round((activities["summary"]["activityCalories"] / activities["summary"]["caloriesOut"]) * 100, 1)}% of burned calories spent on activity
""")