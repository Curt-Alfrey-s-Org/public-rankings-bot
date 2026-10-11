#!/usr/bin/env python3
"""
Player Database - Country and name information for WPBA players
"""

# Player country lookup - will be expanded as we process tournaments
PLAYER_COUNTRIES = {
    "Kristina Tkach": "USA",
    "Pia Filler": "GER",
    "Savannah Easton": "USA",
    "Kristina Zlateva": "BUL",
    "Brittany Bryant": "USA",
    "Mayte Ropero": "ESP",
    "Caroline Pao": "USA",
    "Ashley Benoit": "CAN",
    "Kaylee McIntosh Driskell": "USA",
    "Eylul Kibaroglu": "TUR",
    "LoreeJon Brown": "USA",
    "Kristina Grim": "USA",
    "Margaret Fefilova-Styer": "USA",
    "Monica Webb": "USA",
    "Kennedy Meyman": "USA",
    "Olivia Cheng": "USA",
    "Veronique Menard": "CAN",
    "Janet Atwell": "USA",
    "Susan Williams": "USA",
    "Lonnie Fox-Raymond": "USA",
    "Jordan Helfery": "USA",
    "Cathy McDaniel": "USA",
    "Rebekah White": "USA",
    "Tracy Hardie": "USA",
    "Briana Miller": "USA",
    "Angela Janic": "USA",
    "Ada Lio": "USA",
    "Susan Mello": "USA",
    "Billie Billing": "USA",
    "Rachel Lang": "USA",
    "Jessica Barnes": "USA",
    "Silvia Lopez": "USA",
    "Ashley Rice": "USA",
    "Emily Duddy": "USA",
    "Stephanie Mitchell": "USA",
    "Sara Miller": "USA",
    "Lisa Cossette": "USA",
    "Joanne Ashton": "CAN",
    "June Maiers": "USA",
    "Shanelle Loraine": "USA",
    "Kia Bennett": "USA",
    "Aleksandra Guleikova": "RUS",
    "Veronica Lyon": "USA",
    "Krystal DePelsMaeker": "USA",
    "Avah Weems": "USA",
    "Michell Monk": "USA",
    "Giovanna Napolitano": "ITA",
    "Julie Stephens": "USA",
}


def get_player_country(full_name: str) -> str:
    """Get player country by full name"""
    return PLAYER_COUNTRIES.get(full_name, "USA")  # Default to USA if not found


def split_player_name(full_name: str) -> tuple:
    """
    Split full name into (family_name, given_names)
    Examples:
        "Kristina Tkach" -> ("Tkach", "Kristina")
        "Kaylee McIntosh Driskell" -> ("Driskell", "Kaylee McIntosh")
    """
    parts = full_name.strip().split()
    if len(parts) == 1:
        return (parts[0], "")
    else:
        # Last part is family name, everything else is given names
        family_name = parts[-1]
        given_names = " ".join(parts[:-1])
        return (family_name, given_names)
