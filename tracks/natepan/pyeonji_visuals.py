"""사연 편지함 1호 (결시친 옴니버스) — 씬 비주얼 생성 드라이버.

sijang_visuals와 동일한 구조 (앵커 반복·고유컷+씬매핑·편당 훅 모션 1컷).
바이블: data/bibles/pyeonji_series.yaml (mood / places / cast)

컷 정의: (cast 키 목록, 액션, 장소 키 | "none")
실행:  .venv/bin/python -m tracks.natepan.pyeonji_visuals [ep ...]
"""

from __future__ import annotations

import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
BIBLE = yaml.safe_load((ROOT / "data/bibles/pyeonji_series.yaml").read_text())
PRODUCE = ROOT / "data/assets/produce"

MOOD = BIBLE["mood"].strip()
PLACES = BIBLE["places"]
CAST = BIBLE["cast"]

EPISODES: dict[str, dict] = {
    "frame": {
        "shots": {
            "f1": ([], "The entrance hall of an old Korean apartment building (bokdo-style 90s apartment): a wall of small weathered steel mailboxes (upyeonham) with unit numbers, one mailbox stuffed with six handwritten letters sticking out, warm entrance light against blue evening, worn terrazzo floor.", "none"),
            "f2": ([], "Close-up of a green steel gate mailbox on a Korean brick house wall (jutaek), a single thick handwritten envelope being visible in the slot, late afternoon light, climbing ivy on the brick.", "none"),
            "f3": ([], "A rusty mailbox mounted beside the gate of a Korean multi-family villa (dasedae jutaek), an envelope inside along with a pair of worn cotton work gloves resting on top, warm dusk light.", "none"),
            "f4": ([], "Close-up of Korean apartment mailboxes, one box door ajar with an envelope and a corporate ID lanyard hanging out, fluorescent lobby light mixed with warm sunset from the entrance.", "none"),
            "f5": ([], "A snow-dusted green mailbox on a Korean hillside house wall at dawn, an envelope tucked inside, snowflakes drifting, blue winter light with one warm streetlamp.", "none"),
            "f6": ([], "An old Korean house gate mailbox at dusk, the last worn envelope halfway in the slot, an old brass key on a string hanging beside it, quiet nostalgic warmth.", "none"),
            "f7": ([], "Night: the Korean apartment entrance mailbox wall now tidy, all letters collected, one mailbox door gently closed, warm lobby lamp glowing, peaceful ending mood.", "none"),
        },
        "map": {1: "f1", 2: "f2", 3: "f3", 4: "f4", 5: "f5", 6: "f6", 7: "f7"},
        "motion": {"f1": "A hand gently pulling the six letters from the stuffed mailbox, dust motes in warm light, slow push-in toward the mailbox wall."},
    },
    "gongjang": {
        "shots": {
            "g1": (["gongjang_m", "gongjang_sinui"], "At a 60th-birthday family dinner table, the sister-in-law pushing a white envelope across the table toward the woman, relatives watching.", "none"),
            "g2": (["gongjang_m"], "Close-up: the woman's hands opening the thin envelope of banknotes, her face keeping a forced smile.", "none"),
            "g3": (["gongjang_m"], "Flashback: the same woman in her late 20s as a young bride, sitting stiffly at a steel desk piled with ledgers in the factory office.", "gongjang_office"),
            "g4": (["gongjang_m"], "The woman working alone at night in the factory office, calculator and open ledgers under fluorescent light, a lunchbox beside her.", "gongjang_office"),
            "g5": ([], "The aging workshop floor with lathes and shelves of bolts, workers' silhouettes, oil-stained floor.", "gongjang_factory"),
            "g6": (["gongjang_m"], "The woman bowing apologetically on an old phone at the office desk, bank documents spread out, exhausted.", "gongjang_office"),
            "g7": (["gongjang_m"], "Night at home: the woman pulling an old cardboard box of ledger copies and records from deep inside a wardrobe.", "none"),
            "g8": (["gongjang_m", "gongjang_sinui"], "In the factory office, the woman placing a thick document file on the desk in front of the shocked sister-in-law.", "gongjang_office"),
            "g9": (["gongjang_h"], "The husband kneeling on the living-room floor at night, head bowed deeply, the woman's shadow across him.", "none"),
            "g10": (["gongjang_m", "gongjang_h"], "The couple hanging a new signboard together above a small side-dish shop, the husband on a ladder, both laughing.", "banchan_shop"),
            "g11": (["gongjang_m"], "The woman in a clean apron arranging side dishes in the glass counter of her bright little shop, morning light.", "banchan_shop"),
            "g12": ([], "Close-up of a small framed photo beside the shop register: a young woman's old photograph from thirty years ago, warm light.", "banchan_shop"),
        },
        "map": {1: "g1", 2: "g2", 3: "g3", 4: "g3", 5: "g4", 6: "g6", 7: "g4", 8: "g5",
                9: "g6", 10: "g1", 11: "g2", 12: "g7", 13: "g8", 14: "g8", 15: "g8",
                16: "g9", 17: "g9", 18: "g10", 19: "g11", 20: "g11", 21: "g12", 22: "g12", 23: "g12"},
        "motion": {"g1": "Subtle tense stillness, the envelope sliding slowly across the table, candle-warm light flicker."},
    },
    "yaksa": {
        "shots": {
            "y1": (["yaksa_b"], "The woman in a beige coat standing in an apartment corridor before a front door, gripping her bag strap, resolved and pale.", "none"),
            "y2": (["yaksa_b", "yaksa_g"], "The couple sitting close at a cafe table in happier days, shy smiles, afternoon light.", "none"),
            "y3": (["yaksa_simo"], "The future mother-in-law at a formal family-meeting dinner table, unsmiling, chopsticks paused mid-air.", "none"),
            "y4": ([], "Close-up of a wedding appliance checklist on paper, several lines struck through in red pen, on a floral-cloth table.", "none"),
            "y5": (["yaksa_b"], "The woman staring at the returned list at her desk at night, hurt and angry, desk lamp light.", "none"),
            "y6": (["yaksa_simo"], "Through the opening front door: the mother-in-law startled on the sofa, hiding papers behind her back, documents scattered on the low table.", "yaksa_apart"),
            "y7": ([], "Close-up of a loan document page on the living-room floor, numbers softly out of focus, a man's name half visible.", "yaksa_apart"),
            "y8": (["yaksa_simo", "yaksa_b"], "The mother-in-law holding out an old savings passbook with both hands to the young woman, eyes lowered, humble.", "yaksa_apart"),
            "y9": (["yaksa_simo", "yaksa_b"], "The two women embracing in the small living room, both in tears, evening light through lace curtains.", "yaksa_apart"),
            "y10": (["yaksa_g"], "The young man kneeling sheepishly on the living-room floor while two women scold him, a comic-warm family scene.", "yaksa_apart"),
            "y11": (["yaksa_simo"], "The mother-in-law wiping the glass front of a small new pharmacy with a rag, flower pots at the entrance, spring light.", "yaksa_pharmacy"),
            "y12": ([], "Close-up of a framed passbook first-page copy on a bedroom wall, handwriting softly blurred, morning light.", "none"),
        },
        "map": {1: "y1", 2: "y2", 3: "y3", 4: "y4", 5: "y4", 6: "y5", 7: "y3", 8: "y2",
                9: "y5", 10: "y1", 11: "y6", 12: "y7", 13: "y8", 14: "y8", 15: "y8",
                16: "y9", 17: "y9", 18: "y10", 19: "y11", 20: "y12", 21: "y12", 22: "y12"},
        "motion": {"y6": "The door swinging slowly open revealing the startled woman, papers slipping from the table, held breath stillness."},
    },
    "sawi": {
        "shots": {
            "s1": (["sawi_h"], "The man in his early 40s in a crumpled suit standing with two suitcases at the green steel gate of a Korean brick house (jutaek) in a narrow residential alley at dusk, low brick walls and utility poles with tangled wires, wife and children behind, defeated posture.", "none"),
            "s2": (["sawi_jangmo"], "The elderly mother-in-law silently laying out a folded futon in a small room, warm lamp light.", "none"),
            "s3": (["sawi_h"], "The man at two a.m. hauling crates of fruit in a wholesale market, breath visible under sodium lights.", "sawi_market"),
            "s4": (["sawi_h"], "The man selling fruit from his one-ton truck by an apartment playground, elderly customers gathered, holding a loudspeaker mic.", "sawi_truck"),
            "s5": (["sawi_jangmo"], "Close-up: the old woman's hands packing a lunchbox at dawn, a handwritten note tucked under the rice container.", "none"),
            "s6": (["sawi_h"], "The man alone at the far end of a holiday dinner table, relatives laughing at the other end, his seat clearly separate.", "none"),
            "s7": ([], "A hospital corridor: an empty guardian bench, a phone showing missed calls lying on it, cold light.", "hospital_ward"),
            "s8": (["sawi_h"], "Close-up over the shoulder: the man's rough hand writing on a surgery consent form's guardian line, pen pressed firm.", "hospital_ward"),
            "s9": (["sawi_h", "sawi_jangmo"], "The man spoon-feeding porridge to the old woman in a hospital bed at dawn, tender and unhurried.", "hospital_ward"),
            "s10": (["sawi_jangmo"], "The old woman standing firm in a hospital lobby addressing her adult sons, small but commanding, the sons' heads lowered.", "hospital_ward"),
            "s11": (["sawi_h"], "The man at the family dinner table now seated beside the old woman's place of honor, receiving a drink from a brother-in-law, warm reconciliation.", "none"),
            "s12": (["sawi_h"], "The man beside two fruit trucks at dawn, arms crossed with a proud small smile, a hand-painted new shop sign leaning against the truck.", "sawi_truck"),
        },
        "map": {1: "s1", 2: "s2", 3: "s6", 4: "s3", 5: "s5", 6: "s4", 7: "s5", 8: "s6",
                9: "s7", 10: "s7", 11: "s8", 12: "s8", 13: "s9", 14: "s9", 15: "s9",
                16: "s10", 17: "s11", 18: "s11", 19: "s12", 20: "s12"},
        "motion": {"s4": "Gentle bustle around the fruit truck, steam from a coffee cup, elderly customers chatting, morning warmth."},
    },
    "palsun": {
        "shots": {
            "p1": (["palsun_w"], "The woman in a charcoal suit in a glass meeting room, standing at the head of the table mid-presentation, poised authority.", "palsun_office"),
            "p2": (["palsun_w"], "The same woman at a crowded holiday dinner at her in-laws', sitting at the table edge, forcing a smile while serving food.", "none"),
            "p3": (["palsun_f"], "The elderly father at a fruit wholesale stall at dawn, arranging crates with weathered hands, humble and content.", "none"),
            "p4": (["palsun_w"], "The woman on the office rooftop on the phone with her father, holding back tears, city dusk behind.", "palsun_office"),
            "p5": (["palsun_w", "palsun_h"], "A tense argument in a night living room, the woman finally shouting, the husband frozen with a calendar in his hand.", "none"),
            "p6": (["palsun_f"], "The 80th-birthday banquet: the elderly father in a modest grey hanbok seated at the head table before the folding screen, the stacked fruit-and-rice-cake towers beside him, guests raising soju glasses.", "palsun_janchi"),
            "p7": ([], "An elderly guest in a suit standing to give a toast at the banquet, mid-laughter, low tables of Korean food and soju bottles, festive warmth.", "palsun_janchi"),
            "p8": (["palsun_h"], "The husband's face gone pale at the banquet table, chopsticks lowered, realization dawning.", "palsun_janchi"),
            "p9": (["palsun_h", "palsun_f"], "The husband performing a deep formal bow on the banquet floor before the startled elderly father, guests watching in hushed silence.", "palsun_janchi"),
            "p10": (["palsun_f"], "Close-up: the elderly father lifting the son-in-law by the hands, eyes wet, saying something gently.", "palsun_janchi"),
            "p11": (["palsun_w", "palsun_h", "palsun_f"], "New Year's morning at the modest parental home: the couple bowing together to the beaming father, breakfast table steaming.", "none"),
            "p12": (["palsun_w"], "The woman back at her office desk, stamping a document, a small smile, family photo now facing up beside the monitor.", "palsun_office"),
        },
        "map": {1: "p1", 2: "p2", 3: "p2", 4: "p2", 5: "p3", 6: "p3", 7: "p1", 8: "p4",
                9: "p5", 10: "p5", 11: "p6", 12: "p7", 13: "p7", 14: "p8", 15: "p8",
                16: "p9", 17: "p10", 18: "p5", 19: "p11", 20: "p11", 21: "p11", 22: "p12", 23: "p12"},
        "motion": {"p9": "The slow deep bow unfolding, guests turning their heads, banquet lights soft, emotional stillness."},
    },
    "ganhosa": {
        "shots": {
            "n1": (["ganhosa_n"], "The nurse in uniform under a padded coat walking out of a hospital lobby at dawn, exhausted, breath visible.", "hospital_ward"),
            "n2": (["ganhosa_simo"], "The silent mother-in-law locking the front door behind the departing nurse at night, expressionless, hallway light.", "ganhosa_home"),
            "n3": (["ganhosa_n"], "The nurse mid-shift at a busy ward station at night, phones ringing, monitors glowing, composed under pressure.", "hospital_ward"),
            "n4": ([], "A front door quietly ajar at five a.m., a small shadow slipping out, blue dawn in the hallway.", "ganhosa_home"),
            "n5": (["ganhosa_n"], "The nurse walking up a steep snowy alley at dawn — the stairway strangely swept clean of snow ahead of her.", "ganhosa_alley"),
            "n6": (["ganhosa_simo"], "Under a streetlamp in falling snow: the small woman in the purple padded coat sweeping the stairs with a broom, caught by surprise.", "ganhosa_alley"),
            "n7": ([], "Close-up through a door gap: an old wall calendar densely marked with hand-drawn circles, dawn light.", "ganhosa_home"),
            "n8": (["ganhosa_simo"], "The old woman scattering briquette ash on icy steps before dawn, working quietly ahead of the bus stop.", "ganhosa_alley"),
            "n9": (["ganhosa_n"], "The nurse standing alone in the snowy alley, hand over her mouth, tears freezing on her lashes.", "ganhosa_alley"),
            "n10": ([], "A takeout container of hot abalone porridge with a folded note, left at a doorstep, steam rising in cold air.", "none"),
            "n11": (["ganhosa_n", "ganhosa_simo"], "Kimchi-making day: the two women sitting knee to knee over tubs of cabbage, laughing mid-chatter, red pepper paste on gloves.", "ganhosa_home"),
            "n12": ([], "Close-up of a refrigerator door with two handwritten duty rosters side by side under magnets, warm kitchen light.", "ganhosa_home"),
        },
        "map": {1: "n1", 2: "n2", 3: "n2", 4: "n4", 5: "n3", 6: "n3", 7: "n7", 8: "n4",
                9: "n3", 10: "n5", 11: "n5", 12: "n6", 13: "n7", 14: "n8", 15: "n9",
                16: "n2", 17: "n10", 18: "n10", 19: "n11", 20: "n12", 21: "n12", 22: "n12"},
        "motion": {"n6": "Snow falling steadily, the broom moving in slow strokes, streetlamp halo glowing, the small figure looking up."},
    },
    "sangsok": {
        "shots": {
            "k1": (["sangsok_d"], "The woman CEO at her office window at dusk, city lights below, composed but distant gaze.", "ceo_office"),
            "k2": (["sangsok_f"], "The elderly father working at an old offset printing machine, ink-stained hands, absorbed.", "insoe"),
            "k3": (["sangsok_d"], "Flashback: the same woman in her 20s delivering side-dish boxes from a battered truck in winter, wearing double gloves.", "none"),
            "k4": ([], "A lawyer's office table: a will document being read, two brothers seated, one empty chair, cold light.", "none"),
            "k5": (["sangsok_d"], "The woman at home at night, blanket over her head on the bed, shoulders shaking, city glow through the window.", "none"),
            "k6": ([], "The print shop's steel desk: the bottom drawer pulled open revealing an old metal box, a paper label in handwriting on its lock, dusty light shaft.", "insoe"),
            "k7": ([], "Close-up of the opened metal box: an old bank passbook and a thick bundle of yellowed newspapers inside.", "insoe"),
            "k8": ([], "Extreme close-up of the passbook's inside cover, a short pencil-pressed memo line softly out of focus, trembling fingers holding it.", "insoe"),
            "k9": ([], "The newspaper bundle unfolded on the workbench: pages worn white at the corners from repeated reading, a woman's interview photo softly blurred.", "insoe"),
            "k10": (["sangsok_d"], "The woman collapsed onto the print shop stool, pressing the newspapers to her chest, weeping openly among the old machines.", "insoe"),
            "k11": (["sangsok_f"], "Flashback: the elderly father proudly showing a newspaper to print-shop customers, pointing at a page, boastful warm grin.", "insoe"),
            "k12": (["sangsok_d"], "A scholarship ceremony: the woman CEO handing a certificate to a young woman entrepreneur on a small stage, both smiling with wet eyes.", "none"),
        },
        "map": {1: "k1", 2: "k2", 3: "k2", 4: "k3", 5: "k1", 6: "k2", 7: "k4", 8: "k4",
                9: "k5", 10: "k3", 11: "k1", 12: "k6", 13: "k7", 14: "k8", 15: "k8",
                16: "k8", 17: "k9", 18: "k10", 19: "k11", 20: "k12", 21: "k12", 22: "k12"},
        "motion": {"k6": "The drawer sliding open slowly, dust motes in the light shaft, the handwritten label coming into focus."},
    },
}


