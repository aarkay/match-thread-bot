match-thread-bot
================

Match thread creation bot for football/soccer matches on reddit. Developed using [Python 2.7](https://www.python.org/download/releases/2.7.7/) and requires [PRAW](https://praw.readthedocs.org/en/v2.1.16/) - you'll need to install these first if you want to run your own version of the code. Uses goal.com to grab most of its info. My version of this bot, [MatchThreadder](http://www.reddit.com/user/MatchThreadder), currently runs on [/r/soccer](http://www.reddit.com/r/soccer).


login.txt
-----

To run this bot, you must have a file called 'login.txt' in the same directory. This file should contain exactly four lines: the bot's username, the bot's password, the subreddit that the bot will be used in, and the bot's user agent. For example, if I wanted to use this code to allow a bot called 'TestThreadBot' with the password 'ThisIsATestPassword' to the subreddit 'SubForTesting', the login.txt file would look like this:

    TestThreadBot
    ThisIsATestPassword
    SubForTesting
    TestThreadBot v0.1 by /u/iliketotestthings

    
The fourth line, the bot's user agent, should be provided as per [reddit's API rules](https://github.com/reddit/reddit/wiki/API).

mtb.py
-----

In this file is the code used to run MatchThreadder - as long as you change the login.txt file appropriately, you should be able to run this file in its current form to have your own subreddit-specific version of the bot, although I haven't tested that at all. The bot checks for new messages every 60 seconds, and if any messages are titled 'Match Thread' or 'Match Info' it will attempt to find the appropriate info about that match.

If/when the bot runs into any HTTP errors (reddit is down, can't access goal.com, etc) it will sleep for 2 minutes and try again.

If a message is titled 'Match Thread', the bot will attempt to find info about the match and then post a match thread to the specified subreddit. If a message is titled 'Match Info', the bot will attempt to find info about the match and then reply to the user with a template for the match thread so the user can post and update the thread themselves.
