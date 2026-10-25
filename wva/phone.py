"""Phone Link, Windows' own phone app: open it at a tab, call a number, start a text,
and the Windows side of offhook: answer, decline, hang up or mute a phone call by
voice, with the call's sound on the PC.

Phone Link does the Bluetooth part (the PC becomes the phone's hands-free set, like a
car kit). Windows gives other apps no way into that, so this presses Phone Link's own
buttons: the incoming call's Accept / Decline through UI Automation (only the names
of buttons are looked at, never logged), and the call window's keys from Microsoft's
list (Ctrl+Shift+H ends a call, Ctrl+Shift+M mutes it).

Nothing here reads your contacts, messages, photos or call history. "call mom" types
"mom" into Phone Link's own contact search: Phone Link finds her and you press call."""
import re
import sys
import time

from . import ui, win
from .actions import keys, log, open_app, type_text
from .engine import CTX

WINDOWS = sys.platform == "win32"
EXES = {"phoneexperiencehost.exe", "yourphone.exe", "phonelink.exe"}
TOAST_EXES = {"shellexperiencehost.exe", "explorer.exe"}  # where Windows draws notification pop-ups
# Microsoft's Phone Link shortcuts (support.microsoft.com, "Keyboard shortcuts for Phone Link")
TABS = {"messages": "ctrl+1", "texts": "ctrl+1", "calls": "ctrl+2", "apps": "ctrl+3", "photos": "ctrl+4"}
ACCEPT = ("accept", "answer", "pick up")
DECLINE = ("decline", "reject", "ignore")
HANG_UP = ("end call", "hang up", "end the call")
TO_PHONE = ("use phone", "transfer to phone", "switch to phone", "audio to phone", "move to phone", "phone audio")


def _windows(toasts=False):
    """Phone Link's windows, its call window included; with toasts, also Windows'
    notification pop-ups (an incoming call can show there)."""
    def keep(w):
        exe = w.exe.lower()
        return exe in EXES or w.title == "Phone Link" or (
            toasts and exe in TOAST_EXES and w.cls == "Windows.UI.Core.CoreWindow")
    return win.popups(keep)


def _uia():
    """Windows' UI Automation (the accessibility interface screen readers use)."""
    import comtypes
    import comtypes.client
    comtypes.CoInitialize()
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient as U
    return U, comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)


def _buttons(words, toasts=False, avoid=()):
    """Buttons in Phone Link's windows whose name has one of these words (and none of
    avoid). Their names are only compared here, never kept or logged."""
    U, auto = _uia()
    is_button = auto.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_ButtonControlTypeId)
    for w in _windows(toasts):
        try:
            found = auto.ElementFromHandle(w.hwnd).FindAll(U.TreeScope_Descendants, is_button)
        except Exception:
            continue
        for i in range(found.Length):
            b = found.GetElement(i)
            name = (b.CurrentName or "").lower()
            if any(re.search(rf"\b{x}\b", name) for x in words) and not any(x in name for x in avoid):
                yield U, b


def _press(words, toasts=False, avoid=()):
    """Press the first such button: True if one was pressed."""
    for U, b in _buttons(words, toasts, avoid):
        try:
            b.GetCurrentPattern(U.UIA_InvokePatternId).QueryInterface(U.IUIAutomationInvokePattern).Invoke()
            return True
        except Exception:
            continue
    return False


def _front():
    """Phone Link's main or call window to the front: True if there is one."""
    ws = _windows()
    if ws:
        win.focus(ws[0].hwnd)
        time.sleep(0.3)
    return bool(ws)


def ringing():
    """A phone call is ringing (so 'answer the call' means it, not Discord's). Dry runs:
    when the window in front says 'incoming call'."""
    if CTX.dry or not WINDOWS:
        return "incoming call" in (CTX.front or "")
    try:
        return next(_buttons(ACCEPT, toasts=True), None) is not None
    except Exception:
        return False


# ----------------------------------------------------------------- open, tabs, dialling
def open_phone(tab=None):
    """Phone Link, at messages / calls / photos / apps if asked (Ctrl+1…4)."""
    combo = TABS.get(tab or "")
    if CTX.dry:
        return log("open phone link" + (f", keys {combo}" if combo else ""))
    if not _front():
        open_app("phone link")
        for _ in range(40):
            time.sleep(0.2)
            if _windows():
                break
        else:
            return ui.notify("Phone Link didn't open. Is it set up? (Start menu → Phone Link)")
        time.sleep(1.0)
        _front()
    if combo:
        keys(combo)


