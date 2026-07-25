"""시장 골목 연작 — 씬 비주얼 생성 드라이버.

일관성 규칙 (CLAUDE.md 11장):
  - 무드/장소/인물 앵커는 data/bibles/sijang_series.yaml에서 읽어
    "모든 프롬프트에 그대로 반복" 삽입한다.
  - 에피소드당 고유 컷 14~17장 + 씬 매핑(같은 컷을 여러 씬 번호로 복사).
  - 모션은 편당 오프닝 훅 1컷만 (정책: 바이블 motion 항목).

컷 정의: (cast 키 목록, 액션 묘사[, 장소 모드])
  장소 모드 — "shop"(기본: 아케이드+해당 가게) / 가게 키 문자열(다른 가게) /
  "arcade"(아케이드만) / "near"(시장 바로 바깥, 캐노피 배경) / "none"(시장 외부)

실행:  .venv/bin/python -m tracks.natepan.sijang_visuals [ep ...]
       (ep 생략 시 전체: frame suseon gudubang tteokjip munbanggu)
재실행 안전: 기존 파일은 건너뜀 (3분 간격 재시도 루프는 호출측에서).
"""

from __future__ import annotations

import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
BIBLE = yaml.safe_load((ROOT / "data/bibles/sijang_series.yaml").read_text())
PRODUCE = ROOT / "data/assets/produce"

MOOD = BIBLE["mood"].strip()
PLACE = BIBLE["place"].strip()
NEAR_PLACE = (
    "Just outside the same old traditional Korean covered market, its "
    "translucent corrugated canopy roof and hanging globe lamps visible in the "
    "background, weathered Korean shopfronts and hand-painted signs nearby."
)
SHOPS = BIBLE["shops"]
CAST = BIBLE["cast"]

# ---------------------------------------------------------------------------
# 에피소드 콘테 — shots: 고유 컷, map: 씬번호→컷
# ---------------------------------------------------------------------------

