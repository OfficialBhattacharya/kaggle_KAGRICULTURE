# ---- price-floor / pre-crash herd liquidation layer -------------------------
# Appended after the base agent. Captures the previous entry point as its host,
# adjusts only the market list, and returns the host's action unchanged on any
# error or non-standard configuration.
#
# Why this exists (measured over 14 live replays of submission 56334431):
#   * Wool falls from ~$215 to $1 between day 14 and day 15 in every game and
#     never recovers; milk follows within two days. Roughly 58 surplus units
#     floor wool, and two agents each running ~6 sheep saturate that in days.
#   * The tape keeps selling into the floored market: 71% of our wool units went
#     out after the price hit $1, realising an average $33 against a $200 base.
#     Milk averaged $56 against $160.
#   * 5 of 7 live losses were against EXACT mirrors of our own planting plan, so
#     the opponent carries the same collapsing inventory. Whoever converts the
#     herd before the crash keeps the value.
#
# Two independent mechanisms, each separately switchable:
#   FLOOR  - stop spending market-order slots on items trading below a fraction
#            of base. Slots are capped at 10/turn; a $1 wool order displaces a
#            crop order worth 1.3-1.7x base. Yields when the shed is under
#            pressure, because overflow is destroyed at end of day.
#   EARLY  - while an animal product is still near base, sell held stock ahead
#            of the tape's own schedule, capped per turn so we do not crash the
#            price ourselves.
_PF_HOST = [v for v in list(globals().values()) if callable(v)][-1]

_PF_FLOOR = True
_PF_EARLY = True
_PF_FLOOR_FRAC = 0.25        # skip SELL below this fraction of base price
_PF_EARLY_FRAC = 0.85        # only pre-sell while price is at least this
_PF_EARLY_FROM = 96          # day 4; herd output is meaningful by then
_PF_EARLY_TO = 360           # day 15; the crash has happened by here
_PF_EARLY_MAX = 8            # units per item per turn, to avoid self-crashing
_PF_SHED_PRESSURE = 80       # above this many shed units, never withhold a sale
_PF_LAST_STEP = 700          # leave the terminal liquidation alone
_PF_FLOOR_ITEMS = ('WOOL', 'MILK', 'FERTILIZER', 'MELON')
_PF_EARLY_ITEMS = ('WOOL', 'MILK')
_PF_BASE = {'WHEAT': 25, 'CARROT': 35, 'TOMATO': 60, 'STRAWBERRY': 120,
            'MELON': 250, 'EGG': 50, 'MILK': 160, 'WOOL': 200, 'FERTILIZER': 100}
_PF_REPORT = dict(floor_skips=0, floor_units=0, early_turns=0, early_units=0, errors=0)


def _pf_shed_total(obs):
    try:
        return sum(int(v) for v in (obs['private']['shed'] or {}).values())
    except Exception:
        return 0


def _pf_adjust(obs, action):
    step = int(obs['step'])
    if step >= _PF_LAST_STEP:
        return action
    prices = obs['market']['prices']
    market = [list(o) for o in (action.get('market') or []) if o]
    shed = obs['private']['shed'] or {}
    pressure = _pf_shed_total(obs)

    # Never withhold anything once the shed is close to the cap: unsold overflow
    # is destroyed at the end of the day, which costs more than a bad price.
    if _PF_FLOOR and pressure < _PF_SHED_PRESSURE:
        kept = []
        for o in market:
            if (len(o) >= 3 and o[0] == 'SELL' and o[1] in _PF_FLOOR_ITEMS
                    and int(prices.get(o[1], 0)) < _PF_FLOOR_FRAC * _PF_BASE.get(o[1], 1)):
                _PF_REPORT['floor_skips'] += 1
                _PF_REPORT['floor_units'] += int(o[2])
                continue
            kept.append(o)
        market = kept

    if _PF_EARLY and _PF_EARLY_FROM <= step < _PF_EARLY_TO and len(market) < 10:
        already = {}
        for o in market:
            if len(o) >= 3 and o[0] == 'SELL':
                already[o[1]] = already.get(o[1], 0) + int(o[2])
        # a BUY_PRODUCT order in the same list means the tape is funding something
        # this turn; adding sales ahead of it changes its fill, so abstain
        if not any(len(o) > 1 and o[0] == 'BUY_PRODUCT' for o in market):
            added = 0
            for item in _PF_EARLY_ITEMS:
                if len(market) >= 10:
                    break
                price = int(prices.get(item, 0))
                if price < _PF_EARLY_FRAC * _PF_BASE.get(item, 1):
                    continue
                have = int(shed.get(item, 0)) - already.get(item, 0)
                n = min(have, _PF_EARLY_MAX)
                if n < 1:
                    continue
                hit = next((o for o in market
                            if len(o) >= 3 and o[0] == 'SELL' and o[1] == item), None)
                if hit is not None:
                    hit[2] = int(hit[2]) + n
                else:
                    market.insert(0, ['SELL', item, n])
                added += n
            if added:
                _PF_REPORT['early_turns'] += 1
                _PF_REPORT['early_units'] += added

    if market == [list(o) for o in (action.get('market') or []) if o]:
        return action
    return dict(action, market=market)


def price_floor_agent(observation, configuration=None):
    action = _PF_HOST(observation, configuration)
    try:
        standard = configuration is None or all(
            configuration.get(k, v) == v for k, v in
            [('boardSize', 10), ('turnsPerDay', 24), ('shedCapacity', 100),
             ('maxMarketOrdersPerTurn', 10)])
        if standard:
            return _pf_adjust(observation, action)
    except Exception:
        _PF_REPORT['errors'] += 1
    return action


price_floor_agent.telemetry = _PF_REPORT
