PANEL_SCRIPT = (
    {
        "stage": "Beginning",
        "panel_title": "The Old Camera",
        "visual": "Arjun explores an abandoned railway station, finds an old mysterious camera lying on a broken bench, and picks it up with a curious expression.",
        "character_action": "Arjun carefully lifts the camera from the broken bench.",
        "background": "An abandoned railway platform with a broken wooden bench and old station arches.",
        "facial_expression": "curious",
        "camera_angle": "wide establishing view",
        "composition": "Arjun and the broken bench are clearly visible in the station.",
        "important_objects": "mysterious old camera, broken bench, black backpack",
        "characters_present": "Arjun",
        "dialogues": ("Arjun: Who left this here? I'll take a photo.",),
        "narration": (
            "After college, Arjun and Kavin enter the\n"
            "silent, dusty abandoned station.\n\n"
            "In the old waiting area, Arjun finds a camera\n"
            "on a broken bench and picks it up."
        ),
        "lighting": "Cool evening light with a warm glow on the camera.",
        "mood": "mysterious curiosity",
    },
    {
        "stage": "Development",
        "panel_title": "A Future Picture",
        "visual": "Arjun takes a photograph with the mysterious camera. Its screen shows his friend Kavin standing near railway tracks. Arjun looks shocked and confused.",
        "character_action": "Arjun peers at the camera screen after taking a photograph.",
        "background": "The abandoned station platform, with the camera screen clearly showing Kavin by the tracks.",
        "facial_expression": "shocked and confused",
        "camera_angle": "medium close-up over the camera",
        "composition": "Arjun, the camera screen, and Kavin in its future image are all legible.",
        "important_objects": "mysterious camera with a clear image of Kavin",
        "characters_present": "Arjun and Kavin in the camera screen",
        "dialogues": ("Arjun: Is this showing the future?",),
        "narration": (
            "Arjun points the camera at the empty\n"
            "platform and takes a photograph.\n\n"
            "Its screen shows Kavin by the tracks,\n"
            "though he is still standing beside Arjun."
        ),
        "lighting": "Soft station light with a bright glow from the camera screen.",
        "mood": "surprise and confusion",
    },
    {
        "stage": "Turning Point",
        "panel_title": "A Warning",
        "visual": "The camera shows a future vision of Kavin near the railway tracks while a train approaches in the distance. Arjun realizes the camera predicts the future and starts running.",
        "character_action": "Arjun sees the approaching train in the camera and breaks into a run.",
        "background": "Railway tracks, a distant approaching train, and the abandoned station.",
        "facial_expression": "alarmed and determined",
        "camera_angle": "dynamic medium view",
        "composition": "The future image of Kavin and train is visible in the camera; Arjun is moving to run.",
        "important_objects": "camera showing Kavin near the tracks, distant train",
        "characters_present": "Arjun and Kavin in the future vision",
        "dialogues": ("Arjun: Kavin is in danger!",),
        "narration": (
            "Arjun's second photo shows Kavin\n"
            "dangerously close to the tracks.\n\n"
            "A train approaches. Arjun knows it will\n"
            "happen in minutes and runs to stop him."
        ),
        "lighting": "Tense cool station shadows with a distant train headlight.",
        "mood": "urgent danger",
    },
    {
        "stage": "Climax",
        "panel_title": "The Rescue",
        "visual": "Arjun reaches Kavin just in time and pulls him away from the railway tracks. A train passes in the background. Both characters look shocked.",
        "character_action": "Arjun pulls Kavin safely onto the platform as the train rushes past behind them.",
        "background": "Railway platform with a passing train in the background, safely separated from the friends.",
        "facial_expression": "both shocked",
        "camera_angle": "dynamic side view",
        "composition": "Arjun pulling Kavin toward the platform, with the passing train clearly behind them.",
        "important_objects": "railway tracks, passing train, black backpack",
        "characters_present": "Arjun and Kavin",
        "dialogues": ("Arjun: Kavin, move!", "Kavin: How did you know?"),
        "narration": (
            "Arjun pulls Kavin from the tracks just in time.\n\n"
            "A train rushes past. Together, they realize\n"
            "the camera saved Kavin's life."
        ),
        "lighting": "Bright train lights streaking across the station at evening.",
        "mood": "high-energy rescue",
    },
    {
        "stage": "Ending",
        "panel_title": "The Mystery Continues",
        "visual": "Arjun and Kavin safely leave the abandoned railway station. Outside in the evening light, they look together at the mysterious camera.",
        "character_action": "Arjun and Kavin stand together outside, examining the camera after their escape.",
        "background": "The abandoned station entrance at sunset with a safe open path outside.",
        "facial_expression": "relieved and curious",
        "camera_angle": "wide two-person view",
        "composition": "Both friends and the camera are clear against the warmly lit station entrance.",
        "important_objects": "mysterious camera, station entrance",
        "characters_present": "Arjun and Kavin",
        "dialogues": ("Kavin: How did you know?",),
        "narration": (
            "Before sunset, Arjun and Kavin leave safely,\n"
            "studying the camera's secret.\n\n"
            "Arjun senses a bigger mystery. Suddenly,\n"
            "the camera snaps a photo by itself!"
        ),
        "lighting": "Warm evening sunset light.",
        "mood": "relief and lingering mystery",
    },
)


def get_panel_script():
    return [
        {**panel, "dialogues": list(panel["dialogues"])}
        for panel in PANEL_SCRIPT
    ]


def get_panel_lettering(panel_number):
    panel = PANEL_SCRIPT[int(panel_number) - 1]
    return list(panel["dialogues"]), panel["narration"]