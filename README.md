# Slack Fitbit Integration

This is a slack bot to give you daily stats in a channel or a DM of your steps, minutes active and percentage of calories burned for activity. It can also send a message when you wake up, detailing how long you slept for.

The bot is easily configurable via the bot's slack home view (pictured below), and it's easy to login with your fitbit account.

<img width="1042" height="612" alt="image" src="https://github.com/user-attachments/assets/0db099a8-9683-47ba-877e-2fcd14b48c81" />


Below is an image of the bot in action!

<img width="658" height="263" alt="image" src="https://github.com/user-attachments/assets/42e03119-a571-4137-b270-53bd39cce32c" />


If you would like to have more stats, open an issue on the github and I'll see what I can do!


## Backend

This bot is written in python, for python-3.12 specifically. It uses the [python-fitbit](https://github.com/orcasgit/python-fitbit) library, as well as slack bolt, flask for the fitbit login callback, and sqlite3 to store a database of users in an SQL database. This bot only store users' config options and the relevant access tokens for fitbit, no health data is stored except for the timestamp of the last sleep end.

This bot is added to the hack club slack workspace and can be found at https://hackclub.slack.com/archives/D098A50R7HD, however if you want to run it yourself for a different workspace here's what you will need:

- Basic knowledge of a terminal, and of networking.
- An installation of at least python 3.12. I haven't tested for the minimum version, if you use a lower version you may have trouble or you may be fine.
- 
