# shared/stimuli.py
import random

JBT_STIM_SET = ["S+", "S+", "S-", "S-", "NP", "INT", "NG"]

def next_block(seed=None):
    """Return a shuffled 7-pack with the required ratio."""
    pack = JBT_STIM_SET[:]
    rnd = random.Random(seed)
    rnd.shuffle(pack)
    return pack

def get_current_stimulus(state):
    """Return the stimulus for the next JBT (leader) given state; track within blocks."""
    prog = state["progress"]
    # Ensure we have a block & index tracked:
    if "jbt_block" not in prog or "jbt_index" not in prog or prog["jbt_index"] >= 7:
        prog["jbt_block"] = next_block(seed=prog["session_index"] * 1000 + prog["block_index"])
        prog["jbt_index"] = 0
    stim = prog["jbt_block"][prog["jbt_index"]]
    prog["jbt_index"] += 1
    return stim
