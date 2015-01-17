import praw,urllib2,cookielib,re,logging,logging.handlers,datetime
from collections import Counter
from time import sleep

# TO DO: 
# python 3
#  print(" ")
#  urllib2 to urllib
#  cookielib to http.cookiejar
#  s = f.read().decode('utf8') line not needed? python 3 decodes automatically
# fix penalties detection
#  search subsequent line for "won"
# x date logging
# use goal.com to bypass thread request
# switch from urllib2 to requests maybe
# deal with incorrect matching of non-existent game (eg using "City", etc) - ie better way of finding matches (nearest neighbour?)
# more robust handling of errors

# every minute, check mail, create new threads, update all current threads

# browser header (to avoid 405 error with goal.com, streaming sites)
hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
   'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
   'Accept-Encoding': 'none',
   'Accept-Language': 'en-US,en;q=0.8',
   'Connection': 'keep-alive'}

activeThreads = []

# obvious attempts at abuse + mod requests
subblacklist = ['subreddit',
				'all',
				'gaming',
				'pics',
				'funny',
				'videos',
				'adviceanimals',
				'politics',
				'iama',
				'gifs',
				'worldnews',
				'aww',
				'askreddit',
				'cringe',
				'atheism']

# naughty list				
usrblacklist = ['dbawbaby',
				'12F12']

def login():
	try:
		f = open('login.txt')
		admin,username,password,subreddit,user_agent = f.readline().split(':',5)
		r = praw.Reddit(user_agent)
		r.login(username,password)
		f.close()
		return r,subreddit,admin,username
	except:
		print "Login error: please ensure 'login.txt' file exists in its correct form (check readme for more info)"
		sleep(10)

# save activeThreads
def saveData():
	f = open('active_threads.txt', 'w+')
	s = ''
	for data in activeThreads:
		matchID,t1,t2,thread_id,reqr,sub = data
		s += matchID + '####' + t1 + '####' + t2 + '####' + thread_id + '####' + reqr + '####' + sub + '&&&&'
	s = s[0:-4] # take off last &&&&
	f.write(s.encode('utf8'))
	f.close()

# read saved activeThreads data	
def readData():
	f = open('active_threads.txt', 'a+')
	s = f.read().decode('utf8')
	info = s.split('&&&&')
	if info[0] != '':
		for d in info:
			[matchID,t1,t2,thread_id,reqr,sub] = d.split('####')
			matchID = matchID.encode('utf8') # get rid of weird character at start - got to be a better way to do this...
			data = matchID, t1, t2, thread_id, reqr, sub
			activeThreads.append(data)
			logger.info("Active threads: %i - added %s vs %s (/r/%s)", len(activeThreads), t1, t2, sub)
			print "Active threads: " + str(len(activeThreads)) + " - added " + t1 + " vs " + t2 + " (/r/" + sub + ")"
	f.close()

def getBotStatus():
	thread = r.get_submission(submission_id = '22ah8i')
	status = re.findall('bar-10-(.*?)\)',thread.selftext)
	msg = re.findall('\| \*(.*?)\*',thread.selftext)
	return status[0],msg[0]
	
def findGoalSite(team1, team2):
	# search for each word in each team name in goal.com's fixture list, return most frequent result
	t1 = team1.split()
	t2 = team2.split()
	linkList = []
	fixAddress = "http://www.goal.com/en-us/live-scores"
	req = urllib2.Request(fixAddress, headers=hdr)
	fixWebsite = urllib2.urlopen(req)
	fix_html = fixWebsite.read()
	links = re.findall('/en-us/match/(.*?)"', fix_html)
	for link in links:
		for word in t1:
			if link.find(word.lower()) != -1:
				linkList.append(link)
		for word in t2:
			if link.find(word.lower()) != -1:
				linkList.append(link)		
	counts = Counter(linkList)
	if counts.most_common(1) != []:
		mode = counts.most_common(1)[0]
		return mode[0]
	else:
		return 'no match'
		
