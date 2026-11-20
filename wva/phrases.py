"""Other ways to say a command: everyday English and Hinglish, mapped onto a phrase that
already works. Routing only (what you type or search keeps its words).

SAME: whole phrases. "too loud" means "quieter". Each is matched after the usual clean-up
(politeness, "please", verb forms), so "it's too loud please" works too.
PATTERNS: phrases with a name or song in them, mostly Hindi word order: "spotify kholo"
(open spotify), "arijit singh bajao" (play arijit singh), "chrome band karo" (close chrome).

The tests check that every phrase here lands on the same command as the one it stands for."""
import re

SAME = {
    # ------------------------------------------------------------- volume
    "louder": ["bit louder", "a bit louder", "little louder", "a little louder", "too quiet", "it's too quiet",
               "its too quiet", "i can't hear", "i can't hear it", "i can't hear anything", "can't hear", "cant hear",
               "can't hear anything", "can't hear it", "more volume", "more sound", "volume higher", "higher volume",
               "up the volume", "volume plus", "increase it", "turn it up a bit", "a tad louder", "louder louder",
               "make it a bit louder", "sound up", "volume up a bit", "little more volume", "a bit more volume",
               "it's too low", "too low", "pump it up", "boost the volume", "boost the sound", "turn it up some"],
    "quieter": ["bit quieter", "a bit quieter", "little quieter", "a little quieter", "too loud", "it's too loud",
                "its too loud", "way too loud", "less volume", "less sound", "volume lower", "lower volume",
                "volume minus", "lower it", "turn it down a bit", "softer", "not so loud", "less loud",
                "tone it down", "bring it down", "sound down", "volume down a bit", "a tad quieter", "it's loud",
                "too much volume", "my ears", "turn it down some", "make it a bit quieter"],
    "volume 100": ["full volume", "max volume", "volume max", "maximum volume", "volume maximum", "volume full",
                   "full blast", "max it out", "max out the volume", "maximum sound", "volume to max",
                   "volume to the max", "all the way up", "volume all the way up", "turn it all the way up",
                   "crank it all the way", "hundred percent volume", "volume hundred"],
    "volume 50": ["half volume", "volume half", "half the volume", "medium volume", "volume medium",
                  "volume halfway", "normal volume", "volume normal"],
    "volume 20": ["low volume", "volume low", "quiet volume", "background volume"],
    "volume 10": ["very low volume", "volume very low", "minimum volume", "volume minimum", "lowest volume",
                  "volume lowest", "barely audible"],
    "mute": ["shut up", "quiet", "be quiet", "sound off", "kill the sound", "no sound", "turn off the sound",
             "turn the sound off", "cut the sound", "mute everything", "mute all", "hush", "mute the pc",
             "mute the computer", "shh", "shhh", "silence please", "silence everything", "mute all sound",
             "mute the sound", "mute audio", "audio off", "stop all sound", "volume zero", "volume off"],
    "unmute": ["sound on", "sound back on", "turn the sound back on", "turn on the sound", "turn the sound on",
               "bring back the sound", "unmute everything", "give me sound", "audio on", "unmute all", "volume on",
               "unmute the pc", "unmute the computer"],
    # ------------------------------------------------------------- music and videos
    "pause music": ["hold on pause", "kill the music", "music off", "stop playing", "pause the song", "freeze the music",
                    "hold the music", "pause for a sec", "pause for a second", "wait pause", "pause pause",
                    "stop the song", "turn off the music", "turn the music off", "enough music", "no more music",
                    "pause the track", "stop the track", "pause the video", "stop the video", "pause this video",
                    "pause the movie", "pause the show", "pause the episode", "hold on", "one sec pause"],
    "play music": ["music on", "continue playing", "keep playing", "play some music", "put on some music",
                   "start the music", "start some music", "turn on the music", "turn the music on",
                   "resume playing", "resume the song", "continue the song", "continue the music", "let it play",
                   "unpause the music", "play the song", "play the music again", "resume the video", "play the video",
                   "continue the video", "unpause the video", "resume the movie", "carry on playing", "go on playing",
                   "put some music on", "some music please", "play some songs", "play my music"],
    "next song": ["different song", "another song", "change the song", "change song", "something else",
                  "play something else", "skip this one", "skip the song", "next track please", "not this song",
                  "i don't like this song", "i hate this song", "skip that", "skip track",
                  "skip this track", "play another song", "switch the song", "new song", "next one please",
                  "go to the next song", "forward a song", "next tune", "skip ahead a song"],
    "previous song": ["go back a song", "back one song", "play the last song", "the song before", "play that again",
                      "replay the song", "restart the song", "start the song over", "play it again", "replay",
                      "one more time", "from the start", "start over", "play the song again", "play this again",
                      "replay that", "back a song", "go back one song", "previous track please",
                      "the last one again", "rewind the song"],
    "what's playing": ["name of this song", "what's the name of this song", "who's singing", "who is singing",
                       "who sings this", "what am i listening to", "what is this song", "song name", "track name",
                       "what's this track", "which track is this", "what track is this", "who's this",
                       "who is this artist", "who made this song", "current song", "what's the song"],
    "like this song": ["i like this song", "i love this song", "this song is good", "save this song",
                       "add this to my liked songs", "heart this song", "favorite this song", "favourite this song"],
    # ------------------------------------------------------------- windows and apps
    "take a screenshot": ["screenshot this", "snip", "snip it", "snip this", "screen snip", "snipping",
                          "cut out a part of the screen", "screenshot a part", "screenshot part of the screen",
                          "clip the screen", "screenshot please", "ss", "take a ss", "take ss"],
    "screenshot the screen": ["capture the screen", "grab the screen", "print screen", "capture my screen",
                              "screenshot everything", "screenshot the whole thing", "full screenshot",
                              "screenshot my screen", "save the screen", "capture everything"],
    "show desktop": ["show me the desktop", "clear the screen", "hide all windows", "clear my screen",
                     "hide all the windows", "get everything out of the way", "go to my desktop",
                     "show my desktop", "back to desktop", "back to the desktop", "home screen"],
    "previous window": ["alt tab", "switch back", "go back to the last app", "last app", "previous app",
                        "other app", "other window", "the other window", "the other app", "switch apps",
                        "switch windows", "back to the other window"],
    "snap right": ["put it on the right", "right side", "move it to the right side", "right half",
                   "put this on the right", "send it right"],
    "snap left": ["put it on the left", "left side", "move it to the left side", "left half",
                  "put this on the left", "send it left"],
    "maximize": ["make it big", "full size", "make it full", "make it fill the screen", "make the window big",
                 "biggest", "maximize the window please", "blow it up", "make this big"],
    "minimize": ["hide it", "get it out of the way", "put it away", "minimize this window", "minimise this",
                 "send it down", "hide this window", "make it go away"],
    "close window": ["close this one", "close the current window", "close current window", "shut this",
                     "shut this window", "shut it", "exit this", "exit this window", "kill this window",
                     "close what's in front", "get rid of this window"],
    "what's open": ["what apps are running", "what's running", "show running apps", "what do i have open",
                    "what's open right now", "which windows are open", "list my apps", "open apps"],
    # ------------------------------------------------------------- the PC
    "lock the pc": ["lock up", "lock", "lock it up", "lock my computer", "lock screen", "lock the laptop",
                    "lock everything", "lock this", "lock this pc", "lock the system"],
    "sleep": ["sleep mode", "go to sleep mode", "put it to sleep", "sleep now", "put the laptop to sleep",
              "send it to sleep", "goodnight", "good night"],
    "shutdown": ["power off", "power down", "shut it down", "shut everything down", "turn off my pc",
                 "turn off my computer", "turn off my laptop", "switch off the pc", "switch off my pc",
                 "power off the pc", "power down the pc", "shut off the pc", "shut off the computer"],
    "restart the pc": ["restart my pc", "restart my computer", "restart my laptop", "reboot my pc",
                       "reboot my computer", "reboot the computer", "restart the system", "restart windows"],
    "brightness down": ["dim the screen", "dim it", "dimmer", "screen dimmer", "too bright", "it's too bright",
                        "lower brightness", "less brightness", "darker screen", "dim the display", "my eyes hurt"],
    "brightness up": ["too dark", "it's too dark", "screen brighter", "brighter please", "more brightness",
                      "increase brightness", "brighten the screen", "brighten it", "brighter screen"],
    "brightness 100": ["full brightness", "max brightness", "maximum brightness", "brightness max",
                       "brightness full", "brightness all the way up"],
    "brightness 10": ["lowest brightness", "minimum brightness", "brightness minimum", "brightness lowest"],
    "dark mode": ["night mode", "dark theme", "switch to dark", "go dark", "dark mode please", "make it dark"],
    "light mode": ["day mode", "light theme", "switch to light", "go light", "light mode please"],
    "battery": ["how much charge do i have", "how much charge", "charge left", "am i charging", "is it charging",
                "battery status", "battery life", "how long will the battery last", "power left", "battery check",
                "check the battery", "check battery", "is the charger plugged in", "how's the battery",
                "how much juice", "how much juice is left"],
    "ram": ["how much ram am i using", "how's my ram", "ram usage", "memory left", "how much memory",
            "how much memory am i using", "check my ram", "check ram", "ram check", "free ram", "how much ram"],
    "cpu": ["how hot is my cpu", "cpu temp", "cpu temperature", "processor usage", "how busy is the cpu", "cpu load",
            "how's my cpu", "check the cpu", "check cpu", "cpu check", "cpu status"],
    "gpu": ["how's my gpu", "gpu usage", "graphics card temp", "vram usage", "check the gpu", "check gpu",
            "gpu check", "gpu status", "how hot is the graphics card", "how's my graphics card"],
    "disk space": ["free space", "space left", "how much space", "storage space", "how full is my disk",
                   "how full is my drive", "is my disk full", "check storage", "check disk space",
                   "how much storage", "how much storage do i have", "storage check"],
    "weather": ["temperature outside", "how hot is it", "how cold is it", "what's it like outside", "is it cold outside",
                "is it hot outside", "forecast", "weather forecast", "weather update", "today's weather",
                "weather report", "what's the temperature", "temperature", "how's it outside"],
    "what time is it": ["what time", "time now", "the time", "what's the time please", "time check please",
                        "got the time", "what's the clock say", "clock"],
    "what's the date": ["what's the date today", "what date is it", "date today", "which date is it", "today",
                        "what's today's date please", "date please", "what's the day"],
    "status": ["how's my pc", "how's the pc", "how's my computer", "how is everything", "pc health",
               "system health", "how's the system", "check my pc"],
    # ------------------------------------------------------------- browser
    "new tab": ["another tab", "fresh tab", "blank tab", "new browser tab", "one more tab", "empty tab",
                "open another tab", "open one more tab", "add a tab"],
    "close tab": ["kill this tab", "kill the tab", "get rid of this tab", "close current tab", "shut this tab",
                  "shut the tab", "close the current tab", "exit this tab", "remove this tab", "lose this tab"],
    "reopen tab": ["undo close tab", "bring back the tab", "i closed the wrong tab", "open the tab i closed",
                   "get the tab back", "restore the tab", "bring that tab back"],
    "private window": ["open incognito", "incognito", "incognito mode", "private mode", "private browsing",
                       "go incognito", "incognito tab", "private tab", "secret window", "incognito window please"],
    "scroll down": ["go down", "move down", "page down please", "scroll down please"],
    "scroll up": ["go up", "move up", "page up please", "scroll up please"],
    "reload page": ["refresh it", "refresh this", "reload it", "reload this", "the page is stuck",
                    "page not loading", "hit refresh", "f5"],
    "zoom in": ["bigger text", "make it readable", "i can't read this", "make the words bigger", "enlarge the text"],
    "zoom out": ["smaller text", "make the words smaller", "shrink the text", "zoom out a bit"],
    # ------------------------------------------------------------- the agent itself
    "help": ["what do you do", "what can you do for me", "what are the commands", "show me what i can say",
             "how does this work", "i need help", "help please", "guide", "the guide", "open the guide",
             "show the guide", "what can i ask", "what can i ask you"],
}

