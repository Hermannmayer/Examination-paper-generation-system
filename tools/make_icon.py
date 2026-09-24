"""把一张方形源图转成 Windows 多尺寸 .ico。

单独成脚本是为了让图标可复现：源图换了、或要调裁剪范围时重跑即可。

用法：
    .venv/Scripts/python.exe tools/make_icon.py <源图> [--out packaging/app.ico]

Windows 会按场景挑不同尺寸（任务栏 32、桌面 48、Alt+Tab 64、资源管理器大图标 256），
所以 .ico 里必须**同时**包含这些尺寸，只放一张 256 会在小尺寸下糊掉。
"""

from __future__ import annotations

import argparse
import os
import sys

from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "packaging", "app.ico")

# Windows 实际会用到的尺寸
ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]

# 源图是 2000x2000 且右下角带生成器水印，裁掉底部约 10% 并保持正方形。
# 换成无水印的源图时把 --crop 设成 none 即可。
DEFAULT_CROP_BOTTOM = 0.10


def load_square(source: str, crop_bottom: float) -> Image.Image:
    image = Image.open(source).convert("RGBA")
    width, height = image.size

    if crop_bottom <= 0:
        return image

    # 先按比例裁掉底部，再从左右对称裁回正方形，保证主体居中
    keep_height = int(height * (1.0 - crop_bottom))
    if keep_height >= width:
        left = 0
        box = (left, 0, width, keep_height)
        cropped = image.crop(box)
        # 高度仍大于宽度时，从底部再收一次
        if cropped.height > cropped.width:
            cropped = cropped.crop(
                (0, 0, cropped.width, cropped.width)
            ).resize((cropped.width, cropped.width))
    else:
        offset = (width - keep_height) // 2
        cropped = image.crop((offset, 0, offset + keep_height, keep_height))

    return cropped.resize((1024, 1024), Image.LANCZOS)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成 Windows 多尺寸 .ico")
    parser.add_argument("source", help="方形源图（png / webp / jpg）")
    parser.add_argument("--out", default=DEFAULT_OUT, help="输出的 .ico 路径")
    parser.add_argument(
        "--crop",
        type=float,
        default=DEFAULT_CROP_BOTTOM,
        help="裁掉底部高度的比例（用于去掉生成器水印）；0 表示不裁",
    )
    args = parser.parse_args(argv)

    if not os.path.isfile(args.source):
        print(f"找不到源图：{args.source}", file=sys.stderr)
        return 1

    image = load_square(args.source, args.crop)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    image.save(args.out, format="ICO", sizes=[(s, s) for s in ICON_SIZES])

    size_kb = os.path.getsize(args.out) / 1024
    print(f"已生成 {args.out}  ({size_kb:.1f} KB)")
    print(f"  尺寸：{'、'.join(str(s) for s in ICON_SIZES)}")

    # 顺便导出一张 png 便于肉眼确认裁剪效果
    preview = os.path.splitext(args.out)[0] + "-preview.png"
    image.resize((256, 256), Image.LANCZOS).save(preview)
    print(f"  预览：{preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