def getLineUps(matchID):
	# try to find line-ups (404 if line-ups not on goal.com yet)
	try:
		lineAddress = "http://www.goal.com/en-us/match/" + matchID + "/lineups"
		req = urllib2.Request(lineAddress, headers=hdr)
		lineWebsite = urllib2.urlopen(req)
		line_html_enc = lineWebsite.read()
		line_html = line_html_enc.decode("utf8")

		delim = '<ul class="player-list">'
		split = line_html.split(delim) # [0]:nonsense [1]:t1 XI [2]:t2 XI [3]:t1 subs [4]:t2 subs + managers

		managerDelim = '<div class="manager"'
		split[4] = split[4].split(managerDelim)[0] # managers now excluded
		
		team1Start = re.findall('<span class="name".*?>(.*?)<',split[1],re.DOTALL)
		team2Start = re.findall('<span class="name".*?>(.*?)<',split[2],re.DOTALL)	
		team1Sub = re.findall('<span class="name".*?>(.*?)<',split[3],re.DOTALL)
		team2Sub = re.findall('<span class="name".*?>(.*?)<',split[4],re.DOTALL)

		# if no players found, ie TBA
		if team1Start == []:
			team1Start = ["TBA"]
		if team1Sub == []:
			team1Sub = ["TBA"]
		if team2Start == []:
			team2Start = ["TBA"]
		if team2Sub == []:
			team2Sub = ["TBA"]
		return team1Start,team1Sub,team2Start,team2Sub
		
	except urllib2.HTTPError:
		team1Start = ["TBA"]
		team1Sub = ["TBA"]
		team2Start = ["TBA"]
		team2Sub = ["TBA"]
		return team1Start,team1Sub,team2Start,team2Sub

# get current match time/status
def getStatus(matchID):
	lineAddress = "http://www.goal.com/en-us/match/" + matchID
	req = urllib2.Request(lineAddress, headers=hdr)
	lineWebsite = urllib2.urlopen(req)
	line_html = lineWebsite.read()
	status = re.findall('<div class="vs">(.*?)<',line_html,re.DOTALL)[0]
	return status			
	
# get venue, ref, lineups, etc from goal.com	
def getGDCinfo(matchID):
	lineAddress = "http://www.goal.com/en-us/match/" + matchID
	req = urllib2.Request(lineAddress, headers=hdr)
	lineWebsite = urllib2.urlopen(req)
	line_html_enc = lineWebsite.read()
	line_html = line_html_enc.decode("utf8")

	# get "fixed" versions of team names (ie team names from goal.com, not team names from match thread request)
	team1fix = re.findall('<div class="home" .*?<h2>(.*?)<', line_html, re.DOTALL)[0]
	team2fix = re.findall('<div class="away" .*?<h2>(.*?)<', line_html, re.DOTALL)[0]
	
	if team1fix[-1]==' ':
		team1fix = team1fix[0:-1]
	if team2fix[-1]==' ':
		team2fix = team2fix[0:-1]	
	
	status = getStatus(matchID)
	ko = re.findall('<div class="match-header .*?</li>.*? (.*?)</li>', line_html, re.DOTALL)[0]
	
	venue = re.findall('<div class="match-header .*?</li>.*?</li>.*? (.*?)</li>', line_html, re.DOTALL)
	if venue != []:
		venue = venue[0]
	else:
		venue = '?'
		
	ref = re.findall('Referee: (.*?)</li>', line_html, re.DOTALL)
	if ref != []:
		ref = ref[0]	
	else:
		ref = '?'
		
	team1Start,team1Sub,team2Start,team2Sub = getLineUps(matchID)
		
	return (team1fix,team2fix,team1Start,team1Sub,team2Start,team2Sub,venue,ref,ko,status)
	
def writeLineUps(body,t1,t2,team1Start,team1Sub,team2Start,team2Sub):
	body += '**LINE-UPS**\n\n**' + t1 + '**\n\n'
	body += ", ".join(x for x in team1Start) + ".\n\n"
	body += '**Subs:** '
	body += ", ".join(x for x in team1Sub) + ".\n\n^____________________________\n\n"
	
	body += '**' + t2 + '**\n\n'
	body += ", ".join(x for x in team2Start) + ".\n\n"
	body += '**Subs:** '
	body += ", ".join(x for x in team2Sub) + "."
	return body
	
def findScoreSide(time,left,right):
	leftTimes = [int(x) for x in re.findall(r'\b\d+\b', left)]
	rightTimes = [int(x) for x in re.findall(r'\b\d+\b', right)]
	if time in leftTimes and time in rightTimes:
		return 'none'
	if time in leftTimes:
		return 'left'
	if time in rightTimes:
		return 'right'
	return 'none'

