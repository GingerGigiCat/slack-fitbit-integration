# Slack Fitbit Integration

This is a slack bot to give you daily stats in a channel or a DM of your steps, minutes active and percentage of calories burned for activity. It can also send a message when you wake up, detailing how long you slept for.

The bot is easily configurable via the bot's slack home view (pictured below), and it's easy to login with your fitbit account. (Note: when logging in for the first time, you'll have to click off the home tab and then click back onto it for it to refresh)

<img width="1042" height="612" alt="image" src="https://github.com/user-attachments/assets/0db099a8-9683-47ba-877e-2fcd14b48c81" />


Below is an image of the bot in action!

<img width="658" height="263" alt="image" src="https://github.com/user-attachments/assets/42e03119-a571-4137-b270-53bd39cce32c" />


If you would like to have more stats, open an issue on the github and I'll see what I can do!


## Backend

This bot is written in python, for python-3.12 specifically. It uses the [python-fitbit](https://github.com/orcasgit/python-fitbit) library, as well as slack bolt, flask for the fitbit login callback, and sqlite3 to store a database of users in an SQL database. This bot only store users' config options and the relevant access tokens for fitbit, no health data is stored except for the timestamp of the last sleep end.

This bot is added to the hack club slack workspace and can be found at https://hackclub.slack.com/archives/D098A50R7HD, however if you want to run it yourself for a different workspace here's what you will need:

- Basic knowledge of a terminal, and of networking.
- An installation of at least python 3.12. I haven't tested for the minimum version, if you use a lower version you may have trouble or you may be fine.
- In a terminal, run `git clone https://github.com/GingerGigiCat/slack-fitbit-integration/` to download this repo to a folder on your computer
- Then run `cd slack-fitbit-integration` to change to the folder you just downloaded from github
- Next, run `pip install -r requirements.txt` to install the required packages
  - Then, create a file called `keys.json` with the contents: 
    ```
    {
      "fitbit_client_id": "",
      "fitbit_client_secret": "",
      "slack_signing_secret": "",
      "slack_app_token": "",
      "slack_bot_token": "",
      "port": 3100
    }
    ```

- Then create an app on https://api.slack.com/
- From the Basic Information page on the created app, copy the Signing Secret and put it inbetween the quotes after `"slack_signing_secret": `
- Scroll down and create an app-level token with the scope connections:write (the name of the token doesn't matter) and copy the token it gives you into the `"slack_app_token": `
- Then go to Socket Mode and enable socket mode.
- Then go to OAuth and permissions and give the bot the following OAuth scopes: `chat:write`, `users.profile:read`, `users:read`
- Install the bot to your workspace and get the bot user token it gives you, then put it as the `"slack_bot_token": `
- Go to Event Subscriptions and enable events, then expand Subscribe to bot events and add bot user event of `app_home_opened`
- Ok you should be done with slack! Now onto fitbit.

- Go to https://dev.fitbit.com/apps/new and log in if prompted. Register and application and put in the info you want. The OAuth 2.0 Application Type should be Server, and it's Read Only. The redirect URL should be a https url of where the bot is being hosted with /fitbit/oauth on the end, such as `https://example.com/fitbit/oauth`. I'd suggest using ngrok for this unless you have a better way, google or your favourite LLM should be able to help you, the default port for this is 3100
- You'll need to get the OAuth 2.0 client ID and the Client Secret, and put them in the `keys.json` file where appropriate (i'm sure you can figure out where by now)
- You should be good to go! Run the bot in python by running `python3 main.py` in a terminal in the folder you git cloned to, and it should just run!
- Find your bot on slack and go to its home tab to login with fitbit and configure