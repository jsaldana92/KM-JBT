# shared/persistence.py
import os, json
from datetime import datetime

STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "state", "KM_JBT")
ARCHIVE_DIR = os.path.join(STATE_DIR, "archive")
os.makedirs(STATE_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

INCOMPLETE = {}  # uid -> state dict


def make_uid(leader, follower, stimuli, sessions_total, version="v1"):
    return f"KMJBT_{version}__Leader-{leader}__Follower-{follower}__Stim-{stimuli}__Sessions-{int(sessions_total)}"


def state_path(uid):
    return os.path.join(STATE_DIR, f"{uid}.json")


def save_state(state):
    state.setdefault("progress", {})
    state["progress"]["last_saved_iso"] = datetime.now().isoformat(timespec="seconds")
    tmp = state_path(state["uid"]) + ".tmp"
    final = state_path(state["uid"])
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, final)


def load_all_states():
    INCOMPLETE.clear()
    if not os.path.isdir(STATE_DIR):
        return INCOMPLETE
    for name in os.listdir(STATE_DIR):
        if not name.endswith(".json"):
            continue
        p = os.path.join(STATE_DIR, name)
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("status") != "complete":
                INCOMPLETE[data["uid"]] = data
        except Exception:
            # skip corrupted/unreadable file
            pass
    return INCOMPLETE


def new_or_resume_state(uid, config):
    """Open existing state if it exists; otherwise create a new one."""
    p = state_path(uid)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f), True
    state = {
        "version": 1,
        "uid": uid,
        "status": "incomplete",
        "config": {
            "leader": config["leader"],
            "follower": config["follower"],
            "stimuli": config["stimuli"],
            "sessions_total": int(config["sessions_total"]),
        },
        "progress": {
            "session_index": 1,
            "block_index": 1,
            "trio_index": 1,
            "stage": "KM",
            "completed_trios": 0,
            "last_saved_iso": datetime.now().isoformat(timespec="seconds"),
        },
    }
    save_state(state)
    return state, False


def set_next_trial(state, session_index, next_trial):  # 1..28
    next_trial = max(1, min(28, int(next_trial)))
    block_index = ((next_trial - 1) // 7) + 1
    trio_index = ((next_trial - 1) % 7) + 1
    state["progress"]["session_index"] = int(session_index)
    state["progress"]["block_index"] = block_index
    state["progress"]["trio_index"] = trio_index
    state["progress"]["completed_trios"] = next_trial - 1
    state["progress"]["stage"] = "KM"


def archive_or_delete_if_complete(state, delete=True):
    if state.get("status") != "complete":
        return
    src = state_path(state["uid"])
    if delete:
        try:
            os.remove(src)
        except FileNotFoundError:
            pass
    else:
        dst = os.path.join(ARCHIVE_DIR, os.path.basename(src))
        try:
            os.replace(src, dst)
        except FileNotFoundError:
            pass


def ensure_fake_incomplete_examples():
    """Dev helper: create a couple of JSON files if there are none, then reload."""
    if INCOMPLETE:
        return
    samples = [
        dict(leader="Ira", follower="Irene", stimuli="Dark S+",  sessions_total=6, session_index=1, next_trial=11),
        dict(leader="Paddy", follower="Ingrid", stimuli="Light S+", sessions_total=6, session_index=3, next_trial=16),
    ]
    for s in samples:
        uid = make_uid(s["leader"], s["follower"], s["stimuli"], s["sessions_total"])
        st = {
            "version": 1,
            "uid": uid,
            "status": "incomplete",
            "config": {
                "leader": s["leader"],
                "follower": s["follower"],
                "stimuli": s["stimuli"],
                "sessions_total": s["sessions_total"],
            },
            "progress": {
                "session_index": s["session_index"],
                "block_index": ((s["next_trial"] - 1) // 7) + 1,
                "trio_index": ((s["next_trial"] - 1) % 7) + 1,
                "stage": "KM",
                "completed_trios": s["next_trial"] - 1,
                "last_saved_iso": datetime.now().isoformat(timespec="seconds"),
            },
        }
        save_state(st)
    load_all_states()

# --- Trio/session progression helpers ---

def current_trio_number(state) -> int:
    """1..28 within the current session."""
    # completed_trios is total within the session
    return int(state["progress"].get("completed_trios", 0)) + 1

def advance_after_trio(state):
    """
    Move to the next trio in the session, then next block, then next session.
    Marks 'complete' when all sessions done.
    """
    p = state["progress"]
    cfg = state["config"]

    # bump completed trios
    p["completed_trios"] = int(p.get("completed_trios", 0)) + 1

    # advance trio index within a block of 7
    if p["trio_index"] < 7:
        p["trio_index"] += 1
    else:
        # next block
        p["trio_index"] = 1
        if p["block_index"] < 4:
            p["block_index"] += 1
        else:
            # next session
            p["block_index"] = 1
            p["session_index"] += 1
            p["completed_trios"] = 0  # reset per session

            # done with all sessions?
            if p["session_index"] > int(cfg["sessions_total"]):
                state["status"] = "complete"

    # always reset stage to KM for the next trio
    p["stage"] = "KM"

import random

_JBT_BLOCK_TEMPLATE = ["S+", "S+", "S-", "S-", "NP", "INT", "NG"]

def _ensure_block_schedule(state):
    """
    Ensure we have a randomized schedule for each block in the current session.
    Stored under progress["_stim_blocks"][str(session_index)][str(block_index)] = list of 7 labels
    """
    p = state["progress"]
    sess = str(p["session_index"])
    blk  = str(p["block_index"])

    if "_stim_blocks" not in p:
        p["_stim_blocks"] = {}

    if sess not in p["_stim_blocks"]:
        p["_stim_blocks"][sess] = {}

    if blk not in p["_stim_blocks"][sess]:
        block = _JBT_BLOCK_TEMPLATE[:]
        random.shuffle(block)  # simple shuffle; change if you want extra constraints
        p["_stim_blocks"][sess][blk] = block

def get_current_jbt_stimulus(state) -> str:
    """
    Returns the scheduled JBT stimulus label ("S+","S-","NP","INT","NG") for the current trio.
    """
    _ensure_block_schedule(state)
    p = state["progress"]
    sess = str(p["session_index"]); blk = str(p["block_index"])
    trio_idx_1based = int(p["trio_index"])
    # guard
    trio_idx_1based = max(1, min(7, trio_idx_1based))
    return p["_stim_blocks"][sess][blk][trio_idx_1based - 1]
