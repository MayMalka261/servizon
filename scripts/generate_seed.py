"""Generate realistic synthetic seed data for the four canonical tables.

The output stands in for the production tables during development. It is
deliberately *not* flat random: contact volume follows a daily arrival curve and
a weekly pattern (Sunday-Thursday are the working week in Israel), staffing
tracks demand imperfectly, and each center has its own scale and character.
That realism matters — a simulation engine tuned against uniform noise produces
KPI movements nobody in an operations room would believe.

Run:  python scripts/generate_seed.py [--days 90] [--seed 20260728]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = PROJECT_ROOT / "backend" / "data" / "seed"

# Reuse the application's queueing model rather than reimplementing it here.
# Generating history from the same physics the engine assumes is what keeps the
# fitted baselines coherent — otherwise the ETL spends its time reconciling
# data that no real service center could have produced.
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from app.simulation.erlang import abandonment_rate, solve_queue  # noqa: E402

BUCKET_MINUTES = 30
BUCKETS_PER_DAY = 24 * 60 // BUCKET_MINUTES

DIGITAL_CHANNELS = ("web", "whatsapp", "email", "forms", "chat")
ALL_CHANNELS = ("phone", *DIGITAL_CHANNELS)

# (id, name, type, district, headcount, hours/day, daily contacts, digital share)
CENTER_BLUEPRINTS: tuple[tuple[str, str, str, str, int, float, int, float], ...] = (
    ("SC-101", "מוקד תמיכה טכנית ארצי", "technical_support", "hq", 120, 24.0, 9800, 0.50),
    ("SC-102", "מוקד כוח אדם – מרכז", "personnel", "center", 85, 12.0, 6200, 0.44),
    ("SC-103", "מוקד לוגיסטיקה צפון", "logistics", "north", 46, 10.0, 2900, 0.38),
    ("SC-104", "מוקד רפואה ארצי", "medical", "hq", 96, 24.0, 7400, 0.29),
    ("SC-105", "מוקד פניות כלליות דרום", "general_inquiries", "south", 38, 10.0, 2400, 0.55),
    ("SC-106", "מוקד תמיכה טכנית צפון", "technical_support", "north", 52, 12.0, 3600, 0.47),
    ("SC-107", "מוקד כוח אדם ירושלים", "personnel", "jerusalem", 29, 9.0, 1750, 0.41),
    ("SC-108", "מוקד לוגיסטיקה דרום", "logistics", "south", 61, 12.0, 3900, 0.34),
    ("SC-109", "מוקד רפואה מרכז", "medical", "center", 44, 16.0, 3100, 0.26),
    ("SC-110", "מוקד פניות כלליות צפון", "general_inquiries", "north", 22, 9.0, 1300, 0.58),
    ("SC-111", "מוקד תמיכה טכנית דרום", "technical_support", "south", 67, 16.0, 4800, 0.45),
    ("SC-112", "מוקד כוח אדם צפון", "personnel", "north", 33, 10.0, 2050, 0.39),
    ("SC-113", "מוקד לוגיסטיקה מרכז", "logistics", "center", 78, 14.0, 5100, 0.36),
    ("SC-114", "מוקד רפואה דרום", "medical", "south", 31, 12.0, 2150, 0.24),
    ("SC-115", "מוקד פניות כלליות מרכז", "general_inquiries", "center", 54, 12.0, 3450, 0.53),
    ("SC-116", "מוקד תמיכה טכנית ירושלים", "technical_support", "jerusalem", 26, 9.0, 1600, 0.49),
    ("SC-117", "מוקד לוגיסטיקה מטכ\"ל", "logistics", "hq", 41, 12.0, 2700, 0.32),
    ("SC-118", "מוקד כוח אדם דרום", "personnel", "south", 19, 9.0, 1100, 0.42),
    ("SC-119", "מוקד רפואה צפון", "medical", "north", 24, 12.0, 1500, 0.27),
    ("SC-120", "מוקד פניות כלליות ירושלים", "general_inquiries", "jerusalem", 16, 8.0, 880, 0.56),
)

#: Baseline AHT in seconds per center type — medical and technical calls run long.
AHT_BY_TYPE: dict[str, float] = {
    "technical_support": 410.0,
    "personnel": 300.0,
    "logistics": 265.0,
    "medical": 480.0,
    "general_inquiries": 215.0,
}

#: Baseline first-contact resolution per center type.
FCR_BY_TYPE: dict[str, float] = {
    "technical_support": 0.68,
    "personnel": 0.74,
    "logistics": 0.79,
    "medical": 0.62,
    "general_inquiries": 0.83,
}

#: Staffing generosity per center, as the beta of the square-root staffing rule
#: (Halfin-Whitt):  agents = traffic + beta * sqrt(traffic).
#:
#: A flat multiple of traffic is the wrong shape and produces a fleet where
#: every large center sits at 100% SLA and every small one collapses: the
#: buffer a queue needs grows with the *square root* of its load, not in
#: proportion to it. Beta is the dimensionless quality knob that works at any
#: center size — roughly, 1.8 is comfortable, 1.0 is tight, 0.5 is underwater.
#:
#: The spread across the fleet is deliberate. A tool for deciding where to move
#: capacity is worthless if every center is already fine.
STAFFING_BETA_BY_CENTER: dict[str, float] = {
    # Comfortable
    "SC-101": 1.80, "SC-104": 1.70, "SC-107": 1.90, "SC-110": 2.00,
    "SC-113": 1.75, "SC-115": 1.85, "SC-117": 1.80, "SC-120": 1.95,
    # Under pressure
    "SC-102": 1.05, "SC-106": 1.00, "SC-109": 1.10, "SC-112": 0.95,
    "SC-116": 1.05, "SC-118": 1.00,
    # Struggling. Not catastrophic: a center genuinely running at 10% SLA for a
    # month would have been escalated long before anyone opened this tool.
    # These sit where a real problem site sits — bad enough to demand a
    # decision, plausible enough to be believed.
    "SC-103": 0.82, "SC-108": 0.75, "SC-111": 0.70, "SC-114": 0.85,
    "SC-105": 0.78, "SC-119": 0.90,
}

#: Minimum bodies on shift regardless of demand — nobody runs a center at 0.4
#: of a person during the quiet hours.
MIN_AGENTS_ON_SHIFT = 2.0


def arrival_curve(hours_per_day: float) -> np.ndarray:
    """Share of a day's contacts landing in each half-hour bucket.

    A twin-peaked profile — a late-morning peak and a smaller afternoon one —
    which is what service centers actually see. Centers that do not run 24/7
    get a window centred on the working day and zero elsewhere.
    """
    centres = np.arange(BUCKETS_PER_DAY) * (BUCKET_MINUTES / 60.0)

    if hours_per_day >= 24:
        open_from, open_to = 0.0, 24.0
        # Round the clock still has a pronounced day shape, plus a night floor.
        floor = 0.18
    else:
        open_from = 8.0
        open_to = min(24.0, 8.0 + hours_per_day)
        floor = 0.0

    morning = np.exp(-((centres - 10.5) ** 2) / (2 * 2.1**2))
    afternoon = 0.62 * np.exp(-((centres - 15.0) ** 2) / (2 * 2.6**2))
    shape = morning + afternoon + floor

    open_mask = (centres >= open_from) & (centres < open_to)
    shape = np.where(open_mask, shape, 0.0)

    total = shape.sum()
    if total <= 0:  # pragma: no cover - guarded by the blueprint hours
        raise ValueError("arrival curve collapsed to zero")
    return shape / total


def weekday_factor(day: datetime) -> float:
    """Israeli working week: Sunday(6)-Thursday(3) busy, Friday/Saturday quiet."""
    weekday = day.weekday()  # Mon=0 .. Sun=6
    return {
        6: 1.12,  # Sunday — start-of-week backlog
        0: 1.06,  # Monday
        1: 1.02,  # Tuesday
        2: 0.99,  # Wednesday
        3: 0.94,  # Thursday
        4: 0.42,  # Friday
        5: 0.30,  # Saturday
    }[weekday]


def build_centers() -> pd.DataFrame:
    rows = []
    for center_id, name, ctype, district, headcount, hours, daily, _digital in CENTER_BLUEPRINTS:
        rows.append(
            {
                "center_id": center_id,
                "center_name": name,
                "center_type": ctype,
                "district": district,
                # Status is recomputed from live KPIs during ETL; this column is
                # the source system's own flag and only marks hard outages.
                "status": "active",
                "headcount": headcount,
                "working_hours_per_day": hours,
            }
        )
    return pd.DataFrame(rows)


def build_channels(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for center_id, _name, ctype, _district, _hc, _hours, _daily, digital in CENTER_BLUEPRINTS:
        # Technical centers invest more in self-service; medical far less.
        maturity = {
            "technical_support": 1.15,
            "general_inquiries": 1.10,
            "personnel": 1.0,
            "logistics": 0.92,
            "medical": 0.78,
        }[ctype]

        for channel in ALL_CHANNELS:
            is_digital = channel != "phone"
            enabled = True
            if channel in ("forms", "chat"):
                # Not every center has rolled these out yet.
                enabled = bool(rng.random() < 0.75)

            if is_digital:
                self_service = float(np.clip(0.34 * maturity + rng.normal(0, 0.05), 0.05, 0.9))
                automation = float(np.clip(0.28 * maturity + rng.normal(0, 0.05), 0.02, 0.85))
                customer_ai = float(np.clip(0.30 * maturity + rng.normal(0, 0.06), 0.02, 0.8))
            else:
                self_service = float(np.clip(0.11 * maturity + rng.normal(0, 0.03), 0.0, 0.4))
                automation = float(np.clip(0.14 * maturity + rng.normal(0, 0.03), 0.0, 0.5))
                customer_ai = float(np.clip(0.16 * maturity + rng.normal(0, 0.04), 0.0, 0.5))

            rows.append(
                {
                    "center_id": center_id,
                    "channel": channel,
                    "enabled": enabled,
                    "self_service_rate": round(self_service, 4),
                    "automation_level": round(automation, 4),
                    "agent_ai_usage": round(
                        float(np.clip(0.27 * maturity + rng.normal(0, 0.05), 0.02, 0.85)), 4
                    ),
                    "customer_ai_usage": round(customer_ai, 4),
                    "knowledge_base_quality": round(
                        float(np.clip(0.58 * maturity + rng.normal(0, 0.06), 0.15, 0.95)), 4
                    ),
                }
            )
    return pd.DataFrame(rows)


def build_facts(
    rng: np.random.Generator, days: int, channels: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate the interactions and staffing fact tables together.

    They are built in one pass because staffing has to respond to the same
    demand curve the interactions follow — otherwise the derived KPIs come out
    nonsensical.
    """
    end = datetime.now().replace(minute=0, second=0, microsecond=0)
    start_day = (end - timedelta(days=days)).replace(hour=0)

    enabled_lookup = {
        (row.center_id, row.channel): row.enabled for row in channels.itertuples(index=False)
    }

    interaction_rows: list[dict[str, object]] = []
    staffing_rows: list[dict[str, object]] = []

    for center_id, _name, ctype, _district, headcount, hours, daily, digital in CENTER_BLUEPRINTS:
        curve = arrival_curve(hours)
        base_aht = AHT_BY_TYPE[ctype]
        base_fcr = FCR_BY_TYPE[ctype]
        sla_target_sec = 60.0 if ctype in ("medical", "technical_support") else 90.0
        staffing_beta = STAFFING_BETA_BY_CENTER.get(center_id, 1.20)

        active_digital = [c for c in DIGITAL_CHANNELS if enabled_lookup.get((center_id, c), False)]
        # Split the digital share across whichever digital channels are live.
        digital_weights = np.array([1.0, 0.85, 0.6, 0.4, 0.55][: len(active_digital)])
        if digital_weights.sum() > 0:
            digital_weights = digital_weights / digital_weights.sum()

        for day_offset in range(days):
            day = start_day + timedelta(days=day_offset)
            # Day-level demand: weekly pattern, a slow upward drift, and noise.
            drift = 1.0 + 0.0009 * day_offset
            day_volume = daily * weekday_factor(day) * drift * rng.normal(1.0, 0.055)
            day_volume = max(day_volume, 0.0)

            for bucket in range(BUCKETS_PER_DAY):
                share = curve[bucket]
                if share <= 0:
                    continue

                ts = day + timedelta(minutes=bucket * BUCKET_MINUTES)
                bucket_total = day_volume * share * rng.normal(1.0, 0.11)
                bucket_total = max(bucket_total, 0.0)

                phone_volume = bucket_total * (1.0 - digital)
                digital_volume = bucket_total * digital

                aht = max(base_aht * rng.normal(1.0, 0.08), 45.0)
                digital_aht = max(base_aht * 0.55, 30.0)

                # -- Staffing for this bucket -----------------------------
                # Rostered against the traffic the bucket actually carries,
                # times the center's staffing factor. Rosters are built in
                # advance from a forecast, so they track the *smoothed* curve
                # and lag it slightly — which is precisely where real service
                # levels break down, and worth reproducing.
                lag = curve[max(bucket - 1, 0)]
                planned_share = 0.72 * share + 0.28 * lag
                planned_total = day_volume * planned_share

                planned_traffic = (
                    planned_total * (1.0 - digital) * 2.0 * aht
                    + planned_total * digital * 2.0 * digital_aht
                ) / 3600.0

                logged_in = planned_traffic + staffing_beta * np.sqrt(max(planned_traffic, 0.0))
                logged_in = max(float(logged_in), MIN_AGENTS_ON_SHIFT)
                logged_in *= rng.normal(1.0, 0.04)
                shrinkage = float(np.clip(rng.normal(0.28, 0.035), 0.12, 0.45))
                scheduled = logged_in / (1.0 - shrinkage)

                staffing_rows.append(
                    {
                        "center_id": center_id,
                        "ts_bucket": ts,
                        "agents_scheduled": round(scheduled, 2),
                        "agents_logged_in": round(logged_in, 2),
                        "shrinkage_pct": round(shrinkage * 100, 2),
                        "sla_target_sec": sla_target_sec,
                    }
                )

                # -- Phone interactions -----------------------------------
                # Waiting time comes out of the queueing model rather than an
                # invented curve, so the history is internally consistent.
                # Digital contacts compete for the same agents, so the phone
                # queue only gets the share of capacity its traffic warrants.
                total_traffic = (
                    phone_volume * 2.0 * aht + digital_volume * 2.0 * digital_aht
                ) / 3600.0
                phone_traffic = phone_volume * 2.0 * aht / 3600.0
                phone_share_of_capacity = (
                    phone_traffic / total_traffic if total_traffic > 0 else 1.0
                )
                phone_agents = max(logged_in * phone_share_of_capacity, 1.0)

                outcome = solve_queue(
                    calls_per_hour=phone_volume * 2.0,
                    aht_sec=aht,
                    agents=phone_agents,
                    sla_target_sec=sla_target_sec,
                )
                wait_sec = min(outcome.asa_sec, 900.0)
                abandon_rate = abandonment_rate(
                    asa_sec=wait_sec,
                    patience_sec=float(np.clip(rng.normal(200.0, 25.0), 90.0, 320.0)),
                )

                offered = phone_volume
                abandoned = offered * abandon_rate
                handled = max(offered - abandoned, 0.0)
                fcr = float(
                    np.clip(
                        base_fcr * rng.normal(1.0, 0.04) - 0.10 * outcome.occupancy,
                        0.25,
                        0.97,
                    )
                )

                interaction_rows.append(
                    {
                        "center_id": center_id,
                        "ts_bucket": ts,
                        "channel": "phone",
                        "offered": round(offered, 2),
                        "handled": round(handled, 2),
                        "abandoned": round(abandoned, 2),
                        "aht_sec": round(aht, 1),
                        "wait_sec": round(wait_sec, 1),
                        "resolved_first_contact": round(handled * fcr, 2),
                    }
                )

                # -- Digital interactions ---------------------------------
                for idx, channel in enumerate(active_digital):
                    ch_offered = digital_volume * float(digital_weights[idx])
                    if ch_offered <= 0:
                        continue
                    # Asynchronous channels are cheaper to handle and rarely
                    # abandoned in the queueing sense.
                    ch_aht = max(digital_aht * rng.normal(1.0, 0.1), 30.0)
                    ch_wait = float(np.clip(rng.normal(45.0, 20.0), 2.0, 400.0))
                    ch_abandon = float(np.clip(rng.normal(0.035, 0.015), 0.0, 0.25))
                    ch_abandoned = ch_offered * ch_abandon
                    ch_handled = max(ch_offered - ch_abandoned, 0.0)
                    ch_fcr = float(np.clip(base_fcr * 1.05 * rng.normal(1.0, 0.04), 0.3, 0.98))

                    interaction_rows.append(
                        {
                            "center_id": center_id,
                            "ts_bucket": ts,
                            "channel": channel,
                            "offered": round(ch_offered, 2),
                            "handled": round(ch_handled, 2),
                            "abandoned": round(ch_abandoned, 2),
                            "aht_sec": round(ch_aht, 1),
                            "wait_sec": round(ch_wait, 1),
                            "resolved_first_contact": round(ch_handled * ch_fcr, 2),
                        }
                    )

    return pd.DataFrame(interaction_rows), pd.DataFrame(staffing_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Servizon seed data")
    parser.add_argument("--days", type=int, default=90, help="days of history to generate")
    parser.add_argument("--seed", type=int, default=20260728, help="RNG seed for reproducibility")
    parser.add_argument("--out", type=Path, default=SEED_DIR, help="output directory")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    centers = build_centers()
    channels = build_channels(rng)
    interactions, staffing = build_facts(rng, args.days, channels)

    centers.to_csv(out / "centers.csv", index=False, encoding="utf-8")
    channels.to_csv(out / "channels.csv", index=False, encoding="utf-8")
    interactions.to_csv(out / "interactions.csv", index=False, encoding="utf-8")
    staffing.to_csv(out / "staffing.csv", index=False, encoding="utf-8")

    print(f"centers      {len(centers):>9,} rows -> {out / 'centers.csv'}")
    print(f"channels     {len(channels):>9,} rows -> {out / 'channels.csv'}")
    print(f"interactions {len(interactions):>9,} rows -> {out / 'interactions.csv'}")
    print(f"staffing     {len(staffing):>9,} rows -> {out / 'staffing.csv'}")


if __name__ == "__main__":
    main()
