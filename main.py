# main.py
import sys
import pygame
from datetime import datetime
from shared.csv_logger import append_trio_row, reconcile_csv_with_state


from scenes.launch import LaunchScene
from shared.persistence import (
    load_all_states,
    save_state,
    archive_or_delete_if_complete,
)
from scenes.km_game import run as run_km
from scenes.jbt_game import run as run_jbt


pygame.init()
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.display.set_caption("KM + JBT")
clock = pygame.time.Clock()


def _advance_progress_after_trio(state):
    """Advance indices after completing one trio (KM + JBT leader + JBT follower)."""
    prog = state["progress"]
    prog["completed_trios"] = int(prog.get("completed_trios", 0)) + 1
    total_done = prog["completed_trios"]  # 1..28 within session

    if total_done >= 28:
        # Session complete
        prog["trio_index"] = 7
        prog["block_index"] = 4
        state["status"] = "complete"
        return

    # Not finished: compute next trio/block for resume
    next_trio = (total_done % 7) + 1       # 1..7
    next_block = (total_done // 7) + 1     # 1..4
    prog["trio_index"] = next_trio
    prog["block_index"] = next_block
    prog["stage"] = "KM"                   # always start next trio at KM


def _roll_to_next_session_if_complete(state):
    """If 28 trios are done, roll to next session (if available) or finish overall."""
    if state.get("status") != "complete":
        return

    sessions_total  = int(state["config"]["sessions_total"])
    current_session = int(state["progress"]["session_index"])

    if current_session < sessions_total:
        # Move to next session
        state["status"] = "incomplete"
        prog = state["progress"]
        prog["session_index"]   = current_session + 1
        prog["block_index"]     = 1
        prog["trio_index"]      = 1
        prog["completed_trios"] = 0
        prog["stage"]           = "KM"

        # Reset per-side JBT decks so each new session starts fresh
        prog.pop("jbt_decks_sides", None)

        # (Optional: legacy—safe to remove if unused)
        prog.pop("last_jbt_label", None)

    else:
        # All sessions for this pair are done
        state["status"] = "complete"


def main():
    load_all_states()

    # Tolerant to both return shapes: (outcome, state) OR just state
    scene = LaunchScene(screen, clock)
    _out = scene.run()
    if isinstance(_out, tuple) and len(_out) == 2:
        outcome, state = _out
    else:
        outcome, state = ("launch", _out)  # assume old API
    if outcome == "quit" or state is None:
        pygame.quit(); sys.exit(0)

    # Reconcile JSON progress with what’s already in the CSV for this pair/session.
    prog = state["progress"]
    csv_done = reconcile_csv_with_state(state)
    mem_done = int(prog.get("completed_trios", 0))

    if csv_done != mem_done:
        # Trust the CSV (rows reflect fully completed trios).
        prog["completed_trios"] = csv_done

        # Recompute trio/block indices from completed_trios (1..7, 1..4)
        # completed_trios = 0 -> next is trio 1, block 1
        next_trio  = (csv_done % 7) + 1          # 1..7
        next_block = (csv_done // 7) + 1         # 1..4 (caps at 4 naturally when csv_done==28)
        prog["trio_index"]  = min(next_trio, 7)
        prog["block_index"] = min(next_block, 4)
        prog["stage"]       = "KM"
    
    # After reconciliation:
    if prog["completed_trios"] >= 28:
        prog["trio_index"] = 7
        prog["block_index"] = 4
        state["status"] = "complete"
        # Immediately roll or finish so you don't try to run another trio:
        _roll_to_next_session_if_complete(state)
        save_state(state)
        if state.get("status") == "complete":
            archive_or_delete_if_complete(state, delete=True)
            pygame.quit(); sys.exit(0)


    running = True
    while running:
        # Also allow closing via window X
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
        pygame.event.clear()

        # 1) KM — capture when KM starts for CSV date/time columns
        km_start_dt = datetime.now()
        km_out = run_km(screen, clock, state)
        if km_out is None:
            break

        # 2) JBT (leader)
        jbt_lead = run_jbt(screen, clock, state, player="leader")
        if jbt_lead is None:
            break

        # 3) JBT (follower)
        jbt_follow = run_jbt(screen, clock, state, player="follower")
        if jbt_follow is None:
            break

        # 3.5) Log one CSV row for this completed trio
        try:
            csv_path = append_trio_row(state, km_start_dt, km_out, jbt_lead, jbt_follow)
            # Optional debug:
            # print(f"[CSV] wrote: {csv_path}")
        except Exception as e:
            # Don't crash the session on CSV errors; surface to console for now
            print("CSV log error:", e)

        # 4) Advance/save
        _advance_progress_after_trio(state)
        save_state(state)

        # If a full session (28 trios) is done, roll or finish
        if state.get("status") == "complete":
            _roll_to_next_session_if_complete(state)
            save_state(state)

            if state.get("status") == "complete":
                archive_or_delete_if_complete(state, delete=True)
                running = False

        clock.tick(60)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