EPISODES: dict[str, dict] = {
    "frame": {
        "shop": None,
        "shots": {
            "f1": ([], "Dawn at five a.m., wide establishing shot down the empty arcade, metal shutters half-raised, thick white steam drifting from a soup pot near the entrance, cool blue morning light mixing with warm lamps.", "arcade"),
            "f2": ([], "Morning, view along the alley from a fogged-glass soup restaurant toward the market entrance in the distance, a few shopkeepers setting up stalls.", "arcade"),
            "f3": ([], "Mid-morning warm wide shot of the arcade interior, stacked rice sacks visible at a shopfront, golden light shafts through the canopy roof.", "arcade"),
            "f4": ([], "View into a deeper narrow side of the alley, warm incandescent glow spilling from a small repair shop's glass door, quiet atmosphere.", "arcade"),
            "f5": ([], "Long symmetrical perspective down the full length of the arcade, both far ends visible as small bright openings, hanging lamps receding into distance.", "arcade"),
            "f6": ([], "Early evening, the far end of the alley where the market meets a residential lane, a small laundry's warm window light, plastic-covered clothes visible inside.", "arcade"),
            "f7": ([], "Autumn afternoon at the corner where the market alley meets an elementary school back gate, ginkgo leaves on the ground, a small stationery shop's colorful storefront.", "arcade"),
            "f8": ([], "Night, the arcade after closing, all shutters down, round globe lamps still glowing warmly, one distant shop light left on, quiet and tender.", "arcade"),
        },
        "map": {1: "f1", 2: "f2", 3: "f3", 4: "f4", 5: "f5", 6: "f6", 7: "f7", 8: "f8"},
        "motion": {"f1": "Steam slowly drifting and curling upward, subtle flicker of lamps, very slow push-in down the alley."},
    },
    "gudubang": {
        "shop": "gudubang",
        "shots": {
            "g1": ([], "Establishing shot of the tiny shoeshine booth at the market entrance in soft morning light, the old bus stop sign beside it."),
            "g2": (["gudubang_choi"], "The old shoeshiner sitting inside his booth, methodically polishing a shoe, absorbed in his work."),
            "g3": (["gudubang_choi", "gudubang_yeong"], "The young man in the navy suit standing in front of the booth holding a pair of dress shoes, the old shoeshiner looking up at him."),
            "g4": ([], "Close-up of a pair of pristine, spotless black dress shoes being handed over a small wooden counter, two pairs of hands."),
            "g5": ([], "Market people passing the booth exchanging amused glances, a vendor woman whispering to another near a produce stall.", "arcade"),
            "g6": (["gudubang_yeong"], "Flashback, eleven years earlier: the same man but in his early twenties, in a cheap ill-fitting grey suit completely soaked by heavy summer rain, standing miserable under the booth's narrow eaves, rain pouring off the canopy."),
            "g7": (["gudubang_choi"], "Close-up of the old shoeshiner's stained hands polishing a muddy, worn-out dress shoe to a mirror shine, rain blurring the background."),
            "g8": (["gudubang_yeong"], "Flashback: the young man in his early twenties in the cheap grey suit, quietly crying under the eaves in the rain, holding the freshly shined shoes, trying to compose himself."),
            "g9": (["gudubang_yeong"], "Flashback: a bright clear morning, the young man in his twenties walking down the market alley with confident steps, gleaming shoes, morning sun flaring.", "arcade"),
            "g10": (["gudubang_choi", "gudubang_yeong"], "The young man sitting on the low stool beside the booth, the old shoeshiner working, both comfortable in silence, morning light."),
            "g11": ([], "An official demolition notice paper taped to the booth's wooden wall, the printed text softly out of focus and unreadable, grey overcast light."),
            "g12": ([], "A queue of office workers in suits lined up in front of the tiny shoeshine booth in the morning, each holding a pair of shoes, market coming alive around them."),
            "g13": ([], "A group of middle-aged market merchants in aprons and work vests gathered around the booth in discussion, determined warm faces."),
            "g14": ([], "Autumn: a neat new wooden shoeshine stand beside a renovated bus stop, the old weathered wooden signboard re-hung on it, warm golden light.", "near"),
            "g15": (["gudubang_choi", "gudubang_yeong"], "Moving day: the young man in rolled-up shirt sleeves carrying a wooden box of polish tins, the old shoeshiner carrying his stool, both mid-conversation, gentle smiles.", "near"),
            "g16": (["gudubang_yeong"], "Morning at the new shoeshine stand: the young man first in a long queue of people holding shoes, warm sunrise light.", "near"),
        },
        "map": {1: "g1", 2: "g3", 3: "g4", 4: "g5", 5: "g6", 6: "g6", 7: "g7", 8: "g7",
                9: "g8", 10: "g9", 11: "g10", 12: "g11", 13: "g2", 14: "g12", 15: "g10",
                16: "g13", 17: "g14", 18: "g15", 19: "g15", 20: "g16", 21: "g16"},
        "motion": {"g1": "Gentle morning bustle, a bus passing softly in the background, subtle steam, slow push-in toward the booth."},
    },
    "suseon": {
        "shop": "suseon",
        "shots": {
            "s1": ([], "Establishing shot looking into the repair shop through its glass door, the old sewing machine and fabric rolls lit by a single warm bulb."),
            "s2": (["suseon_jeong"], "The seamstress working at her old sewing machine, concentrated, warm bulb light on her hands."),
            "s3": (["suseon_jeong", "suseon_cheong"], "The young man in the worn grey padded jacket standing at the counter, handing the folded jacket to the seamstress with both hands, polite and shy."),
            "s4": ([], "Close-up of the worn grey padded jacket laid flat on a worktable: the back panel and both shoulders visibly worn smooth and shiny, sleeves still intact."),
            "s5": (["suseon_jeong"], "The seamstress holding the jacket up under the bulb, examining the strangely worn back panel with a puzzled, thoughtful expression."),
            "s6": (["suseon_cheong"], "Close-up at the counter: the young man's rough hands carefully flattening crumpled banknotes and offering them with both hands."),
            "s7": (["suseon_jeong"], "Cold winter pre-dawn, the seamstress in a thick coat with a market bag walking through the dark blue empty alley toward the first bus.", "arcade"),
            "s8": (["suseon_cheong", "suseon_eomeoni"], "Winter dawn on a steep hillside residential stairway behind the old market: the young man in the worn grey padded jacket carrying his elderly mother on his back, descending the frozen concrete steps carefully, her hands gripping his shoulders, breath visible in the cold blue air, the market's canopy roof small in the distance below.", "none"),
            "s9": (["suseon_cheong", "suseon_eomeoni"], "At the bus stop bench in dawn light: the young man kneeling to eye level with his seated elderly mother, re-wrapping her scarf gently.", "near"),
            "s10": (["suseon_jeong"], "Macro shot of the seamstress's hands sewing a tough hidden reinforcement panel inside the jacket's back, a soft fleece layer at the shoulders, stitches hidden inside the lining."),
            "s11": ([], "Dawn at the bus stop: a steaming thermos and a wrapped side dish quietly left on the bench, a maroon-aproned woman walking away in the background.", "near"),
            "s12": (["suseon_cheong"], "The young man in the grey padded jacket helping right an overturned handcart in the alley, other merchants joining, casual working warmth.", "arcade"),
            "s13": (["suseon_eomeoni"], "Spring: the elderly mother with her cane, alone, carefully opening the repair shop's glass door, soft afternoon light behind her."),
            "s14": (["suseon_jeong", "suseon_eomeoni"], "The mother unwrapping a brand-new dark jacket from a cloth bundle on the counter, speaking earnestly to the seamstress who listens closely."),
            "s15": ([], "Night in the shop: close-up of hands embroidering something inside the new jacket's back lining by lamplight, the thread pattern softly out of focus, a cup of tea gone cold beside."),
            "s16": (["suseon_cheong"], "The young man wearing the new dark jacket, receiving his old grey jacket folded in a paper bag, bowing slightly, both hands, gentle smile."),
        },
        "map": {1: "s1", 2: "s3", 3: "s4", 4: "s5", 5: "s6", 6: "s7", 7: "s8", 8: "s8",
                9: "s9", 10: "s10", 11: "s10", 12: "s3", 13: "s11", 14: "s11", 15: "s12",
                16: "s13", 17: "s14", 18: "s15", 19: "s16", 20: "s2"},
        "motion": {"s8": "Very slow careful steps down the stairs, breath misting in cold air, the mother's hands holding steady, handheld documentary feel."},
    },
    "tteokjip": {
        "shop": "tteok_east",
        "shots": {
            "t1": ([], "Long perspective down the arcade showing both distant ends of the alley, morning steam rising at two far points, lamps receding.", "arcade"),
            "t2": (["tteok_sunnam"], "The older sister arranging fresh rice cakes in the glass display case of the east-end shop, steam rising from a wooden steamer behind her."),
            "t3": (["tteok_sunok"], "The younger sister at the west-end mill feeding rice into an old milling machine, focused, flour dust in warm light.", "tteok_west"),
            "t4": ([], "Close-up of fresh Korean rice cakes: white baekseolgi in a steaming wooden siru, injeolmi coated in roasted soybean powder on a wooden tray."),
            "t5": ([], "Flashback thirty-five years ago: a bustling large rice-cake shop in the middle of the same arcade, a long queue of customers in older-era clothing, huge clouds of steam, nostalgic faded warmth.", "arcade"),
            "t6": ([], "Close-up of an old handwritten recipe notebook torn in half on a wooden table, the two halves separated, handwriting softly out of focus, one lamp overhead.", "none"),
            "t7": ([], "Four-thirty a.m., the empty dark-blue arcade: a small figure in an apron quietly crossing the alley carrying a wrapped bundle, long shadows under the globe lamps.", "arcade"),
            "t8": ([], "Close-up of a cloth-wrapped bundle of warm rice cake hanging on a shop's door handle in blue dawn light, faint steam escaping the wrapping.", "arcade"),
            "t9": ([], "A small container of dark sweet rice placed carefully on a doorstep, dawn light, weathered shop door.", "arcade"),
            "t10": (["tteok_sunok"], "The younger sister running down the dawn alley still in her apron, clutching a container, alarmed, motion blur on the lamps.", "arcade"),
            "t11": (["tteok_sunnam", "tteok_sunok"], "Inside the east shop: the older sister sitting on the floor holding her wrist, the younger sister rushing through the door toward her, steam filling the room."),
            "t12": (["tteok_sunok"], "The younger sister lifting a heavy steaming siru in her sister's shop, eyes wet but smiling, dense white steam around her."),
            "t13": (["tteok_sunok"], "Dawn: the younger sister carrying a wooden tray of rice cakes across the alley between the two shops, merchants at their stalls watching with quiet warm smiles.", "arcade"),
            "t14": (["tteok_sunnam", "tteok_sunok"], "At the counter: one sister offering a cloth bundle containing half of an old notebook, the other sister receiving it with both hands, eyes meeting."),
            "t15": ([], "Close-up of the two torn notebook halves laid together on a table, edges matching perfectly, two pairs of older women's hands smoothing tape over the seam, lamplight.", "none"),
            "t16": (["tteok_sunnam", "tteok_sunok"], "Lunar New Year: a small festive tent stall in the middle of the arcade, the two sisters in pink and green aprons side by side serving a long queue, trays of colorful rice cakes.", "arcade"),
            "t18": (["tteok_sunnam", "tteok_sunok"], "Dawn: the two sisters meeting in the middle of the alley, exchanging wrapped bundles, sitting together on a bench under a globe lamp, quiet companionship.", "arcade"),
        },
        "map": {1: "t1", 2: "t2", 3: "t5", 4: "t6", 5: "t6", 6: "t3", 7: "t7", 8: "t8",
                9: "t9", 10: "t10", 11: "t11", 12: "t12", 13: "t13", 14: "t14", 15: "t15",
                16: "t16", 17: "t16", 18: "t18", 19: "t8"},
        "motion": {"t1": "Steam drifting from both far ends of the alley, lamps flickering softly, very slow dolly forward."},
    },
    "munbanggu": {
        "shop": "munbanggu",
        "shots": {
            "m1": ([], "Establishing shot of the old stationery shop at the corner by the school back gate, autumn afternoon, racks of colorful supplies outside."),
            "m2": (["munbanggu_song"], "The old shopkeeper sitting on the wooden bench in front of his shop in the quiet afternoon, watching the empty alley."),
            "m3": (["munbanggu_song", "munbanggu_nam"], "The middle-aged man in the navy suit standing hesitantly in front of the shop, the old shopkeeper looking up from the bench."),
            "m4": (["munbanggu_song", "munbanggu_nam"], "Inside at the counter: a single banknote placed on the worn wooden counter between the two men, shelves of school supplies behind."),
            "m5": ([], "Flashback forty years ago: a thin Korean boy around ten in a worn hand-me-down jacket standing outside the shop window in fading light, gazing at notebooks and crayons through the glass."),
            "m6": ([], "Flashback: the same shopkeeper as a black-haired man in his forties in a brown cardigan, holding out a paper bag of notebooks and pencils to the thin boy in the worn jacket at the shop door."),
            "m7": ([], "Flashback: the thin boy running down the market alley clutching the paper bag to his chest, joyful, morning light through the canopy.", "arcade"),
            "m8": ([], "Flashback: night in a poor small room, the boy doing homework with a short pencil under a dim lamp, the paper bag beside him.", "none"),
            "m9": (["munbanggu_song"], "The old shopkeeper reaching under the counter and drawing out a single old worn notebook, deliberate and calm."),
            "m10": (["munbanggu_nam"], "Close-up over the shoulder: the old notebook lying open on the counter, its pages empty, the suited man's face reflecting disbelief and welling emotion, handwriting on the first page softly out of focus."),
            "m11": (["munbanggu_song", "munbanggu_nam"], "The old shopkeeper laughing heartily on the bench, head back, the suited man beside him smiling with wet eyes, passersby glancing over warmly."),
            "m12": ([], "Close-up of a brand-new notebook placed on the counter, a fountain pen resting on it, afternoon light."),
            "m13": ([], "Present day: two elementary school kids with backpacks pushing open the shop door cheerfully, colorful supplies inside, bright daylight."),
            "m14": (["munbanggu_song"], "The old shopkeeper holding the new notebook open but writing nothing, smiling toward the door as a child leaves waving."),
            "m15": ([], "Macro shot of a child's pencil case: short well-used pencils and one brand-new pencil side by side, soft window light.", "none"),
        },
        "map": {1: "m1", 2: "m3", 3: "m4", 4: "m4", 5: "m5", 6: "m6", 7: "m7", 8: "m8",
                9: "m8", 10: "m9", 11: "m10", 12: "m10", 13: "m4", 14: "m11", 15: "m11",
                16: "m11", 17: "m12", 18: "m13", 19: "m14", 20: "m15"},
        "motion": {"m1": "Ginkgo leaves drifting down slowly, kids passing the school gate in the background, slow push-in on the shop."},
    },
}