# Hindi helper words: who said them doesn't change the command
_HI_LEAD = r"(?:bhai|bro|yaar|yar|zara|jara|ek baar|ek|jaldi se|jaldi|abhi|please|plz|arre|arey|oye)\s+"
_HI_TRAIL = r"\s+(?:na|yaar|yar|bhai|bro|zara|jaldi|jaldi se|abhi|please|plz|bhi|ji|toh|to)$"

OPEN_V = r"(?:kholo|khol do|khol de|kholna|khol|kholdo|open karo|open kar do|open kardo|open kar|chalu karo|chalu kar do|" \
         r"start karo|start kar do|launch karo|launch kar do|shuru karo)"
CLOSE_V = r"(?:band karo|band kar do|band kardo|band kar|bandh karo|bandh kar do|bandh kardo|close karo|close kar do|" \
          r"close kardo|close kar|hatao|hata do|quit karo)"
PLAY_V = r"(?:bajao|baja do|bajado|chalao|chala do|chalado|lagao|laga do|lagado|sunao|suna do|play karo|play kar do|" \
         r"play kardo|play kar)"
SEARCH_V = r"(?:search karo|search kar do|search kardo|search kar|dhundo|dhoondo|dhundho|dhoondho|dhundh do|khojo|" \
           r"google karo|google kar do)"
