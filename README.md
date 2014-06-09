match-thread-bot
================

Match thread creation bot for football (soccer) matches on reddit. Developed using [Python 2.7](https://www.python.org/download/releases/2.7.7/) and requires [PRAW](https://praw.readthedocs.org/en/v2.1.16/). Uses goal.com to grab most of its info. My version of this bot, [MatchThreadder](http://www.reddit.com/user/MatchThreadder), currently runs on [/r/soccer](http://www.reddit.com/r/soccer).


login.txt
-----

To run this bot, you must have a file called 'login.txt' in the same directory. This file should contain exactly four lines: the bot's username, the bot's password, the bot's user agent, and the subreddit that the bot will be used in. For example, if I wanted to use this code to allow a bot called 'TestThreadBot' with the password 'ThisIsATestPassword' to the subreddit 'SubForTesting', the login.txt file would look like this:

    TestThreadBot
    ThisIsATestPassword
    TestThreadBot v0.1 by /u/iliketotestthings
    SubForTesting
    
The third line, the bot's user agent, should be provided as per [reddit's API guidelines](https://github.com/reddit/reddit/wiki/API).