def grabEvents(matchID,left,right):
	lineAddress = "http://www.goal.com/en-us/match/" + matchID + "/live-commentary"
	req = urllib2.Request(lineAddress, headers=hdr)
	lineWebsite = urllib2.urlopen(req)
	line_html_enc = lineWebsite.read()
	line_html = line_html_enc.decode("utf8")
	
	body = ""
	split = line_html.split('<ul class="commentaries') # [0]:nonsense [1]:events
	events = split[1].split('<li data-event-type="')
	events = events[1:]
	events = events[::-1]
	
	L = 0
	R = 0
	updatescores = True
	
	# goal.com's full commentary tagged as "action" - ignore these
	# will only report goals (+ penalties, own goals), yellows, reds, subs - not sure what else goal.com reports
	supportedEvents = ['goal','penalty-goal','own-goal','missed-penalty','yellow-card','red-card','yellow-red','substitution']
	for text in events:
		tag = re.findall('(.*?)"',text,re.DOTALL)[0]
		if tag.lower() in supportedEvents:
			time = re.findall('<div class="time">\n?(.*?)<',text,re.DOTALL)[0]
			if time[-1] == ' ':
				time = time[:-1]
			info = "**" + time + "** "
			event = re.findall('<div class="text">\n?(.*?)<',text,re.DOTALL)[0]
			if event[-1] == ' ':
				event = event[:-1]
			if tag.lower() == 'goal' or tag.lower() == 'penalty-goal' or tag.lower() == 'own-goal':
				if tag.lower() == 'goal':
					event = event[:4] + ' ' + event[4:]
				elif tag.lower() == 'penalty-goal':
					event = event[:12] + ' ' + event[12:]
				else:
					event = event[:8] + ' ' + event[8:]
				info += '[](#icon-ball) **' + event + '**'
				if findScoreSide(int(time.split("'")[0]),left,right) == 'left':
					L += 1
				elif findScoreSide(int(time.split("'")[0]),left,right) == 'right':
					R += 1
				else:
					updatescores = False
				if updatescores:
					info += ' **' + str(L) + '-' + str(R) + '**'
			if tag.lower() == 'missed-penalty':
				event = event[:14] + ' ' + event[14:]
				info += '[](#icon-red-ball) **' + event + '**'
			if tag.lower() == 'yellow-card':
				event = event[:11] + ' ' + event[11:]
				info += '[](#icon-yellow) ' + event
			if tag.lower() == 'red-card' or tag.lower() == 'yellow-red':
				if tag.lower() == 'red-card':
					event = event[:8] + ' ' + event[8:]
				else:
					event = event[:10] + ' ' + event[10:]
				info += '[](#icon-red) ' + event
			if tag.lower() == 'substitution':
				info += '[](#icon-sub) Substitution: [](#icon-down)' + re.findall('"sub-out">(.*?)<',text,re.DOTALL)[0]
				info += ' [](#icon-up)' + re.findall('"sub-in">(.*?)<',text,re.DOTALL)[0]
			body += info + '\n\n'
		
	return body
	
def findWiziwigID(team1,team2):
	t1 = team1.split()
	t2 = team2.split()
	linkList = []
	fixAddress = "http://www.wiziwig.sx/competition.php?part=sports&discipline=football"
	req = urllib2.Request(fixAddress, headers=hdr)
	try:
		fixWebsite = urllib2.urlopen(req)
	except urllib2.HTTPError, e:
		logger.error("Couldn't access wiziwig streams for %s vs %s", team1,team2)
		return 'no match'
	fix_html = fixWebsite.read()
	
	for word in t1:
		links = re.findall('<td class="home">.*?' + word + '.*?broadcast" href="(.*?)"', fix_html, re.DOTALL)
		for link in links:
			linkList.append(link)
	for word in t2:
		links = re.findall('<td class="away">.*?' + word + '.*?broadcast" href="(.*?)"', fix_html, re.DOTALL)
		for link in links:
			linkList.append(link)

	counts = Counter(linkList)
	if counts.most_common(1) != []:
		mode = counts.most_common(1)[0]
		return mode[0]
	else:
		logger.info("Couldn't find wiziwig streams for %s vs %s", team1,team2)
		return 'no match'
		
