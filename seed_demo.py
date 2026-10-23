"""Seed the demo scenario into the crew memory store.

A fictional household (all data synthetic, invented for this demo): the
crew has been helping the Alvarez family for a few weeks, so the memory
already holds facts, a procedure, an episode, and one open handoff when
the demo starts. Seeding writes through the same MemoryService the MCP
tools use — it is setup, not part of the demoed flow.

Usage: python seed_demo.py [--db crew_memory.db] [--reset]
"""
from __future__ import annotations

import argparse
import os

from crew_brain import CrewBrain
from crew_memory.memory import MemoryService
from crew_memory.sqlite_backend import SQLiteBackend


def seed(brain: CrewBrain) -> dict:
    out = {}
    r = brain.remember(
        "researcher",
        "Maya is allergic to peanuts and needs peanut-free snacks.",
        about=["Maya"])
    out["allergy_fact"] = r["stored"]
    brain.remember(
        "researcher",
        "The household eats vegetarian meals on weekdays.",
        about=["Household"])
    brain.remember(
        "researcher",
        "Maya has soccer practice on Tuesdays and Thursdays at 5 pm.",
        about=["Maya", "Soccer"])
    brain.remember(
        "researcher",
        "Grandma Rosa visits on the last Sunday of every month and loves "
        "mango sticky rice.",
        about=["Rosa"])
    brain.remember(
        "researcher",
        "The family car is due for an oil change at 45,000 miles.",
        about=["Car"])
    brain.remember_procedure(
        "planner", "School morning routine",
        ["Wake Maya at 6:30 am", "Pack a peanut-free lunchbox",
         "Check the soccer bag on Tuesdays and Thursdays",
         "Leave by 7:15 am to beat traffic"],
        trigger="school mornings")
    brain.mem.log_episode(
        "executor", brain._session("executor"), "shopping",
        "Executor restocked oat milk, rice, and mango for the week.")
    h = brain.handoff(
        "planner", "executor",
        "Restock the pantry before Rosa's visit on Sunday; keep everything "
        "peanut-free and weekday-vegetarian.",
        references=[out["allergy_fact"]],
        question="Anything on the list that conflicts with the allergy or "
                 "vegetarian rules?")
    out["open_handoff"] = h["handoff"]
    out["stats"] = brain.stats()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("CREW_MEMORY_DB",
                                                   "crew_memory.db"))
    ap.add_argument("--reset", action="store_true",
                    help="clear the store before seeding")
    args = ap.parse_args()
    backend = SQLiteBackend(args.db)
    if args.reset:
        backend.clear()
    brain = CrewBrain(MemoryService(backend))
    result = seed(brain)
    print("Seeded demo scenario:")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