def build_prompt(cast_keys: list[str], action: str, place: str) -> str:
    parts: list[str] = []
    if place != "none" and place in PLACES:
        parts.append("The scene is at " + PLACES[place].strip() + ".")
    for key in cast_keys:
        parts.append("Featuring " + CAST[key].strip() + ".")
    parts.append(action)
    return " ".join(parts)


def generate(ep_name: str) -> None:
    from core.visuals.higgsfield_gen import gen_image, gen_motion

    ep = EPISODES[ep_name]
    vis = PRODUCE / f"pyeonji_{ep_name}_vis"
    shots_dir = vis / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    def make(item):
        key, (cast_keys, action, place) = item
        ok = gen_image(build_prompt(cast_keys, action, place),
                       shots_dir / f"{key}.png", style=MOOD + " ")
        print(f"[{ep_name}] IMG {key} {'OK' if ok else 'FAIL'}", flush=True)

    todo = [(k, v) for k, v in ep["shots"].items()
            if not (shots_dir / f"{k}.png").exists()]
    if todo:
        with ThreadPoolExecutor(max_workers=3) as ex:
            list(ex.map(make, todo))

    for scene_id, shot_key in ep["map"].items():
        src, dst = shots_dir / f"{shot_key}.png", vis / f"{scene_id:02d}.png"
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

    for shot_key, motion_desc in ep["motion"].items():
        first_scene = min(s for s, k in ep["map"].items() if k == shot_key)
        ok = gen_motion(shots_dir / f"{shot_key}.png", motion_desc,
                        vis / f"{first_scene:02d}.mp4")
        print(f"[{ep_name}] MOT {shot_key}->{first_scene:02d} {'OK' if ok else 'FAIL'}",
              flush=True)


if __name__ == "__main__":
    targets = sys.argv[1:] or list(EPISODES)
    for name in targets:
        print(f"=== {name} ===", flush=True)
        generate(name)