def findFirstrowID(team1,team2):
	t1 = team1.split()
	t2 = team2.split()
	linkList = []
	fixAddress = "http://ifirstrowus.eu/"
	req = urllib2.Request(fixAddress, headers=hdr)
	try:
		fixWebsite = urllib2.urlopen(req)
	except urllib2.HTTPError, e:
		logger.error("Couldn't access firstrow streams for %s vs %s", team1,team2)
		return 'no match'
	fix_html = fixWebsite.read()
	
	for word in t1:
		links = re.findall('<a> <img class="chimg" alt=".*?' + word + ".*?Link 1'href='(.*?)'",fix_html,re.DOTALL)
		for link in links:	
			linkList.append(link)
	for word in t2:
		links = re.findall('<a> <img class="chimg" alt=".*?' + word + ".*?Link 1'href='(.*?)'",fix_html,re.DOTALL)
		for link in links:
			linkList.append(link)

	counts = Counter(linkList)
	if counts.most_common(1) != []:
		mode = counts.most_common(1)[0]
		return mode[0]
	else:
		logger.info("Couldn't find firstrow streams for %s vs %s", team1,team2)
		return 'no match'
		
def findLiveFootballID(team1,team2):
	t1 = team1.split()
	t2 = team2.split()
	linkList = []
	fixAddress = "http://livefootballvideo.com/"
	req = urllib2.Request(fixAddress, headers=hdr)
	try:
		fixWebsite = urllib2.urlopen(req)
	except urllib2.HTTPError, e:
		logger.error("Couldn't access LiveFootballVideo streams for %s vs %s", team1,team2)
		return 'no match'
	fix_html = fixWebsite.read()
	
	for word in t1:
		links = re.findall('<span>.*?' + word + '.*?href="(.*?)"', fix_html, re.DOTALL)
		for link in links:	
			linkList.append(link)
	for word in t2:
		links = re.findall('<span>.*?' + word + '.*?href="(.*?)"', fix_html, re.DOTALL)
		for link in links:
			linkList.append(link)

	counts = Counter(linkList)
	if counts.most_common(1) != []:
		mode = counts.most_common(1)[0]
		return mode[0]
	else:
		logger.info("Couldn't find LiveFootballVideo streams for %s vs %s", team1,team2)
		return 'no match'
	
def findVideoStreams(team1,team2):
	text = "**Got a stream? Post it here!**\n\n"
	
	wiziID = findWiziwigID(team1,team2)
	firstrowID = findFirstrowID(team1,team2)
	liveFootballID = findLiveFootballID(team1,team2)
	
	if wiziID != 'no match':
		text += '[wiziwig](http://www.wiziwig.sx/' + wiziID + ')\n\n'
	if firstrowID != 'no match':
		text += '[FirstRow](http://gofirstrowus.eu' + firstrowID + ')\n\n'
	if liveFootballID != 'no match':
		text += '[LiveFootballVideo](' + liveFootballID + ')\n\n'

	text += "^_____________________________________________________________________\n\n"
	text += "[^[Request ^a ^match ^thread]](http://www.reddit.com/message/compose/?to=MatchThreadder&subject=Match%20Thread&message=Team%20vs%20Team) ^| [^[Request ^a ^thread ^template]](http://www.reddit.com/message/compose/?to=MatchThreadder&subject=Match%20Info&message=Team%20vs%20Team) ^| [^[Current ^status ^/ ^bot ^info]](http://www.reddit.com/r/soccer/comments/22ah8i/introducing_matchthreadder_a_bot_to_set_up_match/)"
	
	return text

def getTimes(ko):
	hour = ko[0:ko.index(':')]
	minute = ko[ko.index(':')+1:ko.index(':')+3]
	ampm = ko[ko.index(' ')+1:]
	hour_i = int(hour)
	min_i = int(minute)
	
	if (ampm == 'PM') and (hour_i != 12):
		hour_i += 12		
	if (ampm == 'AM') and (hour_i == 12):
		hour_i = 0	
	
	now = datetime.datetime.now()
	return (hour_i,min_i,now)
	
# attempt submission to subreddit
def submitThread(sub,title):
	try:
		thread = r.submit(sub,title,text='Updates soon')
		return True,thread
	except praw.errors.APIException:
		print "Submission error, check log file"
		logger.exception("[SUBMIT ERROR:]")
		return False,''
	
