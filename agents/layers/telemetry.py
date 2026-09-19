# ---- diagnostic layer: dump internal counters at the end of the game --------
# Appended last. Because it lives in the same module namespace as everything
# below it, it can read the base agent's own report dicts directly.
#
# Exists because a sweep that returns margin == 0 in every game is ambiguous:
# the parameter may genuinely not matter, or the code path may never execute.
# Those need completely different responses, and only the counters separate them.
_TEL_HOST = [v for v in list(globals().values()) if callable(v)][-1]
_TEL_PATH = "/kaggle/working/telemetry.json"
_TEL_DONE = {}


def _tel_dump(obs):
    import json as _json
    snap = {}
    for name in ("_ADV_REPORT", "_PF_REPORT", "_RACE_REPORT", "_R37_STATS",
                 "_OPEN_REPORT", "_PG_REPORT", "_V44Y_REPORT", "_R44_REPORT"):
        val = globals().get(name)
        if isinstance(val, dict):
            snap[name] = dict(val)
    snap["_step"] = int(obs.get("step", -1))
    snap["_player"] = int(obs.get("player", -1))
    try:
        with open(_TEL_PATH, "a") as fh:
            fh.write(_json.dumps(snap) + "\n")
    except Exception:
        pass


def telemetry_agent(observation, configuration=None):
    action = _TEL_HOST(observation, configuration)
    try:
        step = int(observation.get("step", 0))
        player = int(observation.get("player", 0))
        if step >= 718 and not _TEL_DONE.get(player):
            _TEL_DONE[player] = True
            _tel_dump(observation)
    except Exception:
        pass
    return action
