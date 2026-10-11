"""生成 GitHub 仓库的分享预览图（social preview，1280x640）。

这张图是链接被贴到 V2EX / 掘金 / 微信里时信息流显示的那张卡片，内容取自演示 GIF
里 `holdings benchmark` 那一屏——**「跑赢沪深 300 了吗」是这个项目的压轴卖点**，
卡片上就得是它，而不是 `holdings list` 的持仓表。

    pip install pillow            # 一次性的，不是项目的依赖
    python docs/demo/make-card.py
    # 产物 .github/social-preview.png 需要在 GitHub 仓库
    # Settings -> Social preview 里手动上传，GitHub 没有对应的 API。

GIF 重录之后 `--frame` 大概率要跟着改：用
`ffmpeg -i docs/demo/holdings.gif -vf tile=4x3 -frames:v 1 /tmp/all.png`
铺一屏缩略图，挑出显示 `基准对比（…）：组合 … | 基准 … | 超额 …` 那一帧的序号。
索引写死是没办法的事——要按内容认帧就得引入 OCR，不值当。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]

W, H = 1280, 640
# 配色与终端截图同源（Dracula），底部截图才能和卡片的底色无缝接上。
BG = (40, 42, 54)
FG = (248, 248, 242)
MUTED = (184, 184, 208)
GREEN = (80, 250, 123)
RULE = (68, 71, 90)

# 中文字走 Hiragino（Arial 里没有汉字，渲染出来是一排豆腐块）。
LATIN = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
LATIN_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
CJK = "/System/Library/Fonts/Hiragino Sans GB.ttc"

# 截图只留「资产快照（含净入金）+ 基准对比」这一段：净入金那几列是
# 时间加权口径的全部来由，少了它，下面那行「超额 1.61%」看着就是个凭空的数。
CROP_TOP, CROP_BOTTOM = 496, 838
BOTTOM_MARGIN = 24


def extract_frame(gif: Path, frame: int, out: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-i",
            str(gif),
            "-vf",
            f"select=eq(n\\,{frame})",
            "-frames:v",
            "1",
            "-y",
            str(out),
        ],
        check=True,
    )


def build(frame_path: Path, out: Path) -> Image.Image:
    card = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(card)

    f_title = ImageFont.truetype(LATIN, 76)
    f_tag = ImageFont.truetype(CJK, 30, index=1)
    f_punch = ImageFont.truetype(CJK, 32, index=1)
    f_punch_en = ImageFont.truetype(LATIN_REGULAR, 29)

    draw.text((64, 56), "holdings", font=f_title, fill=FG)
    draw.text(
        (68, 152), "本地优先的持仓记账 CLI · 一个 SQLite 文件，没有账号", font=f_tag, fill=MUTED
    )
    draw.line([(64, 222), (1216, 222)], fill=RULE, width=2)

    draw.text((64, 240), "跑赢沪深 300 了吗？", font=f_punch, fill=FG)
    x = 64 + draw.textlength("跑赢沪深 300 了吗？", font=f_punch) + 22
    draw.text((x, 241), "超额", font=f_punch, fill=GREEN)
    draw.text(
        (x + draw.textlength("超额", font=f_punch) + 10, 246), "+1.61%", font=f_punch_en, fill=GREEN
    )

    shot = Image.open(frame_path).convert("RGB").crop((0, CROP_TOP, 1539, CROP_BOTTOM))
    shot = shot.resize((W, round(shot.height * W / shot.width)), Image.LANCZOS)
    card.paste(shot, (0, H - shot.height - BOTTOM_MARGIN))
    card.save(out, "PNG", optimize=True)
    return card


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gif", type=Path, default=ROOT / "docs/demo/holdings.gif")
    parser.add_argument("--out", type=Path, default=ROOT / ".github/social-preview.png")
    parser.add_argument("--frame", type=int, default=76, help="GIF 里 benchmark 结果那一帧")
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        frame_path = Path(tmp) / "frame.png"
        extract_frame(args.gif, args.frame, frame_path)
        card = build(frame_path, args.out)

    print(f"{args.out}：{card.width}x{card.height}（取自 {args.gif.name} 第 {args.frame} 帧）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