# create a new thread using provided teams	
def createNewThread(team1,team2,reqr,sub):	
	site = findGoalSite(team1,team2)
	if site != 'no match':
		t1, t2, team1Start, team1Sub, team2Start, team2Sub, venue, ref, ko, status = getGDCinfo(site)
		
		# don't post to a subreddit if it's blacklisted
		if sub in subblacklist:
			print "Denied post request to " + sub
			logger.info("Denied post request to %s", sub)
			return 6,''
		
		# don't post if user is blacklisted
		if reqr in usrblacklist:
			print "Denied post request from " + reqr + " - blacklisted"
			logger.info("Denied post request from %s - blacklisted", reqr)
			return 8,''
		
		# don't create a thread if the bot already made it or if user already has an active thread
		for d in activeThreads:
			matchID_at,t1_at,t2_at,id_at,reqr_at,sub_at = d
			if t1 == t1_at and sub == sub_at:
				print "Denied " + t1 + " vs " + t2 + " request - thread already exists"
				logger.info("Denied %s vs %s request - thread already exists", t1, t2)
				return 4,id_at
			if reqr == reqr_at:
				print "Denied post request from " + reqr + " - has an active thread request"
				logger.info("Denied post request from %s - has an active thread request", reqr)
				return 7,''
		
		# don't create a thread if the match is done (probably found the wrong match)
		if status == 'FT' or status == 'PEN' or status == 'AET':
			print "Denied " + t1 + " vs " + t2 + " request - match appears to be finished"
			logger.info("Denied %s vs %s request - match appears to be finished", t1, t2)
			return 3,''
		
		# don't create a thread if the match hasn't started yet
		hour_i, min_i, now = getTimes(ko)
		if now.hour < hour_i:
			print "Denied " + t1 + " vs " + t2 + " request - match yet to start"
			logger.info("Denied %s vs %s request - match yet to start", t1, t2)
			return 2,''
		if (now.hour == hour_i) and (now.minute < min_i):
			print "Denied " + t1 + " vs " + t2 + " request - match yet to start"
			logger.info("Denied %s vs %s request - match yet to start", t1, t2)
			return 2,''
		
		vidcomment = findVideoStreams(team1,team2)
		title = 'Match Thread: ' + t1 + ' vs ' + t2
		result,thread = submitThread(sub,title)
		
		# if subreddit was invalid, notify
		if result == False:
			return 5,''
		vidlink = thread.add_comment(vidcomment)
		
		short = thread.short_link
		id = short[15:].encode("utf8")
		redditstream = 'http://www.reddit-stream.com/comments/' + id 
		
		if status == 'v':
			status = "0'"
		
		body = '**' + status + ': ' + t1 + ' 0-0 ' + t2 + '**\n\n--------\n\n' 
		body += '**Venue:** ' + venue + '\n\n' + '**Referee:** ' + ref + '\n\n--------\n\n'
		body += '[](#icon-stream-big) **STREAMS**\n\n'
		body += '[Video streams](' + vidlink.permalink + ')\n\n'
		body += '[Reddit comments stream](' + redditstream + ')\n\n---------\n\n'
		body += '[](#icon-notes-big) ' 
		body = writeLineUps(body,t1,t2,team1Start,team1Sub,team2Start,team2Sub)
		
		body += '\n\n------------\n\n[](#icon-net-big) **MATCH EVENTS** | *via [goal.com](http://www.goal.com/en-us/match/' + site + '/live-commentary)*\n\n'
		
		botstat,statmsg = getBotStatus()
		if botstat != 'green':
			body += '*' + statmsg + '*\n\n'
		
		thread.edit(body)
		sleep(30)
		data = site, t1, t2, id, reqr, sub
		activeThreads.append(data)
		saveData()
		logger.info("Active threads: %i - added %s vs %s (/r/%s)", len(activeThreads), t1, t2, sub)
		print "Active threads: " + str(len(activeThreads)) + " - added " + t1 + " vs " + t2 + " (/r/" + sub + ")"
		return 0,id
	else:
		print "Could not find match info for " + t1 + " vs " + t2
		logger.info("Could not find match info for %s vs %s", t1, t2)
		return 1,''

