#!/usr/bin/env python3
"""Fetch + render the Avid Pro Tools shortcut icons (reproducible source step).

Glyphs are Google Material Symbols (Apache-2.0, ``ms:`` names) and Microsoft
Fluent UI System Icons (MIT), rendered through ``../icon_fetch.py``. Glyphs
that mean the same as in the REAPER, Ableton Live or FL Studio set are copied
byte-identical from it (``BORROW``). Composites (an icon with a badge, an
arrow or a stroke) use ``../dcc_glyphs.py``. The play, fade, trim and clip
glyphs and the short text glyphs are drawn here.

The ESC mark is the Pro Tools logo from Simple Icons (``protools``, artwork
CC0-1.0) reduced to a 32x32 1-bit trace. See SOURCES.md.

Every drawn or composed file is guarded: a committed PNG is left as it is, so
a hand edit survives a re-run. To redraw one, delete its PNG first.

    pip install cairosvg Pillow numpy
    PYTHONPATH=. python polyhost/res/overlay_sources/protools/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import dcc_glyphs as g  # noqa: E402
from polyhost.res.overlay_sources import icon_fetch, number_badge  # noqa: E402

ICONS = {
    # --- bases for the composites (not drawn on a key themselves)
    "_auto": "ms:show_chart",
    "_autoall": "ms:stacked_line_chart",
    "_sel": "ms:select",
    "_clip": "ms:crop_16_9",
    "_gain": "ms:signal_cellular_alt",
    "_piano": "ms:piano",
    "_file": "ms:draft",
    "_flag": "ms:flag",
    "_eye": "ms:visibility",
    "_blob": "ms:bubble_chart",
    "_playlist": "ms:playlist_add",
    "_dupl": "ms:control_point_duplicate",
    "_copy": "Copy",
    "_cut": "Cut",
    "_paste": "Clipboard Paste",
    "_save": "Save",
    "_erase": "ms:ink_eraser",
    "_pen": "Pen",
    "_target": "ms:adjust",
    "_add": "ms:add",
    "_all": "ms:done_all",
    "_down": "ms:arrow_downward",
    "_up": "ms:arrow_upward",
    "_left": "ms:chevron_left",
    "_right": "ms:chevron_right",
    "_front": "ms:flip_to_front",
    "_back": "ms:flip_to_back",
    "_height": "ms:height",
    "_unfold": "ms:unfold_more",
    "_note": "ms:music_note",
    "_crop": "ms:crop",
    "_glide": "ms:trending_flat",
    "_thin": "ms:compress",
    "_send": "ms:call_split",
    "_lock": "Lock Closed",
    "_moveitem": "ms:move_item",
    "_undo": "ms:undo",
    # --- no modifier / Commands Keyboard Focus
    "zoomtoggle": "ms:center_focus_strong",
    "playlistview": "ms:ssid_chart",
    "playedit": "ms:play_arrow",
    "playtimeline": "ms:play_circle",
    "prevedit": "ms:keyboard_tab_rtl",
    "nextedit": "ms:keyboard_tab",
    "followplay": "ms:moving",
    "cyclemodes": "ms:change_circle",
    "shuffle": "ms:shuffle",
    "slip": "ms:swap_horiz",
    "spot": "ms:my_location",
    "gridmode": "ms:grid_4x4",
    "zoomer": "ms:search",
    "trimmer": "ms:compare_arrows",
    "grabber": "ms:pan_tool",
    "scrubber": "ms:volume_up",
    "smarttool": "ms:auto_fix_high",
    "centerstart": "ms:align_justify_flex_start",
    "centerend": "ms:align_justify_flex_end",
    "insstart": "ms:text_select_jump_to_beginning",
    "insend": "ms:text_select_jump_to_end",
    # --- Shift
    "linktl": "ms:link",
    "linktrack": "ms:dataset_linked",
    "folder": "Folder Open",
    "inputmon": "ms:hearing",
    "targetup": "ms:move_up",
    "targetdown": "ms:move_down",
    "targetfirst": "ms:filter_center_focus",
    "markernames": "ms:comment",
    "markerfollow": "ms:flag_circle",
    "markerlane": "ms:flag",
    "showtarget": "ms:low_priority",
    "recentplaylist": "ms:history",
    "firstplaylist": "ms:vertical_align_top",
    "lastplaylist": "ms:vertical_align_bottom",
    # --- Command / Ctrl
    "printscore": "ms:print",
    "clear": "ms:ink_eraser",
    "heal": "ms:healing",
    "stripsilence": "ms:noise_control_off",
    "capture": "ms:screenshot_region",
    "identifybeat": "ms:speed",
    "online": "ms:sync",
    "prepost": "ms:settings_ethernet",
    "syncpoint": "ms:anchor",
    "pinfocus": "ms:keep",
    "transportmaster": "ms:settings_remote",
    # --- Option / Alt
    "universe": "ms:public",
    "melodyne": "ms:bubble_chart",
    "repeatsel": "ms:event_repeat",
    "shiftsel": "ms:arrow_range",
    "mergemarkers": "ms:bookmarks",
    "automonitor": "ms:headset_mic",
    "clearclip": "ms:report_off",
    "looprec": "ms:repeat_on",
    "workspace": "ms:inventory_2",
    "project": "ms:topic",
    "winfront": "ms:flip_to_front",
    "duration": "ms:straighten",
    "transpose": "ms:swap_vertical_circle",
    "splitnotes": "ms:alt_route",
    "taskmanager": "ms:checklist",
    "volumes": "ms:hard_drive",
    "eventlist": "ms:list",
    "trackview": "ms:swap_vert",
    # --- Option+Shift / Alt+Shift
    "spaceclips": "ms:horizontal_distribute",
    "tce": "ms:hourglass",
    "duptracks": "ms:dynamic_feed",
    "commit": "ms:approval",
    "trackpreset": "ms:assignment",
    "winback": "ms:flip_to_back",
    "retrorec": "ms:replay",
    # --- Command+Shift / Ctrl+Shift
    "openrecent": "ms:restore_page",
    "closesession": "ms:close",
    "newtrack": "ms:add_row_below",
    "quickpunch": "ms:bolt",
    "trackpunch": "ms:offline_bolt",
    "videoonline": "ms:videocam",
    "findclip": "ms:manage_search",
    "clearfind": "ms:search_off",
    "unused": "ms:hide_source",
    "clearclips": "ms:playlist_remove",
    "timestamp": "ms:schedule",
    "exportdef": "ms:file_export",
    "exportclips": "ms:audio_file",
    "suspendgroups": "ms:group_off",
    "chat": "Chat",
    "settarget": "ms:track_changes",
    "cycleprev": "ms:arrow_upward",
    "cyclenext": "ms:arrow_downward",
    # --- Command+Option / Ctrl+Alt
    "dashboard": "ms:dashboard",
    "repeatfill": "ms:content_paste_go",
    "narrowmix": "ms:view_column",
    "scrolltrack": "ms:swipe_vertical",
    "groupclips": "ms:join",
    "regroup": "ms:workspaces",
    "autoclips": "ms:auto_awesome_motion",
    "winconfig": "ms:dashboard_customize",
    "onlinerec": "ms:emergency_recording",
    # --- Command+Option+Shift / Ctrl+Alt+Shift
    "newfolder": "ms:create_new_folder",
    "bouncetrack": "ms:outbox",
    "shrinkstart": "ms:start",
    # --- Control / Start, and its combinations
    "midieditor": "ms:queue_music",
    "newplaylist": "ms:playlist_add",
    "transcription": "ms:subtitles",
    "toollock": "ms:build_circle",
    "batchrename": "ms:drive_file_rename_outline",
    "gainline": "ms:timeline",
    "gaininfo": "ms:info",
    "timelock": "ms:lock_clock",
    "zoomallkeep": "ms:aspect_ratio",
    "soundbase": "ms:album",
    "scoreeditor": "ms:music_note",
    "revisions": "ms:manage_history",
    "zoomselh": "ms:expand_content",
    "dupplaylist": "ms:control_point_duplicate",
    "renderer": "ms:spatial_audio",
    "dockedmidi": "ms:dock_to_bottom",
    "sketch": "ms:gesture",
    "hidefloat": "ms:hide",
    "setprepost": "ms:pin_drop",
    "rulerlines": "ms:view_week",
    "folderlines": "ms:vertical_distribute",
    "mpecolor": "ms:palette",
    "vzoomdefault": "ms:density_medium",
}

# Same action as in a sibling DAW set: a byte-identical copy.
BORROW = {
    "playstop.png": "reaper",       # play/stop
    "pause.png": "reaper",          # pause
    "record.png": "reaper",         # record
    "ratedown.png": "reaper",       # slower playback (half speed)
    "tostart.png": "reaper",        # go to start
    "toend.png": "reaper",          # go to end
    "zoomin.png": "reaper",         # horizontal zoom in
    "zoomout.png": "reaper",        # horizontal zoom out
    "vzoomin.png": "reaper",        # vertical zoom in
    "vzoomout.png": "reaper",       # vertical zoom out
    "zoomsel.png": "reaper",        # zoom to selection
    "zoomproject.png": "reaper",    # zoom to the whole project / session
    "zoomitems.png": "reaper",      # zoom to all items / clips
    "nudgeleft.png": "reaper",      # nudge left
    "nudgeright.png": "reaper",     # nudge right
    "gridleft.png": "reaper",       # move left by grid
    "gridright.png": "reaper",      # move right by grid
    "mute.png": "reaper",           # mute
    "lock.png": "reaper",           # lock items / clips
    "group.png": "reaper",          # group
    "ungroup.png": "reaper",        # ungroup
    "split.png": "reaper",          # split / separate at the cursor
    "nexttransient.png": "reaper",  # next transient
    "prevtransient.png": "reaper",  # previous transient
    "midikeyboard.png": "reaper",   # virtual MIDI keyboard
    "repeat.png": "reaper",         # loop playback
    "panic.png": "reaper",          # all notes off
    "keyhelp.png": "reaper",        # key bindings window
    "prevtrack.png": "reaper",      # previous track
    "nexttrack.png": "reaper",      # next track
    "prevtake.png": "reaper",       # previous take (playlist)
    "nexttake.png": "reaper",       # next take (playlist)
    "maxheight.png": "reaper",      # taller track
    "minheight.png": "reaper",      # shorter track
    "transport.png": "reaper",      # transport
    "duplicate.png": "reaper",      # duplicate
    "video.png": "reaper",          # video
    "mixer.png": "reaper",          # mixer window
    "takefx.png": "reaper",         # take FX = clip effects
    "bounce.png": "reaper",         # bounce / render the mix
    "import.png": "reaper",         # import media
    "fade.png": "ableton",          # create fades
    "solo.png": "ableton",          # solo
    "arm.png": "ableton",           # record-arm
    "recsession.png": "ableton",    # record variant (half-speed record)
    "snapgrid.png": "ableton",      # snap to grid
    "insertsilence.png": "ableton",  # insert silence
    "consolidate.png": "ableton",   # consolidate
    "quantize.png": "ableton",      # quantize
    "crop.png": "ableton",          # crop clips to the selection
    "rename.png": "ableton",        # rename
    "search.png": "ableton",        # search
    "fitheight.png": "ableton",     # fit track height
    "draw.png": "flstudio",         # pencil tool
    "mutesel.png": "flstudio",      # mute selected clips
}

# name -> (base, badge): base reduced to the upper left, badge at lower right.
BADGE = {
    "copyauto": ("_copy", "_auto"),
    "cutwithauto": ("_cut", "_auto"),
    "clearwithauto": ("_erase", "_auto"),
    "dupauto": ("duplicate", "_auto"),
    "silenceauto": ("insertsilence", "_auto"),
    "pasteauto": ("_auto", "_paste"),
    "writeauto": ("_auto", "_pen"),
    "writeall": ("_autoall", "_pen"),
    "trimauto": ("_auto", "_crop"),
    "trimautoall": ("_autoall", "_crop"),
    "glide": ("_auto", "_glide"),
    "glideall": ("_autoall", "_glide"),
    "thinauto": ("_auto", "_thin"),
    "autotosend": ("_auto", "_send"),
    "cutauto": ("_autoall", "_cut"),
    "cutgain": ("_gain", "_cut"),
    "copygain": ("_gain", "_copy"),
    "cleargain": ("_gain", "_erase"),
    "gainup": ("_gain", "_up"),
    "gaindown": ("_gain", "_down"),
    "gainback": ("_gain", "_left"),
    "gainfwd": ("_gain", "_right"),
    "cutfx": ("takefx", "_cut"),
    "copyfx": ("takefx", "_copy"),
    "clearfx": ("takefx", "_erase"),
    "savefx": ("takefx", "_save"),
    "melodynedit": ("_blob", "_pen"),
    "melodynefull": ("_blob", "_height"),
    "importmidi": ("import", "_piano"),
    "importvideo": ("import", "video"),
    "importsession": ("import", "folder"),
    "quantizeclip": ("quantize", "_clip"),
    "quantizemidi": ("quantize", "_piano"),
    "zoomselmidi": ("zoomsel", "_piano"),
    "midiallnotes": ("_piano", "_unfold"),
    "loopclip": ("_clip", "repeat"),
    "clipfront": ("_clip", "_front"),
    "clipback": ("_clip", "_back"),
    "copytarget": ("_copy", "_target"),
    "copynew": ("_copy", "_add"),
    "movetarget": ("_moveitem", "_target"),
    "movenew": ("_moveitem", "_add"),
    "settargetall": ("settarget", "_all"),
    "mergemidi": ("_paste", "_piano"),
    "restoresel": ("_sel", "_undo"),
    "gainpoint": ("_gain", "_add"),
    "newplaylists": ("_playlist", "_all"),
    "newplaylistsel": ("_playlist", "_sel"),
    "dupplaylists": ("_dupl", "_all"),
    "dupplaylistsel": ("_dupl", "_sel"),
    "trimfilestart": ("_file", "tostart"),
    "trimfileend": ("_file", "toend"),
    "trimfile": ("_file", "_crop"),
    "songstart": ("tostart", "_note"),
    "sketchfront": ("sketch", "_front"),
    "extnext": ("_sel", "nexttransient"),
    "extprev": ("_sel", "prevtransient"),
    "extstart": ("_sel", "tostart"),
    "extend": ("_sel", "toend"),
    "extsongstart": ("_sel", "_note"),
    "showselstart": ("_lbr", "_eye"),
    "showselend": ("_rbr", "_eye"),
    "selclips": ("_clip", "_all"),
    "_selflag": ("_sel", "_flag"),
    "_selclip": ("_sel", "_clip"),
    "nextclip": ("_clip", "_right"),
    "prevclip": ("_clip", "_left"),
}
# name -> (base, forward): base over a heavy arrow.
ARROW = {
    "prevzone": ("_flag", False),
    "nextzone": ("_flag", True),
    "moveeditleft": ("_sel", False),
    "moveeditright": ("_sel", True),
    "prevview": ("_auto", False),
    "nextview": ("_auto", True),
    "prevviewall": ("_autoall", False),
    "nextviewall": ("_autoall", True),
    "dupextend": ("duplicate", True),
    "cyclevideo": ("video", True),
    "snapprev": ("_clip", False),
    "snapnext": ("_clip", True),
    "extprevzone": ("_selflag", False),
    "extnextzone": ("_selflag", True),
    "extprevclip": ("_selclip", False),
    "extnextclip": ("_selclip", True),
}
# name -> base: base with a diagonal stroke.
SLASHED = {
    "discardrec": "record",
    "cancelzoom": "zoomtoggle",
}
# Short text glyphs, one or two lines. Each family shares one font size.
TEXT = {
    "tl2edit": ["T→E"],
    "edit2tl": ["E→T"],
    "byp_all": ["BYP", "ALL"],
    "byp_ae": ["BYP", "A-E"],
    "byp_fj": ["BYP", "F-J"],
    "byp_eq": ["BYP", "EQ"],
    "byp_dyn": ["BYP", "DYN"],
    "byp_rev": ["BYP", "REV"],
    "byp_dly": ["BYP", "DLY"],
    "byp_mod": ["BYP", "MOD"],
    "snd_all": ["SND", "ALL"],
    "snd_ae": ["SND", "A-E"],
    "snd_fj": ["SND", "F-J"],
    "back5": ["-5"],
    "tabtransients": ["TAB", "TRN"],
    "ahead5": ["+5"],
    "focusedit": ["a-z", "EDIT"],
    "focusclips": ["a-z", "CLIP"],
    "focusgroups": ["a-z", "GRP"],
    "halvesel": ["SEL", "/2"],
    "doublesel": ["SEL", "x2"],
    "removetop": ["SEL", "-TOP"],
    "removebottom": ["SEL", "-BOT"],
    "extendup": ["SEL", "+UP"],
    "extenddown": ["SEL", "+DN"],
}

PX, SS = g.PX, g.SS
U = PX * SS


def _bar(d, x, top, bot, w, cap):
    """A bracket: vertical bar with short serifs pointing ``cap`` (+1 right, -1 left)."""
    d.rectangle([x - w // 2, top, x + w // 2, bot], fill=255)
    s = int(U * 0.12) * cap
    xa, xb = sorted((x, x + s))
    d.rectangle([xa, top, xb, top + w], fill=255)
    d.rectangle([xa, bot - w, xb, bot], fill=255)


def _tri(d, x0, x1, cy, h):
    d.polygon([(x0, cy - h), (x1, cy), (x0, cy + h)], fill=255)


def play_glyph(path: Path, parts: str) -> None:
    """Play triangles and edit-selection brackets left to right: ``>`` is a
    triangle, ``[`` the selection start, ``]`` the selection end."""
    m = Image.new("L", (U, U), 0)
    d = ImageDraw.Draw(m)
    cy, h, w = U // 2, int(U * 0.30), int(U * 0.08)
    tw, bw = int(U * 0.36), int(U * 0.16)
    widths = [tw if c == ">" else bw for c in parts]
    gap = int(U * 0.04)
    x = (U - sum(widths) - gap * (len(parts) - 1)) // 2
    for c, cw in zip(parts, widths):
        if c == ">":
            _tri(d, x, x + cw, cy, h)
        else:
            cap = 1 if c == "[" else -1
            bx = x + w // 2 if c == "[" else x + cw - w // 2
            _bar(d, bx, cy - int(U * 0.38), cy + int(U * 0.38), w, cap)
        x += cw + gap
    g._save_mask(m, path)


def bracket_glyph(path: Path, cap: int) -> None:
    """One tall selection bracket: ``[`` (cap 1) or ``]`` (cap -1)."""
    m = Image.new("L", (U, U), 0)
    d = ImageDraw.Draw(m)
    w = int(U * 0.15)
    x = int(U * 0.35) if cap == 1 else int(U * 0.65)
    s = int(U * 0.22) * cap
    xa, xb = sorted((x, x + s))
    d.rectangle([x - w // 2, int(U * 0.08), x + w // 2, int(U * 0.92)], fill=255)
    d.rectangle([xa, int(U * 0.08), xb, int(U * 0.08) + w], fill=255)
    d.rectangle([xa, int(U * 0.92) - w, xb, int(U * 0.92)], fill=255)
    g._save_mask(m, path)


def ibeam_glyph(path: Path) -> None:
    """The Selector tool's I-beam cursor."""
    m = Image.new("L", (U, U), 0)
    d = ImageDraw.Draw(m)
    w, cx = int(U * 0.09), U // 2
    d.rectangle([cx - w // 2, int(U * 0.12), cx + w // 2, int(U * 0.88)], fill=255)
    for y in (int(U * 0.08), int(U * 0.84)):
        d.rectangle([cx - int(U * 0.20), y, cx - w // 2, y + w], fill=255)
        d.rectangle([cx + w // 2, y, cx + int(U * 0.20), y + w], fill=255)
    g._save_mask(m, path)


def fade_glyph(path: Path, kind: str) -> None:
    """A clip frame with a fade-in ramp, a fade-out ramp or a crossfade X."""
    m = Image.new("L", (U, U), 0)
    d = ImageDraw.Draw(m)
    x0, y0, x1, y1 = int(U * 0.08), int(U * 0.18), int(U * 0.92), int(U * 0.82)
    w = int(U * 0.05)
    d.rectangle([x0, y1 - w, x1, y1], fill=255)
    if kind == "in":
        d.polygon([(x0, y1), (x1, y0), (x1, y1)], fill=255)
    elif kind == "out":
        d.polygon([(x0, y0), (x1, y1), (x0, y1)], fill=255)
    else:
        lw = int(U * 0.08)
        d.line([(x0, y1), (x1, y0)], fill=255, width=lw)
        d.line([(x0, y0), (x1, y1)], fill=255, width=lw)
    g._save_mask(m, path)


def clip_marker(path: Path, where: str, ref: str) -> None:
    """A clip outline with a line at its start, sync point or end, and the
    reference it snaps to above the line: a playhead triangle (``play``) or a
    clock (``tc``, timecode)."""
    m = Image.new("L", (U, U), 0)
    d = ImageDraw.Draw(m)
    x0, x1, y0, y1 = int(U * 0.06), int(U * 0.94), int(U * 0.52), int(U * 0.90)
    w = int(U * 0.05)
    d.rectangle([x0, y0, x1, y1], outline=255, width=w)
    lx = {"start": x0 + w // 2, "sync": U // 2, "end": x1 - w // 2}[where]
    lw = int(U * 0.09)
    d.rectangle([lx - lw // 2, int(U * 0.36), lx + lw // 2, y1], fill=255)
    cx = min(max(lx, int(U * 0.18)), int(U * 0.82))
    if ref == "play":
        h = int(U * 0.15)
        d.polygon([(cx - h, int(U * 0.06)), (cx + h, int(U * 0.06)), (cx, int(U * 0.34))], fill=255)
    else:
        r = int(U * 0.15)
        cyc = int(U * 0.19)
        d.ellipse([cx - r, cyc - r, cx + r, cyc + r], outline=255, width=int(U * 0.045))
        d.line([(cx, cyc), (cx, cyc - int(r * 0.7))], fill=255, width=int(U * 0.035))
        d.line([(cx, cyc), (cx + int(r * 0.55), cyc)], fill=255, width=int(U * 0.035))
    g._save_mask(m, path)


def trim_glyph(path: Path, side: str) -> None:
    """A clip cut at the cursor: the kept part filled, the trimmed part an
    outline, the cursor a heavy line between them."""
    m = Image.new("L", (U, U), 0)
    d = ImageDraw.Draw(m)
    x0, x1, y0, y1 = int(U * 0.06), int(U * 0.94), int(U * 0.30), int(U * 0.74)
    cx = int(U * 0.40) if side == "start" else int(U * 0.60)
    w = int(U * 0.04)
    if side == "start":
        d.rectangle([x0, y0, cx, y1], outline=255, width=w)
        d.rectangle([cx, y0, x1, y1], fill=255)
    else:
        d.rectangle([x0, y0, cx, y1], fill=255)
        d.rectangle([cx, y0, x1, y1], outline=255, width=w)
    lw = int(U * 0.08)
    d.rectangle([cx - lw // 2, int(U * 0.12), cx + lw // 2, int(U * 0.92)], fill=255)
    d.rectangle([cx - lw // 2 - 1, y0 + w, cx + lw // 2 + 1, y1 - w], fill=255)
    g._save_mask(m, path)


def text_glyph(path: Path, lines: list[str], size: int) -> None:
    """One or two short lines of bold text, centred."""
    m = Image.new("L", (U, U), 0)
    d = ImageDraw.Draw(m)
    f = ImageFont.truetype(g.BOLD, size)
    if len(lines) == 1 and "\u2192" in lines[0]:
        # Two letters with a drawn arrow between them: the font's arrow is too
        # small to read at keycap size.
        a, b = lines[0].split("\u2192")
        d.text((int(U * 0.16), U // 2), a, fill=255, font=f, anchor="mm")
        d.text((int(U * 0.84), U // 2), b, fill=255, font=f, anchor="mm")
        t, h = int(U * 0.05), int(U * 0.13)
        x0, x1 = int(U * 0.33), int(U * 0.67)
        d.rectangle([x0, U // 2 - t, x1 - h, U // 2 + t], fill=255)
        d.polygon([(x1, U // 2), (x1 - h, U // 2 - h), (x1 - h, U // 2 + h)], fill=255)
    elif len(lines) == 1:
        d.text((U // 2, U // 2), lines[0], fill=255, font=f, anchor="mm")
    else:
        d.text((U // 2, int(U * 0.27)), lines[0], fill=255, font=f, anchor="mm")
        d.text((U // 2, int(U * 0.75)), lines[1], fill=255, font=f, anchor="mm")
    g._save_mask(m, path)


def _text_size(lines_all: list[list[str]], frac_w: float, frac_h: float) -> int:
    """The largest font size at which every line of the family fits."""
    size = U
    for lines in lines_all:
        for line in lines:
            for s in range(size, 8, -4):
                bb = ImageFont.truetype(g.BOLD, s).getbbox(line)
                if bb[2] - bb[0] <= U * frac_w and bb[3] - bb[1] <= U * frac_h / len(lines):
                    size = min(size, s)
                    break
    return size


PROTOOLS_ICON_URL = ("https://raw.githubusercontent.com/simple-icons/simple-icons/"
                     "develop/icons/protools.svg")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(ICONS, out)
    icon_fetch.borrow(BORROW, out)

    def p(name: str) -> Path:
        return out / f"{name}.png"

    for name, cap in {"_lbr": 1, "_rbr": -1}.items():
        g.guarded(p(name), lambda q, c=cap: bracket_glyph(q, c), "drawn bracket")
    for name, (base, badge) in BADGE.items():
        g.guarded(p(name), lambda q, b=base, k=badge: g.with_badge(p(b), p(k), q),
                  f"{base} + {badge}")
    for name, (base, fwd) in ARROW.items():
        g.guarded(p(name), lambda q, b=base, f=fwd: g.with_arrow(p(b), q, f),
                  f"{base} + arrow")
    for name, base in SLASHED.items():
        g.guarded(p(name), lambda q, b=base: g.slashed(p(b), q), f"{base} slashed")
    g.guarded(p("shrinkend"),
              lambda q: Image.open(p("shrinkstart")).transpose(Image.FLIP_LEFT_RIGHT).save(q),
              "shrinkstart mirrored")

    for name, parts in {"play_to_start": ">[", "play_from_start": "[>",
                        "play_to_end": ">]", "play_from_end": "]>",
                        "play_thru_start": ">[>", "play_thru_end": ">]>"}.items():
        g.guarded(p(name), lambda q, s=parts: play_glyph(q, s), f"drawn {parts}")
    for name, kind in {"fadein": "in", "fadeout": "out", "xfade": "x"}.items():
        g.guarded(p(name), lambda q, k=kind: fade_glyph(q, k), f"drawn fade {kind}")
    for where in ("start", "sync", "end"):
        for ref in ("play", "tc"):
            g.guarded(p(f"clip{where}_{ref}"),
                      lambda q, w=where, r=ref: clip_marker(q, w, r), f"drawn clip {where}/{ref}")
    g.guarded(p("select"), ibeam_glyph, "drawn I-beam")
    for side in ("start", "end"):
        g.guarded(p(f"trim{side}"), lambda q, s=side: trim_glyph(q, s), f"drawn trim {side}")

    # One font size per family: the arrow pair, the +/-5 pair, the two-line set.
    arrows = [v for v in TEXT.values() if len(v) == 1 and "\u2192" in v[0]]
    one = [v for v in TEXT.values() if len(v) == 1 and "\u2192" not in v[0]]
    two = [v for v in TEXT.values() if len(v) == 2]
    sa = _text_size([[c] for v in arrows for c in v[0].split("\u2192")], 0.30, 0.62)
    s1, s2 = _text_size(one, 0.96, 0.62), _text_size(two, 0.96, 0.84)
    for name, lines in TEXT.items():
        size = s2 if len(lines) == 2 else (sa if "\u2192" in lines[0] else s1)
        g.guarded(p(name), lambda q, ln=lines, z=size: text_glyph(q, ln, z),
                  "text " + "/".join(lines))

    if not all(p(f"zoom{d}").exists() for d in "12345"):
        number_badge.numbered(p("zoomer"), "12345", out, "zoom",
                              size=0.30, centre=(0.40, 0.40))

    g.guarded(out / "protools.png",
              lambda q: g.trace_mark(g.svg_icon(PROTOOLS_ICON_URL), q, luma=160, lit="dark"),
              "simple-icons/protools (CC0), 32x32 trace")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