def phone_keys(combo, what):
    """One of Phone Link's own shortcuts, with its window in front."""
    if CTX.dry:
        return log(f"in phone link: keys {combo}")
    if not _front():
        return ui.notify(f"Open Phone Link first ({what} needs its window)")
    keys(combo)


def dial(number):
    """'call 98765 43210': a tel: link, which Phone Link calls (when Windows asks which
    app should, pick Phone Link and tick 'Always')."""
    digits = re.sub(r"[^\d+]", "", number)
    if CTX.dry:
        return log(f"open tel:{digits}")
    import os
    try:
        os.startfile(f"tel:{digits}")
    except OSError:
        open_phone("calls")
        ui.notify("Windows has no app for phone links: type the number in Phone Link's dialer")


def number_ok(text):
    """'98765 43210' / 'plus 91 98765 43210' / 'nine eight seven…' -> True for a phone number."""
    return 3 <= len(_digits(text)) <= 15


def _digits(text):
    words = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
             "seven": "7", "eight": "8", "nine": "9", "plus": "+", "double": "", "triple": ""}
    t = text.lower().replace("-", " ")
    if re.search(r"[a-z]", re.sub(r"\b(?:" + "|".join(words) + r")\b", "", t)):
        return ""  # a name, not a number
    out, rep = [], 1
    for w in re.findall(r"\+|\d+|[a-z]+", t):
        if w in ("double", "triple"):
            rep = 2 if w == "double" else 3
            continue
        d = words.get(w, w)
        out.append(d * rep if len(d) == 1 else d)
        rep = 1
    return "".join(out)


def call(who):
    """A number: dialled. A name: typed into Phone Link's contact search on the Calls page
    (Phone Link looks it up; you press call)."""
    if number_ok(who):
        return dial(_digits(who))
    open_phone("calls")
    if CTX.dry:
        return type_text(who)
    time.sleep(0.6)
    if not _focus_search():
        return ui.notify(f"Phone Link is open at Calls: search for {who} there")
    type_text(who)


def _focus_search():
    """The first text box in Phone Link's window (on the Calls page: the contact search)."""
    try:
        U, auto = _uia()
        is_edit = auto.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_EditControlTypeId)
        for w in _windows():
            box = auto.ElementFromHandle(w.hwnd).FindFirst(U.TreeScope_Descendants, is_edit)
            if box:
                box.SetFocus()
                time.sleep(0.2)
                return True
    except Exception:
        pass
    return False


def message(who):
    """A new message (Ctrl+N on the Messages page) to this name or number; you write and send it."""
    open_phone("messages")
    if CTX.dry:
        keys("ctrl+n")
        return type_text(who)
    keys("ctrl+n")
    time.sleep(0.8)
    type_text(_digits(who) if number_ok(who) else who)


# ----------------------------------------------------------------- the call itself (offhook)
def answer():
    """Accept the call that's ringing: its sound comes through the PC."""
    if CTX.dry:
        return log("phone link: press Accept")
    if not _press(ACCEPT, toasts=True):
        ui.notify("No call is ringing on Phone Link")


def decline():
    if CTX.dry:
        return log("phone link: press Decline")
    if not _press(DECLINE, toasts=True, avoid=("message",)):  # not 'decline with a message'
        ui.notify("No call is ringing on Phone Link")


def hang_up():
    if CTX.dry:
        return log("phone link: end call (Ctrl+Shift+H)")
    if _press(HANG_UP, avoid=("send",)):
        return
    if not _front():
        return ui.notify("No phone call on Phone Link")
    keys("ctrl+shift+h")


def mute_call():
    if CTX.dry:
        return log("phone link: mute the call (Ctrl+Shift+M)")
    if not _front():
        return ui.notify("No phone call on Phone Link")
    keys("ctrl+shift+m")


def to_phone():
    """The call's sound back on the phone (Phone Link's call window has a button for it)."""
    if CTX.dry:
        return log("phone link: move the call to the phone")
    if not _press(TO_PHONE):
        ui.notify("Couldn't find Phone Link's 'use phone' button: click it in the call window")