# if the requester just wants a template		
def createMatchInfo(team1,team2):
	site = findGoalSite(team1,team2)
	if site != 'no match':
		t1, t2, team1Start, team1Sub, team2Start, team2Sub, venue, ref, ko, status = getGDCinfo(site)
		
		body = '**' + t1 + ' 0-0 ' + t2 + '**\n\n--------\n\n' 
		body += '**Venue:** ' + venue + '\n\n' + '**Referee:** ' + ref + '\n\n--------\n\n'
		body += '[](#icon-stream-big) **STREAMS**\n\n'
		body += '[Video streams](LINK-TO-STREAMS-HERE)\n\n'
		body += '[Reddit comments stream](LINK-TO-REDDIT-STREAM-HERE)\n\n---------\n\n'
		body += '[](#icon-notes-big) ' 
		body = writeLineUps(body,t1,t2,team1Start,team1Sub,team2Start,team2Sub)
		
		body += '\n\n------------\n\n[](#icon-net-big) **MATCH EVENTS**\n\n'
		
		logger.info("Provided info for %s vs %s", t1, t2)
		print "Provided info for " + t1 + " vs " + t2
		return 0,body
	else:
		return 1,''

# delete a thread (on admin request)
def deleteThread(id):
	try:
		thread = r.get_submission(submission_id = id)
		for data in activeThreads:
			matchID,team1,team2,thread_id,reqr,sub = data
			if thread_id == id:
				thread.delete()
				activeThreads.remove(data)
				logger.info("Active threads: %i - removed %s vs %s (/r/%s)", len(activeThreads), team1, team2, sub)
				print "Active threads: " + str(len(activeThreads)) + " - removed " + team1 + " vs " + team2 + " (/r/" + sub + ")"
				saveData()
				return team1 + ' vs ' + team2
		return ''
	except:
		return ''
		
# remove incorrectly made thread if requester asks within 5 minutes of creation
def removeWrongThread(id,req):
	try:
		thread = r.get_submission(submission_id = id)
		dif = datetime.datetime.utcnow() - datetime.datetime.utcfromtimestamp(thread.created_utc)
		for data in activeThreads:
			matchID,team1,team2,thread_id,reqr,sub = data
			if thread_id == id:
				if reqr != req:
					return 'req'
				if dif.days != 0 or dif.seconds > 300:
					return 'time'
				thread.delete()
				activeThreads.remove(data)
				logger.info("Active threads: %i - removed %s vs %s (/r/%s)", len(activeThreads), team1, team2, sub)
				print "Active threads: " + str(len(activeThreads)) + " - removed " + team1 + " vs " + team2 + " (/r/" + sub + ")"
				saveData()
				return team1 + ' vs ' + team2
		return 'thread'
	except:
		return 'thread'
		
# default attempt to find teams: split input in half, left vs right	
def firstTryTeams(msg):
	t = msg.split()
	spl = len(t)/2
	t1 = t[0:spl]
	t2 = t[spl+1:]
	t1s = ''
	t2s = ''
	for word in t1:
		t1s += word + ' '
	for word in t2:
		t2s += word + ' '
	return [t1s,t2s]