MUTE_V = r"(?:mute karo|mute kar do|mute kardo|mute kar)"
SONG = r"(?:gaana|gana|gaane|gane|gaano|song|songs|music|track)"
LOUD = r"(?:volume|awaaz|awaz|aawaz|avaaz|aavaz|sound|aawaj|awaj)"
PC = r"(?:pc|computer|laptop|system)"
UP_V = r"(?:badhao|badha do|badhado|badha|tez karo|tez kar do|zyada karo|jyada karo|upar karo|badi karo|up karo)"
DOWN_V = r"(?:kam karo|kam kar do|kamkaro|kam kardo|kam|dheere karo|dheemi karo|dhimi karo|halki karo|neeche karo|" \
         r"ghatao|ghata do|down karo)"
STOP_V = r"(?:roko|rok do|rokdo|ruko|ruk jao|pause karo|pause kar do|pause kardo|band karo|band kar do|band kardo|bandh karo)"

# (pattern on the whole command, what it means). The first that fits wins; a pattern with
# a name in it (\1) never takes a command that types, searches or says free text.
PATTERNS = [
    # music
    (rf"{SONG} {STOP_V}", "pause music"),
    (rf"{SONG} (?:chalao|chala do|bajao|baja do|lagao|laga do|chalu karo|chalu kar do|play karo|shuru karo|sunao)", "play music"),
    (rf"(?:koi |ek )?(?:aur|dusra|doosra|naya) {SONG}(?: chalao| bajao| lagao| laga do)?", "next song"),
    (rf"(?:agla|agle|aagla|next) {SONG}(?: chalao| bajao| lagao| laga do| karo)?", "next song"),
    (rf"(?:pichla|pichhla|pichle|purana|previous|last) {SONG}(?: chalao| bajao| lagao| laga do| karo)?", "previous song"),
    (rf"{SONG} (?:badlo|badal do|change karo|change kar do|skip karo|skip kar do)", "next song"),
    (rf"(?:yeh |ye )?{SONG} (?:phir se|fir se|dobara|wapas) (?:chalao|bajao|lagao|laga do|sunao)", "previous song"),
    (r"(?:phir se|fir se|dobara|wapas) (?:chalao|bajao|lagao|sunao)", "previous song"),
    (rf"(?:yeh |ye )?(?:kaunsa|konsa|kaun sa|kon sa|kya) {SONG} (?:hai|chal raha hai|baj raha hai)", "what's playing"),
    (r"(?:skip karo|skip kar do|aage karo|aage badhao|agla|next karo)", "next song"),
    # volume
    (rf"{LOUD} (?:full karo|full kar do|poora karo|puri karo|max karo|maximum karo)", "volume 100"),
    (rf"{LOUD} (?:band karo|band kar do|bandh karo|off karo|mute karo|mute kar do)", "mute"),
    (rf"(?:thoda |thodi |aur )?{LOUD} (?:thoda |thodi |aur |zara |aur thoda )?{UP_V}(?: thoda| thodi| aur)?", "volume up"),
    (rf"(?:thoda |thodi |aur )?{LOUD} (?:thoda |thodi |aur |zara |aur thoda )?{DOWN_V}(?: thoda| thodi| aur)?", "volume down"),
    (rf"{LOUD} (?:wapas|vapas) (?:lao|chalu karo|on karo)|unmute karo|unmute kar do", "unmute"),
    (r"(?:bahut|bohot|bahot|kaafi) (?:tez|zor|loud) hai|(?:bahut|bohot) (?:awaaz|awaz) (?:hai|aa rahi hai)", "quieter"),
    (r"(?:sunai nahi de raha|kuch sunai nahi de raha|awaaz nahi aa rahi|awaz nahi aa rahi|aawaz nahi aa rahi)", "louder"),
    (r"(?:chup|chup karo|chup kar|chup ho jao|chup raho|shant|shaant|shant ho jao)", "mute"),
    (rf"{MUTE_V}", "mute"),
    (r"(?:ruko|ruk jao|roko|rok do|ruk|pause karo|pause kar do|pause kardo)", "pause"),
    (r"(?:chalao|play karo|play kar do|shuru karo|chalu karo|resume karo)", "play"),
    # screen and PC
    (r"(?:brightness|roshni|screen) (?:badhao|badha do|tez karo|zyada karo|jyada karo|upar karo)", "brightness up"),
    (r"(?:brightness|roshni|screen) (?:kam karo|kam kar do|ghatao|ghata do|dheemi karo|neeche karo)", "brightness down"),
    (r"(wifi|bluetooth|net|internet) (?:on|chalu) (?:karo|kar do|kardo)", r"turn on \1"),
    (r"(wifi|bluetooth|net|internet) (?:off|band) (?:karo|kar do|kardo)", r"turn off \1"),
    (r"(?:naya|nayi|new|ek aur) tab(?: kholo| khol do| open karo| chahiye)?", "new tab"),
    (rf"(?:yeh |ye |is )?tab {CLOSE_V}", "close tab"),
    (rf"(?:yeh |ye |is )?window {CLOSE_V}|(?:yeh|ye|isko|isse|ise) {CLOSE_V}", "close window"),
    (r"(?:yeh |ye |isko |ise )?(?:chhota|chota|minimize) (?:karo|kar do|kardo)", "minimize"),
    (r"(?:yeh |ye |isko |ise )?(?:bada|badi|full screen|fullscreen|maximize) (?:karo|kar do|kardo)", "maximize"),
    (r"(?:screenshot|ss|screen shot) (?:lo|le lo|lelo|le|khicho|kheencho|khich lo|lena|le do|nikalo)", "take a screenshot"),
    (rf"(?:{PC} )?lock (?:karo|kar do|kardo|kar)", "lock the pc"),
    (rf"{PC} (?:band karo|band kar do|bandh karo|bandh kar do|shutdown karo|shutdown kar do|off karo|off kar do)", "shutdown"),
    (rf"{PC} (?:restart karo|restart kar do|restart kardo|reboot karo|dobara chalu karo)", "restart the pc"),
    (rf"{PC} (?:sula do|sleep karo|sleep kar do|so jao)|so jao", "sleep"),
    (r"desktop (?:dikhao|dikha do|pe jao|par jao)|sab (?:chhota|chota|minimize) (?:karo|kar do)", "show desktop"),
    # questions
    (r"(?:time|samay|waqt|tym) (?:kya hai|kya hua|kya hua hai|kya ho raha hai|kitna hua|kitna hua hai|batao|bata do|bataao)"
     r"|kya time (?:hai|ho gaya|hua)|kitne baje(?: hain| hai| gaye)?|kitna baj gaya|kitne baj gaye", "what time is it"),
    (r"(?:aaj|aj) (?:ki date|ki tareekh|ki tarikh|kya date hai|kaun sa din hai|kaunsa din hai|kya din hai|konsa din hai)"
     r"|date (?:kya hai|batao|bata do)|aaj kya hai", "what's the date"),
    (r"(?:mausam|mosam|weather|mausum) (?:kaisa hai|kaisa rahega|batao|bata do|kya hai|kaisa hoga)", "weather"),
    (r"(?:kya |aaj |kal )?(?:baarish|barish|barsat) (?:hogi|hone wali hai|ho rahi hai|aayegi)", "will it rain"),
    (r"(?:battery|charge|charging) (?:kitni hai|kitna hai|kitni bachi hai|kitna bacha hai|batao|kitni)", "battery"),
    (r"(?:ram|memory) (?:kitni hai|kitna hai|kitni use ho rahi hai|batao)", "ram"),
    (r"(?:madad|help) (?:karo|chahiye|kar do)|kya kya (?:bol sakta hoon|kar sakte ho|kar sakta hai)", "help"),
    # the music bot in Discord: "bot pe kesariya bajao", "kesariya bot pe chalao", "bot gaana skip karo"
    (r"(?:bot|jockie|jockey)(?: pe| par| se| mein| me)? (.+?) (?:bajao|baja do|chalao|chala do|lagao|laga do|play karo)",
     r"bot play \1"),
    (r"(.+?) (?:bot|jockie|jockey) (?:pe|par|se|mein|me) (?:bajao|baja do|chalao|chala do|lagao|laga do|play karo)",
     r"bot play \1"),
    (rf"(?:bot|jockie|jockey)(?: pe| par| se)? (?:{SONG} )?(?:skip karo|skip kar do|agla|next karo|badlo)", "bot skip"),
    (rf"(?:bot|jockie|jockey)(?: pe| par| se)? (?:{SONG} )?{STOP_V}", "bot pause"),
    # with a name in it (Hindi word order: the name first)
    (rf"(.+?) {OPEN_V}", r"open \1"),
    (rf"(.+?) {CLOSE_V}", r"close \1"),
    (rf"(.+?) {PLAY_V}", r"play \1"),
    (rf"(.+?) {SEARCH_V}", r"search \1"),
    (rf"(.+?) {MUTE_V}", r"mute \1"),
    (r"(.+?) (?:pe|par|mein|me) (?:jao|chalo|le chalo|le jao|switch karo)", r"switch to \1"),
    (r"(.+?) (?:ka|ki) (?:volume|awaaz|awaz) (badhao|kam karo|tez karo|ghatao)", r"turn \1 \2"),
    # English with a name in it
    (r"(?:get me|gimme|bring me|can i get|can i have|boot up|boot|start up|pull up|load up|fire off) (.+)", r"open \1"),
    (r"(?:close down|get rid of|kill off|close out|close out of|quit out of|exit out of|exit out) (.+)", r"close \1"),
    (r"shutdown (?!(?:the |my )?(?:computer|pc|laptop|system|windows)\b|in\b)(.+)", r"close \1"),
    (r"(?:switch over to|go over to|flip to|flip over to|hop to|hop over to|take me back to|change over to|"
     r"go back over to|move over to) (.+)", r"switch to \1"),
    (r"(?:play|put on|throw on|blast) (?:some |a few |my )?(?:music|songs|tunes|tracks)", "play music"),
]
# A pattern's \1 never starts with one of these: it's text to type, search or say.
FREE = {"type", "write", "text", "message", "search", "google", "say", "ask", "translate", "define", "dictate",
        "call", "dial", "find", "look", "play", "watch", "open", "close", "switch", "mute", "turn", "go"}
_PATTERNS = [(re.compile(p), r) for p, r in PATTERNS]


def rewrite(t):
    """One command's text -> what it means, by the patterns (Hindi helper words first stripped)."""
    s = t
    while (m := re.match(_HI_LEAD, s)) and len(s) > m.end():
        s = s[m.end():]
    while (m := re.search(_HI_TRAIL, s)) and m.start() > 0:
        s = s[:m.start()]
    for pat, rep in _PATTERNS:
        m = pat.fullmatch(s)
        if not m:
            continue
        if m.groups():
            name = m.group(1)
            if not name or name.split()[0] in FREE or len(name.split()) > 6:
                continue
        return m.expand(rep)
    return t
