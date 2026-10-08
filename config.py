""" Fixed ists used accross the app. Change here them nowwhere here"""

# id stored in database -> labe shown in screen
TYPES ={
    "sofa": "Sofa",
    "armchair": "Armchair",
    "side_table": "Side table",
    "dining_table": "Dining table",
    "dining_chair": "Dining chair",
    "console_table": "Console table",
    "tv_unit": "TV unit",
    "bed": "Bed",
    "bedside_table": "Bedside table",
    "chest_of_drawers": "Chest of drawers",
    "desk": "Desk",
    "desk_chair": "Desk chair",
    "outdoor_sofa": "Outdoor sofa",
    "outdoor_chair": "Outdoor chair",
    "outdoor_table": "Outdoor table",
    "rug": "Rug",
}
LABEL_TO_TYPE = {label: key for key, label in TYPES.items()}

# Every room the app knows about, in the order they are shown.
ROOM_LABELS ={
    "living": "Living Room",
    "living2": "Living Room 2",
    "living3": "Living Room 3",
    "living4": "Living Room 4",
    "dining": "Dining Room",
    "kitchen": "Kitchen",
    "master": "Master Bedroom",
    "bed2": "Bedroom 2", "bed3": "Bedroom 3", "bed4": "Bedroom 4", "bed5": "Bedroom 5",
    "bed6": "Bedroom 6", "bed7": "Bedroom 7", "bed8": "Bedroom 8", "bed9": "Bedroom 9",
    "bed10": "Bedroom 10", "bed11": "Bedroom 11", "bed12": "Bedroom 12",
    "study": "Study",
    "outdoor": "Outdoor",
    "other": "Other",
}
MAX_BEDROOMS = 12
MAX_LIVING_AREAS = 4

def rooms_for(bedrooms, living_areas, keep=()):
    """Rooms to show for a property of this size (a 1- bed flat or a 7 bed house).
    'keep' = rooms already have photos and furniture. They always stay in the list,
     even if someone later lowers the bedroom count, so no data is hidden.
    """

    beds = min(int(bedrooms or 4), MAX_BEDROOMS)  # blank = typical 4 beds
    living = min(int(living_areas or 2), MAX_LIVING_AREAS)  # blank = typical 2 living area
    ids = ["living"] + [f"living{i}" for i in range(2, living + 1)]
    ids += ["dining", "kitchen", "master"] + [f"bed{i}" for i in range(2, beds + 1)]
    ids += ["study", "outdoor", "other"]
    ids += [r for r in keep if r in ROOM_LABELS and r not in ids]
    ids.sort(key=list(ROOM_LABELS).index)  # keep the standard order
    labels = {r: ROOM_LABELS[r] for r in ids}
    if beds == 1:
        labels["master"] = "Bedroom"
    if living > 1:
        labels["living"] = "Living Room 1"
        return labels


STAGES =[
    "Discussion with Customer",
    "Quote sent",
    "Approved",
    "Scheduled",
    "Styled",
    "D-staged",
    "Completed"
]
STYLED_INDEX = STAGES.index("Styled") # Photos unlock from this page
MAX_PHOTOS_PER_ROOM = 8

# The AI model name. If you ever get a "model not found" error, look up the
# Current model names at the docs.claude.com and change this on line.
AI_MODEL = "claude-sonnet-4-5"