def build_prompt(ep: dict, cast_keys: list[str], action: str, mode: str = "shop") -> str:
    parts: list[str] = []
    if mode == "shop":
        parts.append(PLACE)
        if ep["shop"]:
            parts.append("The scene is at " + SHOPS[ep["shop"]].strip() + ".")
    elif mode in SHOPS:
        parts.append(PLACE)
        parts.append("The scene is at " + SHOPS[mode].strip() + ".")
    elif mode == "arcade":
        parts.append(PLACE)
    elif mode == "near":
        parts.append(NEAR_PLACE)
    # "none": 장소 앵커 없이 무드만
    for key in cast_keys:
        parts.append("Featuring " + CAST[key].strip() + ".")
    parts.append(action)
    return " ".join(parts)


def generate(ep_name: str) -> None:
    from core.visuals.higgsfield_gen import gen_image, gen_motion

    ep = EPISODES[ep_name]
    vis = PRODUCE / f"sijang_{ep_name}_vis"
    shots_dir = vis / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    def make(item):
        key, spec = item
        cast_keys, action, mode = (*spec, "shop")[:3]
        ok = gen_image(build_prompt(ep, cast_keys, action, mode),
                       shots_dir / f"{key}.png", style=MOOD + " ")
        print(f"[{ep_name}] IMG {key} {'OK' if ok else 'FAIL'}", flush=True)

    todo = [(k, v) for k, v in ep["shots"].items()
            if not (shots_dir / f"{k}.png").exists()]
    if todo:
        with ThreadPoolExecutor(max_workers=3) as ex:
            list(ex.map(make, todo))

    # 씬 번호 매핑 — 같은 컷을 여러 씬으로 복사 (produce --images 규격)
    for scene_id, shot_key in ep["map"].items():
        src, dst = shots_dir / f"{shot_key}.png", vis / f"{scene_id:02d}.png"
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

    # 훅 모션 (편당 1컷) — 매핑된 첫 씬 번호로 저장
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