# check for new mail, create new threads if needed
def checkAndCreate():
	sub = subreddit
	delims = [' x ',' - ',' v ',' vs ']
	subdel = ' for '
	for msg in r.get_unread(unset_has_mail=True,update_user=True,limit=None):
		msg.mark_as_read()
		if msg.subject.lower() == 'match thread':
			subreq = msg.body.split(subdel,2)
			if subreq[0] != msg.body:
				sub = subreq[1].split('/')[-1]
				sub = sub.lower()
				sub = sub.strip()
			teams = firstTryTeams(subreq[0])
			for delim in delims:
				attempt = subreq[0].split(delim,2)
				if attempt[0] != subreq[0]:
					teams = attempt
			threadStatus,thread_id = createNewThread(teams[0],teams[1],msg.author.name,sub)
			if threadStatus == 0: # thread created successfully
				msg.reply("[Here](http://www.reddit.com/r/" + sub + "/comments/" + thread_id + ") is a link to the thread you've requested. Thanks for using this bot!\n\n-------------------------\n\n*Did I create a thread for the wrong match? [Click here and press send](http://www.reddit.com/message/compose/?to=" + username + "&subject=delete&message=" + thread_id + ") to delete the thread (note: this will only work within five minutes of the thread's creation). This probably means that I can't find the right match - sorry!*")
				r.send_message(admin,"Match thread request fulfilled","/u/" + reqr + " requested " + t1 + " vs " + t2 + " in /r/" + sub + ". [Click here](http://www.reddit.com/message/compose/?to=" + username + "&subject=delete&message=" + thread_id + ") to delete.")
			if threadStatus == 1: # not found
				msg.reply("Sorry, I couldn't find info for that match. In the future I'll account for more matches around the world.")
			if threadStatus == 2: # before kickoff
				msg.reply("Please wait until kickoff to send me a thread request, just in case someone does end up making one themselves. Thanks!")
			if threadStatus == 3: # after kickoff - probably found the wrong match
				msg.reply("Sorry, I couldn't find info for that match. In the future I'll account for more matches around the world.")
			if threadStatus == 4: # thread already exists
				msg.reply("There is already a [match thread](http://www.reddit.com/r/" + sub + "/comments/" + thread_id + ") for that game. Join the discussion there!")
			if threadStatus == 5: # invalid subreddit
				msg.reply("Sorry, it looks like /r/" + sub + " doesn't exist. Are you sure you entered it correctly?")
			if threadStatus == 6: # sub blacklisted
				msg.reply("Sorry, I cannot post to /r/" + sub + ". Please contact the subreddit mods if you'd like more info.")
			if threadStatus == 7: # thread limit
				msg.reply("Sorry, you can only have one active thread request at a time.")
		
		if msg.subject.lower() == 'match info':
			teams = firstTryTeams(msg.body)
			for delim in delims:
				attempt = msg.body.split(delim,2)
				if attempt[0] != msg.body:
					teams = attempt
			threadStatus,text = createMatchInfo(teams[0],teams[1])
			if threadStatus == 0: # successfully found info
				msg.reply("Below is the information for the match you've requested. There are gaps left for you to add in a link to a comment containing stream links and a link to the reddit-stream for the thread; if you don't want to include these, be sure to remove those lines.\n\nIf you're using [RES](http://redditenhancementsuite.com/), you can use the 'source' button below this message to copy/paste the exact formatting code. If you aren't, you'll have to add the formatting yourself.\n\n----------\n\n" + text)
			if threadStatus == 1: # not found
				msg.reply("Sorry, I couldn't find info for that match. In the future I'll account for more matches around the world.")
		
		if msg.subject.lower() == 'delete':
			if msg.author.name == admin:
				name = deleteThread(msg.body)
				if name != '':
					msg.reply("Deleted " + name)
				else:
					msg.reply("Thread not found")
			else:
				name = removeWrongThread(msg.body,msg.author.name)
				if name == 'thread':
					msg.reply("Thread not found - please double-check thread ID")
				elif name == 'time':
					msg.reply("This thread is more than five minutes old - thread deletion from now is an admin feature only. You can message /u/" + admin + " if you'd still like the thread to be deleted.")
				elif name == 'req':
					msg.reply("Username not recognised. Only the thread requester and bot admin have access to this feature.")
				else:
					msg.reply("Deleted " + name)
				
