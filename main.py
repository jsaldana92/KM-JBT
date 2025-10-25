# main.py
import sys
import pygame

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

    sessions_total = int(state["config"]["sessions_total"])
    current_session = int(state["progress"]["session_index"])

    if current_session < sessions_total:
        # Move to next session
        state["status"] = "incomplete"
        state["progress"]["session_index"] = current_session + 1
        state["progress"]["block_index"] = 1
        state["progress"]["trio_index"] = 1
        state["progress"]["completed_trios"] = 0
        state["progress"]["stage"] = "KM"
        # optional: clear last_jbt_label for a fresh start in the new session
        state["progress"].pop("last_jbt_label", None)
    else:
        # All sessions for this pair are done
        state["status"] = "complete"


# ---- JBT stimulus scheduler ----
TRIO_ORDER = ["S+", "S-", "NP", "NN", "INT", "S+", "S-"]

def _next_jbt_label(state):
    """
    Decide which JBT label to use for the current trio.
    Uses a fixed 7-trio order and avoids same-label carry-over across blocks.
    """
    prog = state["progress"]
    # Use recorded trio_index when present; otherwise derive from completed_trios.
    trio_idx = int(prog.get("trio_index") or ((int(prog.get("completed_trios", 0)) % 7) + 1))
    label = TRIO_ORDER[trio_idx - 1]

    # Avoid same-label carry-over across blocks:
    # If this is the first trio in a block and it's the same as the last label used,
    # bump to the second label in the order.
    if trio_idx == 1 and prog.get("last_jbt_label") == label:
        label = TRIO_ORDER[1]
    return label


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

    running = True
    while running:
        # Also allow closing via window X
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
        pygame.event.clear()

        # 1) KM
        km_out = run_km(screen, clock, state)
        if km_out is None:
            break

        # Decide the JBT stimulus label for this trio (same label for both players)
        jbt_label = _next_jbt_label(state)   # "S+", "S-", "NP", "NN", or "INT"

        # 2) JBT (leader)
        jbt_lead = run_jbt(screen, clock, state, player="leader", stimulus_label=jbt_label)
        if jbt_lead is None:
            break

        # 3) JBT (follower) — same stimulus label as leader
        jbt_follow = run_jbt(screen, clock, state, player="follower", stimulus_label=jbt_label)
        if jbt_follow is None:
            break

        # Remember which label we used this trio so the next block won't repeat it in trio #1
        state["progress"]["last_jbt_label"] = jbt_label

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
