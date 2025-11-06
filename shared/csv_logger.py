# shared/csv_logger.py
import os, csv

def _csv_dir_for_state(state):
    # This file is <project_root>/shared/csv_logger.py, so one up is the root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.makedirs(project_root, exist_ok=True)  # harmless if it already exists
    return project_root

def _csv_filename_for_state(state):
    leader   = state["config"]["leader"]
    follower = state["config"]["follower"]
    sess     = int(state["progress"]["session_index"])
    return f"KM-JBT_{leader}-{follower}_S{sess}.csv"

def _csv_path_for_state(state):
    return os.path.join(_csv_dir_for_state(state), _csv_filename_for_state(state))

def reconcile_csv_with_state(state):
    """
    Return the number of *completed trios already on disk* for this pair/session.
    If the CSV doesn't exist, returns 0.
    """
    path = _csv_path_for_state(state)
    if not os.path.exists(path):
        return 0
    n = 0
    with open(path, "r", newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for _ in rdr:
            n += 1
    return n

def append_trio_row(state, km_start_dt, km_out, jbt_lead, jbt_follow):
    csv_path = _csv_path_for_state(state)

    is_new = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow([
                "date","time","stimuli_type","pair","leader_side",
                "leader","follower","session","block","trial",
                "km_paired_choice","km_leader_choice","km_leader_choice_time",
                "km_follower_choice","km_follower_choice_time",
                "jbt_leader_stimuli","jbt_leader_choice","jbt_leader_choice_time",
                "jbt_follower_stimuli","jbt_follower_choice","jbt_follower_choice_time",
            ])

        # --- build row from state + km_out + jbt_* ---
        cfg   = state["config"]
        prog  = state["progress"]
        pair  = f'{cfg["leader"]}-{cfg["follower"]}'
        side  = "Left" if cfg.get("leader") == cfg.get("left_name", cfg["leader"]) else "Right"

        # KM choices and times (prefer *_ms if present; else convert seconds -> ms)
        km_leader_choice        = km_out.get("leader_choice", "")
        km_follower_choice      = km_out.get("follower_choice", "")
        km_paired_choice        = f"{km_leader_choice}{km_follower_choice}"

        leader_time_ms = km_out.get("leader_choice_time_ms")
        if leader_time_ms is None:
            leader_time_ms = int(float(km_out.get("leader_choice_time", 0)) * 1000)

        follower_time_ms = km_out.get("follower_choice_time_ms")
        if follower_time_ms is None:
            follower_time_ms = int(float(km_out.get("follower_choice_time", 0)) * 1000)

        row = [
            km_start_dt.strftime("%Y-%m-%d"),
            km_start_dt.strftime("%H:%M:%S"),
            cfg.get("stimuli", ""),
            pair,
            side,
            cfg["leader"],
            cfg["follower"],
            int(prog.get("session_index", 1)),
            int(prog.get("block_index", 1)),
            int(prog.get("completed_trios", 0)) + 1,  # overall trial = next trio index

            # KM (now in the right order)
            km_paired_choice,
            km_leader_choice,
            int(leader_time_ms),
            km_follower_choice,
            int(follower_time_ms),

            # JBT leader
            jbt_lead.get("stimulus",""),
            1 if jbt_lead.get("collided") else 0,
            int(jbt_lead.get("rt_ms", 0)),

            # JBT follower
            jbt_follow.get("stimulus",""),
            1 if jbt_follow.get("collided") else 0,
            int(jbt_follow.get("rt_ms", 0)),
        ]
        w.writerow(row)

    print("[CSV] wrote:", os.path.abspath(csv_path))
    return csv_path