# update score, scorers
def updateScore(matchID, t1, t2):
	lineAddress = "http://www.goal.com/en-us/match/" + matchID + "/live-commentary"
	req = urllib2.Request(lineAddress, headers=hdr)
	lineWebsite = urllib2.urlopen(req)
	line_html_enc = lineWebsite.read()
	line_html = line_html_enc.decode("utf8")
	leftScore = re.findall('<div class="home-score">(.*?)<',line_html,re.DOTALL)[0]
	rightScore = re.findall('<div class="away-score">(.*?)<',line_html,re.DOTALL)[0]
	aggregate = re.findall('<div class="away-score">.*?<p>(.*?)<',line_html,re.DOTALL)[0]
	status = getStatus(matchID)
	goalUpdating = True
	if status == 'v':
		status = "0'"
		goalUpdating = False
	
	split1 = line_html.split('<div class="home"') # [0]:nonsense [1]:scorers
	split2 = split1[1].split('<div class="away"') # [0]:home scorers [1]:away scorers + nonsense
	split3 = split2[1].split('<div class="module') # [0]:away scorers [1]:nonsense
	
	leftScorers = re.findall('<a href="/en-us/people/.*?>(.*?)<',split2[0],re.DOTALL)
	rightScorers = re.findall('<a href="/en-us/people/.*?>(.*?)<',split3[0],re.DOTALL)
	
	text = '**' + status + ": " +  t1 + ' ' + leftScore + '-' + rightScore + ' ' + t2 + '**\n\n'
	if not goalUpdating:
		text += '*Sorry, it looks like goal.com will be providing little to no match updates for this game.*\n\n'
	
	if aggregate != '':
		text += '**_' + aggregate + '_**\n\n'
	
	left = ''
	if leftScorers != []:
		left += "*" + t1 + " scorers: "
		for scorer in leftScorers:
			scorer.replace('&nbsp;',' ')
			left += scorer + ", "
		left = left[0:-2] + "*"
		
	right = ''
	if rightScorers != []:
		right += "*" + t2 + " scorers: "
		for scorer in rightScorers:
			scorer.replace('&nbsp;',' ')
			right += scorer + ", "
		right = right[0:-2] + "*"
		
	text += left + '\n\n' + right
		
	return text,left,right
		
# update all current threads			
def updateThreads():
	toRemove = []

	for data in activeThreads:
		index = activeThreads.index(data)
		matchID,team1,team2,thread_id,reqr,sub = data
		thread = r.get_submission(submission_id = thread_id)
		body = thread.selftext
		venueIndex = body.index('**Venue:**')
		
		# update lineups (sometimes goal.com changes/updates them)
		team1Start,team1Sub,team2Start,team2Sub = getLineUps(matchID)
		lineupIndex = body.index('**LINE-UPS**')
		bodyTilThen = body[venueIndex:lineupIndex]
		newbody = writeLineUps(bodyTilThen,team1,team2,team1Start,team1Sub,team2Start,team2Sub)
		newbody += '\n\n------------\n\n[](#icon-net-big) **MATCH EVENTS** | *via [goal.com](http://www.goal.com/en-us/match/' + matchID + '/live-commentary)*\n\n'
		
		botstat,statmsg = getBotStatus()
		if botstat != 'green':
			newbody += '*Note: ' + statmsg + '*\n\n'
			
		# update scorelines
		score,left,right = updateScore(matchID,team1,team2)
		newbody = score + '\n\n--------\n\n' + newbody
		
		events = grabEvents(matchID,left,right)
		newbody += '\n\n' + events

		# save data
		if newbody != body:
			logger.info("Making edit to %s vs %s (/r/%s)", team1,team2,sub)
			print "Making edit to " + team1 + " vs " + team2 + " (/r/" + sub + ")"
			thread.edit(newbody)
			saveData()
		newdata = matchID,team1,team2,thread_id,reqr,sub
		activeThreads[index] = newdata
		
		# discard finished matches - search for "FT"
		if getStatus(matchID) == 'FT' or getStatus(matchID) == 'PEN' or getStatus(matchID) == 'AET':
			toRemove.append(newdata)
			
	for getRid in toRemove:
		activeThreads.remove(getRid)
		logger.info("Active threads: %i - removed %s vs %s (/r/%s)", len(activeThreads), getRid[1], getRid[2], getRid[5])
		print "Active threads: " + str(len(activeThreads)) + " - removed " + getRid[1] + " vs " + getRid[2] + " (/r/" + getRid[5] + ")"
		saveData()
		

r,subreddit,admin,username = login()

logger = logging.getLogger('a')
logger.setLevel(logging.ERROR)
logfilename = 'log.log'
handler = logging.handlers.RotatingFileHandler(logfilename,maxBytes = 50000,backupCount = 5) 
handler.setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.info("[STARTUP]")
print "[STARTUP]"

readData()

running = True
while running:
	try:
		checkAndCreate()
		updateThreads()
		sleep(60)
	except KeyboardInterrupt:
		logger.info("[MANUAL SHUTDOWN]")
		print "[MANUAL SHUTDOWN]"
		running = False
	except praw.errors.APIException:
		print "API error, check log file"
		logger.exception("[API ERROR:]")
		sleep(120) 
	except Exception:
		print "Unknown error, check log file"
		logger.exception('[UNKNOWN ERROR:]')
		sleep(120) 